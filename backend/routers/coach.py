"""Smart Onboarding Coach - nudges contextuales para tenants en trial.

Detecta features sin usar y crea recordatorios in-app accionables.
Endpoints:
  GET  /api/coach/nudges          -> nudges activos del tenant actual
  POST /api/coach/nudges/{id}/dismiss -> marcar como descartado
  POST /api/coach/run             -> dispara el chequeo manualmente (admin only)

Tipos de nudges:
  - whatsapp_unconfigured  (signal: tenant.whatsapp_access_token vacio)
  - no_leads_yet           (signal: 0 leads en DB)
  - default_branding       (signal: colors == defaults)
  - ai_unused              (signal: 0 audit_logs de bot_config_ai_edit/flow_ai_edit)

Cada nudge es idempotente: solo 1 activo por (tenant_id, nudge_type).
Se dispara a partir de N dias de antiguedad del tenant.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth_routes import require_admin, get_db, get_current_user
from models import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["coach"])

DEFAULT_PRIMARY = "#3b82f6"
DEFAULT_ACCENT = "#8b5cf6"


# Definicion declarativa de nudges
# Cada uno tiene: type, days_since_signup_min, severity, builder(tenant, db)->Optional[dict]
async def _check_whatsapp_unconfigured(tenant: dict, db) -> dict | None:
    if tenant.get("whatsapp_access_token") and tenant.get("whatsapp_phone_number_id"):
        return None
    return {
        "title": "Configurá tu WhatsApp para empezar a recibir leads",
        "body": "Tu bot está listo pero todavía no conectaste el número de WhatsApp. Sin esto, los clientes no pueden chatear con tu negocio.",
        "cta_text": "Conectar WhatsApp",
        "cta_url": "/config",
        "severity": "high",
    }


async def _check_no_leads_yet(tenant: dict, db) -> dict | None:
    count = await db.leads.count_documents({"tenant_id": tenant["tenant_id"]})
    if count > 0:
        return None
    # Solo dispara si WhatsApp esta configurado (sino el otro nudge cubre el caso)
    if not tenant.get("whatsapp_access_token"):
        return None
    return {
        "title": "Todavía no recibiste tu primer lead",
        "body": "Tu bot está conectado pero no llegó nadie aún. Probá compartir tu link de WhatsApp en redes o agregar el widget de catálogo en tu web.",
        "cta_text": "Ver mi widget",
        "cta_url": "/widget",
        "severity": "warn",
    }


async def _check_default_branding(tenant: dict, db) -> dict | None:
    primary = (tenant.get("primary_color") or "").lower()
    accent = (tenant.get("accent_color") or "").lower()
    has_logo = bool(tenant.get("logo_url"))
    if has_logo and primary != DEFAULT_PRIMARY and accent != DEFAULT_ACCENT:
        return None
    return {
        "title": "Personalizá la marca de tu landing y widget",
        "body": "Tu landing pública sigue con los colores y logo por defecto. Subí tu logo y elegí tus colores corporativos en 30 segundos.",
        "cta_text": "Personalizar marca",
        "cta_url": "/landing",
        "severity": "info",
    }


async def _check_ai_unused(tenant: dict, db) -> dict | None:
    # Algun audit_log de IA del tenant?
    has_ai = await db.audit_log.find_one({
        "tenant_id": tenant["tenant_id"],
        "action": {"$in": ["bot_config_ai_edit", "flow_ai_edit"]},
    }, {"_id": 1})
    if has_ai:
        return None
    return {
        "title": "Probá el Asistente IA: editá tu bot hablándole",
        "body": "Decile a la IA 'cambia el horario a 9 a 19hs' o 'agrega un paso para preguntar el barrio' y el bot se reconfigura solo. Es la feature más zarpada del sistema.",
        "cta_text": "Probar Asistente IA",
        "cta_url": "/config",
        "severity": "info",
    }


# Lista de checks: (nudge_type, days_min, async_fn)
_CHECKS = [
    ("whatsapp_unconfigured", 1, _check_whatsapp_unconfigured),
    ("no_leads_yet", 3, _check_no_leads_yet),
    ("default_branding", 5, _check_default_branding),
    ("ai_unused", 7, _check_ai_unused),
]


def _parse_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


async def _evaluate_tenant(tenant: dict, db) -> int:
    """Corre todos los checks sobre un tenant y crea nudges nuevos si corresponde.
    Devuelve cantidad de nudges creados."""
    tenant_id = tenant.get("tenant_id")
    if not tenant_id:
        return 0
    created_at = _parse_dt(tenant.get("created_at")) or datetime.now(timezone.utc)
    age_days = (datetime.now(timezone.utc) - created_at).days
    created = 0

    for nudge_type, days_min, check_fn in _CHECKS:
        if age_days < days_min:
            continue
        # Idempotencia: ya existe un nudge activo (sin dismissed_at) de este tipo?
        existing = await db.coach_nudges.find_one(
            {"tenant_id": tenant_id, "nudge_type": nudge_type, "dismissed_at": None},
            {"_id": 1},
        )
        if existing:
            continue
        try:
            payload = await check_fn(tenant, db)
        except Exception as e:
            logger.warning(f"coach check {nudge_type} fallo para {tenant_id}: {e}")
            continue
        if not payload:
            continue
        doc = {
            "nudge_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "nudge_type": nudge_type,
            "title": payload["title"],
            "body": payload["body"],
            "cta_text": payload["cta_text"],
            "cta_url": payload["cta_url"],
            "severity": payload.get("severity", "info"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dismissed_at": None,
        }
        await db.coach_nudges.insert_one(doc)
        created += 1
    return created


async def run_coach_for_all_tenants(db) -> dict:
    """Llama desde el scheduler. Itera tenants en trial/active y evalua nudges."""
    total_created = 0
    total_evaluated = 0
    cursor = db.tenants.find(
        {"active": True},
        {"_id": 0, "tenant_id": 1, "created_at": 1, "primary_color": 1,
         "accent_color": 1, "logo_url": 1,
         "whatsapp_access_token": 1, "whatsapp_phone_number_id": 1,
         "subscription_status": 1, "subscription_plan": 1},
    )
    async for tenant in cursor:
        total_evaluated += 1
        try:
            total_created += await _evaluate_tenant(tenant, db)
        except Exception as e:
            logger.error(f"coach evaluate {tenant.get('tenant_id')} fallo: {e}")
    return {"evaluated": total_evaluated, "created": total_created}


# ---------------- Endpoints publicos ----------------

@router.get("/coach/nudges")
async def list_nudges(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Lista nudges activos (no descartados) del tenant actual."""
    docs = await db.coach_nudges.find(
        {"tenant_id": current_user.tenant_id, "dismissed_at": None},
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=20)
    return {"nudges": docs, "count": len(docs)}


@router.post("/coach/nudges/{nudge_id}/dismiss")
async def dismiss_nudge(
    nudge_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Marca un nudge como descartado. Solo afecta al propio tenant."""
    res = await db.coach_nudges.update_one(
        {"nudge_id": nudge_id, "tenant_id": current_user.tenant_id, "dismissed_at": None},
        {"$set": {"dismissed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Nudge no encontrado o ya descartado")
    return {"dismissed": True}


@router.post("/coach/run")
async def run_coach_now(
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Admin: dispara el chequeo manualmente para SU tenant.
    Util para development y para "refrescar" nudges sin esperar al cron."""
    tenant = await db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    created = await _evaluate_tenant(tenant, db)
    return {"created": created, "tenant_id": current_user.tenant_id}
