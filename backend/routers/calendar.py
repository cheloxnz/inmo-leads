"""
Router de Google Calendar (OAuth per-tenant + CRUD events).

Flujo OAuth:
- `GET /api/oauth/calendar/start` (auth JWT): devuelve authorization_url.
- `GET /api/oauth/calendar/callback` (público, lo llama Google): canjea code,
  persiste tokens, redirige a /config con ?calendar=connected|error.

Uso:
- `GET /api/calendar/status`: si el tenant tiene la integración activa.
- `GET /api/calendar/events?max_results=20`: lista próximos eventos.
- `POST /api/calendar/events`: crea evento.
- `DELETE /api/calendar/events/{id}`: elimina evento.
- `POST /api/calendar/disconnect`: desvincula la cuenta del tenant.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional

from auth_routes import get_current_user, require_admin
from models import User
import google_calendar_service as gcal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["google-calendar"])

_db_holder = {"db": None}


def init_router(db):
    _db_holder["db"] = db


def _db():
    return _db_holder["db"]


class CreateEventBody(BaseModel):
    summary: str
    start_iso: str  # "2026-05-10T14:00:00-03:00"
    end_iso: str
    description: Optional[str] = ""
    attendee_email: Optional[str] = ""
    timezone: Optional[str] = "America/Argentina/Buenos_Aires"


@router.get("/oauth/calendar/start")
async def oauth_start(current_user: User = Depends(require_admin)):
    """Genera URL de consentimiento Google para el tenant del user actual."""
    if not gcal.is_configured():
        raise HTTPException(status_code=503, detail="Google Calendar no está configurado en el servidor")
    state = await gcal.create_oauth_state(
        _db(), tenant_id=current_user.tenant_id, user_email=current_user.email or "",
    )
    url = gcal.build_authorization_url(state)
    return {"authorization_url": url}


@router.get("/oauth/calendar/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Callback público al que redirige Google. No requiere JWT (es Google
    quien lo llama en el browser del user). La autorización se valida con
    el `state` token one-shot que generamos en /start."""
    # Usamos APP_URL configurado para redirigir de vuelta al frontend
    import os
    app_url = os.environ.get("APP_URL", "").rstrip("/")
    front_config_url = f"{app_url}/config" if app_url else "/config"

    if error:
        return RedirectResponse(f"{front_config_url}?calendar=error&reason={error}", status_code=302)
    if not code or not state:
        return RedirectResponse(f"{front_config_url}?calendar=error&reason=missing_params", status_code=302)

    state_doc = await gcal.consume_oauth_state(_db(), state)
    if not state_doc:
        return RedirectResponse(f"{front_config_url}?calendar=error&reason=invalid_state", status_code=302)

    try:
        tokens = gcal.exchange_code_for_tokens(code)
    except Exception as e:
        logger.warning(f"[calendar] token exchange failed: {e}")
        return RedirectResponse(f"{front_config_url}?calendar=error&reason=token_exchange", status_code=302)

    user_info = gcal.fetch_userinfo(tokens["access_token"])
    email = user_info.get("email", "")

    try:
        await gcal.persist_tokens_for_tenant(
            _db(), tenant_id=state_doc["tenant_id"],
            token_resp=tokens, connected_email=email,
        )
    except Exception as e:
        logger.warning(f"[calendar] persist failed: {e}")
        return RedirectResponse(f"{front_config_url}?calendar=error&reason=persist", status_code=302)

    return RedirectResponse(f"{front_config_url}?calendar=connected", status_code=302)


@router.get("/calendar/status")
async def calendar_status(current_user: User = Depends(get_current_user)):
    cal = await gcal.get_tenant_calendar(_db(), current_user.tenant_id)
    return {
        "configured": gcal.is_configured(),
        "connected": bool(cal),
        "connected_email": (cal or {}).get("connected_email", ""),
        "connected_at": (cal or {}).get("connected_at", ""),
    }


@router.get("/calendar/events")
async def list_events(
    max_results: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    cal = await gcal.get_tenant_calendar(_db(), current_user.tenant_id)
    if not cal:
        raise HTTPException(status_code=400, detail="Google Calendar no conectado para este tenant")
    events = await gcal.list_upcoming_events(_db(), current_user.tenant_id, max_results=max_results)
    return {
        "count": len(events),
        "events": [
            {
                "id": e.get("id"),
                "summary": e.get("summary", ""),
                "description": e.get("description", ""),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                "html_link": e.get("htmlLink"),
                "attendees": [a.get("email") for a in (e.get("attendees") or []) if a.get("email")],
            }
            for e in events
        ],
    }


@router.post("/calendar/events")
async def create_event_endpoint(
    body: CreateEventBody,
    current_user: User = Depends(get_current_user),
):
    cal = await gcal.get_tenant_calendar(_db(), current_user.tenant_id)
    if not cal:
        raise HTTPException(status_code=400, detail="Google Calendar no conectado")
    ev = await gcal.create_event(
        _db(), tenant_id=current_user.tenant_id,
        summary=body.summary, start_iso=body.start_iso, end_iso=body.end_iso,
        description=body.description or "", attendee_email=body.attendee_email or "",
        timezone_name=body.timezone or "America/Argentina/Buenos_Aires",
    )
    if not ev:
        raise HTTPException(status_code=500, detail="No se pudo crear el evento")
    return {
        "id": ev.get("id"),
        "html_link": ev.get("htmlLink"),
        "summary": ev.get("summary"),
        "start": ev.get("start"),
        "end": ev.get("end"),
    }


@router.delete("/calendar/events/{event_id}")
async def delete_event_endpoint(
    event_id: str,
    current_user: User = Depends(get_current_user),
):
    cal = await gcal.get_tenant_calendar(_db(), current_user.tenant_id)
    if not cal:
        raise HTTPException(status_code=400, detail="Google Calendar no conectado")
    ok = await gcal.delete_event(_db(), current_user.tenant_id, event_id)
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo eliminar el evento")
    return {"deleted": True}


@router.post("/calendar/availability")
async def check_availability_endpoint(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Chequea si un slot está libre en el Calendar del tenant + sugiere
    alternativas si está ocupado.

    Body: {
      start_iso: str,            # "2026-05-10T15:00:00-03:00"
      duration_minutes: int = 60
    }
    Returns: {connected, available, preferred_start, preferred_end, alternatives: [iso]}
    """
    from datetime import datetime
    start_iso = (body or {}).get("start_iso")
    duration = int((body or {}).get("duration_minutes", 60))
    if not start_iso:
        raise HTTPException(status_code=400, detail="start_iso requerido")
    try:
        preferred = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="start_iso inválido (use ISO 8601)")
    return await gcal.check_availability(
        db=_db(),
        tenant_id=current_user.tenant_id,
        preferred_start=preferred,
        duration_minutes=duration,
    )


@router.post("/calendar/disconnect")
async def disconnect_endpoint(current_user: User = Depends(require_admin)):
    ok = await gcal.disconnect_tenant(_db(), current_user.tenant_id)
    return {"disconnected": ok}
