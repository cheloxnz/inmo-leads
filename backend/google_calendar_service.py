"""
Google Calendar Service (Per-Tenant OAuth 2.0)
===============================================

Cada tenant (inmobiliaria) conecta su propia cuenta de Google Calendar. Los
tokens se guardan en `tenants.google_calendar` como:

    {
        "refresh_token": str,
        "access_token": str,
        "expires_at": str (ISO),
        "scope": str,
        "connected_email": str,
        "connected_at": str (ISO),
    }

El flujo:
1. `GET /api/oauth/calendar/start` → devuelve URL de consentimiento Google +
   genera `state` token temporal que mapea a `tenant_id` (TTL 10 min).
2. User consiente → Google redirige a `GET /api/oauth/calendar/callback?code&state`.
3. Backend intercambia `code` por tokens, valida `state`, persiste en el tenant.
4. Para cada call al Calendar API, `get_valid_credentials` refresca el
   access_token si expiró usando el refresh_token.

Scope: calendar.events (crear/editar) + calendar.readonly (listar) +
userinfo.email (para saber qué cuenta conectó).
"""
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def _client_config() -> dict:
    return {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", ""),
    }


def is_configured() -> bool:
    cfg = _client_config()
    return bool(cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"])


async def create_oauth_state(db, tenant_id: str, user_email: str = "") -> str:
    """Crea un state token (one-time, 10 min TTL) que mapea a tenant_id.
    Se valida en el callback para evitar CSRF."""
    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({
        "state": state,
        "tenant_id": tenant_id,
        "user_email": user_email,
        "provider": "google_calendar",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    })
    return state


async def consume_oauth_state(db, state: str) -> Optional[dict]:
    """Valida state, lo borra (one-shot), y devuelve el doc si es válido."""
    doc = await db.oauth_states.find_one({"state": state, "provider": "google_calendar"}, {"_id": 0})
    if not doc:
        return None
    try:
        expires = datetime.fromisoformat(doc["expires_at"].replace("Z", "+00:00"))
        if expires < datetime.now(timezone.utc):
            await db.oauth_states.delete_one({"state": state})
            return None
    except Exception:
        return None
    await db.oauth_states.delete_one({"state": state})
    return doc


def build_authorization_url(state: str) -> str:
    cfg = _client_config()
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # fuerza refresh_token
        "state": state,
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Intercambia el authorization code por tokens. Raises ValueError si falla."""
    cfg = _client_config()
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": cfg["redirect_uri"],
        "grant_type": "authorization_code",
    }, timeout=15)
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        logger.warning(f"[google_cal] token exchange failed: {data}")
        raise ValueError(data.get("error_description") or data.get("error") or "token exchange failed")
    return data


def fetch_userinfo(access_token: str) -> dict:
    resp = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        return {}
    return resp.json()


async def persist_tokens_for_tenant(db, tenant_id: str, token_resp: dict, connected_email: str):
    expires_in = int(token_resp.get("expires_in", 3600))
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))).isoformat()
    calendar_data = {
        "access_token": token_resp["access_token"],
        "scope": token_resp.get("scope", ""),
        "token_type": token_resp.get("token_type", "Bearer"),
        "expires_at": expires_at,
        "connected_email": connected_email,
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    # refresh_token viene solo la primera vez (o cuando prompt=consent). Preservamos el anterior si no vino.
    if token_resp.get("refresh_token"):
        calendar_data["refresh_token"] = token_resp["refresh_token"]
    else:
        existing = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0, "google_calendar": 1})
        if existing and existing.get("google_calendar", {}).get("refresh_token"):
            calendar_data["refresh_token"] = existing["google_calendar"]["refresh_token"]
    await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"google_calendar": calendar_data}},
    )


async def get_tenant_calendar(db, tenant_id: str) -> Optional[dict]:
    t = await db.tenants.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "google_calendar": 1},
    )
    if not t:
        return None
    cal = t.get("google_calendar")
    if not cal or not cal.get("refresh_token"):
        return None
    return cal


async def disconnect_tenant(db, tenant_id: str) -> bool:
    res = await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$unset": {"google_calendar": ""}},
    )
    return res.modified_count > 0


async def get_valid_credentials(db, tenant_id: str) -> Optional[Credentials]:
    """Obtiene Credentials válidas para Calendar API, refrescando si hace falta.
    Persiste el nuevo access_token al refrescar."""
    cal = await get_tenant_calendar(db, tenant_id)
    if not cal:
        return None
    cfg = _client_config()
    creds = Credentials(
        token=cal.get("access_token"),
        refresh_token=cal.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )
    # Forzamos refresh si expirado o cerca de expirar
    needs_refresh = False
    try:
        expires_at = datetime.fromisoformat(cal["expires_at"].replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            needs_refresh = True
    except Exception:
        needs_refresh = True

    if needs_refresh:
        try:
            creds.refresh(GoogleRequest())
            new_expires = (datetime.now(timezone.utc) + timedelta(seconds=3500)).isoformat()
            await db.tenants.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "google_calendar.access_token": creds.token,
                    "google_calendar.expires_at": new_expires,
                }},
            )
        except Exception as e:
            logger.warning(f"[google_cal] refresh failed for {tenant_id}: {e}")
            return None
    return creds


async def list_upcoming_events(db, tenant_id: str, max_results: int = 20) -> list:
    creds = await get_valid_credentials(db, tenant_id)
    if not creds:
        return []
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        result = service.events().list(
            calendarId="primary",
            timeMin=now_iso,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except HttpError as e:
        logger.warning(f"[google_cal] list events failed: {e}")
        return []


async def create_event(
    db,
    tenant_id: str,
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    attendee_email: str = "",
    timezone_name: str = "America/Argentina/Buenos_Aires",
) -> Optional[dict]:
    creds = await get_valid_credentials(db, tenant_id)
    if not creds:
        return None
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": timezone_name},
        "end": {"dateTime": end_iso, "timeZone": timezone_name},
    }
    if attendee_email:
        body["attendees"] = [{"email": attendee_email}]
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return service.events().insert(
            calendarId="primary", body=body, sendUpdates="all" if attendee_email else "none",
        ).execute()
    except HttpError as e:
        logger.warning(f"[google_cal] create event failed: {e}")
        return None


async def delete_event(db, tenant_id: str, event_id: str) -> bool:
    creds = await get_valid_credentials(db, tenant_id)
    if not creds:
        return False
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        service.events().delete(calendarId="primary", eventId=event_id, sendUpdates="all").execute()
        return True
    except HttpError as e:
        logger.warning(f"[google_cal] delete event failed: {e}")
        return False
