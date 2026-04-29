"""Smart Onboarding Coach - nudges contextuales para tenants en trial.

Detecta features sin usar y crea recordatorios in-app accionables.
Endpoints:
  GET  /api/coach/nudges                  -> nudges activos del tenant actual
  POST /api/coach/nudges/{id}/dismiss     -> marcar como descartado
  POST /api/coach/run                     -> dispara el chequeo manualmente (admin only)
  GET  /api/coach/celebrations            -> celebraciones por logros recientes
  POST /api/coach/celebrations/{id}/seen  -> marcar celebracion como vista

Tipos de nudges:
  - whatsapp_unconfigured  (signal: tenant.whatsapp_access_token vacio)
  - no_leads_yet           (signal: 0 leads en DB)
  - default_branding       (signal: colors == defaults)
  - ai_unused              (signal: 0 audit_logs de bot_config_ai_edit/flow_ai_edit)

Cada nudge es idempotente: solo 1 activo por (tenant_id, nudge_type).
Se dispara a partir de N dias de antiguedad del tenant.

Tipos de celebraciones (auto-detectadas tras resolver un signal):
  - whatsapp_connected  (gano whatsapp_access_token)
  - first_lead          (paso de 0 a >=1 lead)
  - branding_customized (subio logo o cambio colores default)
  - first_ai_edit       (primer uso de Asistente IA)
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth_routes import require_admin, get_db, get_current_user
from models import User
from cache_util import ttl_cache_get, ttl_cache_set, ttl_cache_invalidate

logger = logging.getLogger(__name__)
router = APIRouter(tags=["coach"])

DEFAULT_PRIMARY = "#3b82f6"
DEFAULT_ACCENT = "#8b5cf6"

# Retencion de nudges descartados (TTL Mongo).
NUDGE_DISMISS_TTL_DAYS = 90
CELEBRATION_TTL_DAYS = 30
CELEBRATIONS_DETECT_TTL = 60.0  # cache 60s para evitar N find_one por GET


class Severity(str, Enum):
    HIGH = "high"
    WARN = "warn"
    INFO = "info"


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
        "severity": Severity.HIGH.value,
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
        "severity": Severity.WARN.value,
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
        "severity": Severity.INFO.value,
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
        "severity": Severity.INFO.value,
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
        # Validar severity contra el enum (defense in depth)
        sev = payload.get("severity", Severity.INFO.value)
        if sev not in {s.value for s in Severity}:
            sev = Severity.INFO.value
        doc = {
            "nudge_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "nudge_type": nudge_type,
            "title": payload["title"],
            "body": payload["body"],
            "cta_text": payload["cta_text"],
            "cta_url": payload["cta_url"],
            "severity": sev,
            "created_at": datetime.now(timezone.utc),  # BSON datetime (consistencia con dismissed_at)
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
    # Normalizar datetime BSON -> ISO string para JSON
    for d in docs:
        for k in ("created_at", "dismissed_at"):
            v = d.get(k)
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return {"nudges": docs, "count": len(docs)}


@router.post("/coach/nudges/{nudge_id}/dismiss")
async def dismiss_nudge(
    nudge_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Marca un nudge como descartado. Idempotente.
    dismissed_at se guarda como datetime BSON (no string) para que el TTL index funcione.
    """
    now = datetime.now(timezone.utc)
    res = await db.coach_nudges.update_one(
        {"nudge_id": nudge_id, "tenant_id": current_user.tenant_id, "dismissed_at": None},
        {"$set": {"dismissed_at": now}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Nudge no encontrado o ya descartado")

    # Tras dismiss, evaluar si el signal subyacente esta resuelto -> crear celebracion
    try:
        await _maybe_create_celebration(current_user.tenant_id, nudge_id, db)
        # Invalidar cache de detection: el proximo GET evaluara fresco
        ttl_cache_invalidate("celebrations_detected", current_user.tenant_id)
    except Exception as e:
        logger.warning(f"celebration check fallo: {e}")
    return {"dismissed": True}


# ---------------- Celebrations ----------------

# (celebration_type, signal_check_fn(tenant, db) -> Optional[dict])
async def _check_whatsapp_connected(tenant: dict, db) -> dict | None:
    if not (tenant.get("whatsapp_access_token") and tenant.get("whatsapp_phone_number_id")):
        return None
    return {
        "title": "🎉 ¡WhatsApp conectado!",
        "body": "Tu bot ya está activo. Compartí tu link y empezá a recibir leads automáticamente las 24hs.",
        "cta_text": "Ver mi widget",
        "cta_url": "/widget",
        "emoji": "📱",
    }


async def _check_first_lead(tenant: dict, db) -> dict | None:
    count = await db.leads.count_documents({"tenant_id": tenant["tenant_id"]})
    if count < 1:
        return None
    return {
        "title": "🎉 ¡Llegaron tus primeros leads!",
        "body": f"Ya tenés {count} {'lead' if count == 1 else 'leads'} en el pipeline. Mirá quién está caliente y empezá a vender.",
        "cta_text": "Ver pipeline",
        "cta_url": "/leads",
        "emoji": "🚀",
        "metric": count,
    }


async def _check_branding_customized(tenant: dict, db) -> dict | None:
    primary = (tenant.get("primary_color") or "").lower()
    accent = (tenant.get("accent_color") or "").lower()
    has_logo = bool(tenant.get("logo_url"))
    if not has_logo and primary == DEFAULT_PRIMARY and accent == DEFAULT_ACCENT:
        return None
    return {
        "title": "🎉 ¡Branding personalizado!",
        "body": "Tu landing y widget ya muestran tu identidad. Compartí el link y dejá huella.",
        "cta_text": "Ver mi landing",
        "cta_url": "/landing",
        "emoji": "🎨",
    }


async def _check_first_ai_edit(tenant: dict, db) -> dict | None:
    has_ai = await db.audit_log.find_one({
        "tenant_id": tenant["tenant_id"],
        "action": {"$in": ["bot_config_ai_edit", "flow_ai_edit"]},
    }, {"_id": 1})
    if not has_ai:
        return None
    return {
        "title": "🎉 ¡Usaste el Asistente IA!",
        "body": "Acabás de configurar tu bot conversando. Probá tambien editar el flujo desde el FlowBuilder.",
        "cta_text": "Editor de flujo",
        "cta_url": "/flujo",
        "emoji": "✨",
    }


_CELEBRATIONS = [
    ("whatsapp_connected", _check_whatsapp_connected),
    ("first_lead", _check_first_lead),
    ("branding_customized", _check_branding_customized),
    ("first_ai_edit", _check_first_ai_edit),
]


async def _maybe_create_celebration(tenant_id: str, nudge_id: str, db) -> None:
    """Tras dismiss de un nudge, chequeamos si el signal correspondiente fue resuelto.
    Mapping nudge_type -> celebration_type."""
    nudge = await db.coach_nudges.find_one({"nudge_id": nudge_id}, {"_id": 0, "nudge_type": 1})
    if not nudge:
        return
    mapping = {
        "whatsapp_unconfigured": "whatsapp_connected",
        "no_leads_yet": "first_lead",
        "default_branding": "branding_customized",
        "ai_unused": "first_ai_edit",
    }
    cel_type = mapping.get(nudge["nudge_type"])
    if not cel_type:
        return
    await _detect_celebrations_for_tenant(tenant_id, db, only_type=cel_type)


async def _detect_celebrations_for_tenant(tenant_id: str, db, only_type: str = None) -> int:
    """Evalua todas las celebraciones para un tenant. Idempotente.
    Solo crea si no existe ya una celebration del mismo tipo para este tenant."""
    tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        return 0
    created = 0
    for cel_type, check_fn in _CELEBRATIONS:
        if only_type and cel_type != only_type:
            continue
        existing = await db.coach_celebrations.find_one(
            {"tenant_id": tenant_id, "celebration_type": cel_type},
            {"_id": 1},
        )
        if existing:
            continue
        try:
            payload = await check_fn(tenant, db)
        except Exception as e:
            logger.warning(f"celebration check {cel_type} fallo: {e}")
            continue
        if not payload:
            continue
        doc = {
            "celebration_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "celebration_type": cel_type,
            "title": payload["title"],
            "body": payload["body"],
            "cta_text": payload.get("cta_text", ""),
            "cta_url": payload.get("cta_url", ""),
            "emoji": payload.get("emoji", "🎉"),
            "metric": payload.get("metric"),
            "created_at": datetime.now(timezone.utc),
            "seen_at": None,
        }
        await db.coach_celebrations.insert_one(doc)
        created += 1
    return created


@router.get("/coach/celebrations")
async def list_celebrations(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Detecta nuevas celebraciones (lazy, cacheado 60s) y devuelve las no vistas del tenant."""
    # Cache: solo correr la deteccion completa cada 60s por tenant
    cache_key = current_user.tenant_id
    if ttl_cache_get("celebrations_detected", cache_key) is None:
        await _detect_celebrations_for_tenant(current_user.tenant_id, db)
        ttl_cache_set("celebrations_detected", cache_key, True, ttl=CELEBRATIONS_DETECT_TTL)

    docs = await db.coach_celebrations.find(
        {"tenant_id": current_user.tenant_id, "seen_at": None},
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=10)
    for d in docs:
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
    return {"celebrations": docs, "count": len(docs)}


@router.post("/coach/celebrations/{celebration_id}/seen")
async def mark_celebration_seen(
    celebration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Marca una celebracion como vista (no aparece mas en feed)."""
    res = await db.coach_celebrations.update_one(
        {"celebration_id": celebration_id, "tenant_id": current_user.tenant_id, "seen_at": None},
        {"$set": {"seen_at": datetime.now(timezone.utc)}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Celebracion no encontrada o ya vista")
    return {"seen": True}


@router.post("/coach/celebrations/{celebration_id}/share")
async def track_celebration_share(
    celebration_id: str,
    body: dict = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Registra que el usuario compartio una celebracion (analytics + KPI Coach effectiveness).

    Body: {"platform": "twitter|linkedin|download|copy"}.
    Devuelve datos para construir la card en frontend (canvas) y el share text.
    """
    platform = ((body or {}).get("platform") or "unknown")[:20].lower()
    if platform not in {"twitter", "linkedin", "facebook", "download", "copy", "unknown"}:
        platform = "unknown"

    cel = await db.coach_celebrations.find_one(
        {"celebration_id": celebration_id, "tenant_id": current_user.tenant_id},
        {"_id": 0},
    )
    if not cel:
        raise HTTPException(status_code=404, detail="Celebracion no encontrada")

    tenant = await db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {"_id": 0, "business_name": 1, "name": 1, "logo_url": 1,
         "primary_color": 1, "accent_color": 1},
    ) or {}

    # Persistir share count
    await db.coach_celebrations.update_one(
        {"celebration_id": celebration_id, "tenant_id": current_user.tenant_id},
        {"$inc": {f"shares.{platform}": 1, "shares.total": 1},
         "$set": {"last_shared_at": datetime.now(timezone.utc)}},
    )
    # Audit log
    try:
        await db.audit_log.insert_one({
            "tenant_id": current_user.tenant_id,
            "user_email": current_user.email,
            "action": "celebration_shared",
            "celebration_type": cel.get("celebration_type"),
            "platform": platform,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    business = tenant.get("business_name") or tenant.get("name") or "Mi negocio"
    share_text = (
        f"{cel.get('emoji', '🎉')} {cel.get('title', 'Logre un milestone')} "
        f"con InmoBot AI 🚀\n\n#SaaS #AI #WhatsApp #PyME"
    )

    return {
        "tracked": True,
        "platform": platform,
        "card_data": {
            "celebration_type": cel.get("celebration_type"),
            "emoji": cel.get("emoji", "🎉"),
            "title": cel.get("title"),
            "body": cel.get("body"),
            "metric": cel.get("metric"),
            "tenant_id": current_user.tenant_id,
            "business_name": business,
            "logo_url": tenant.get("logo_url") or "",
            "primary_color": tenant.get("primary_color") or DEFAULT_PRIMARY,
            "accent_color": tenant.get("accent_color") or DEFAULT_ACCENT,
            "powered_by": "InmoBot AI",
        },
        "share_text": share_text,
    }


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


@router.get("/coach/referral-stats")
async def get_referral_stats(
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Stats del programa de referidos del tenant (compartió celebraciones, gente que clickeó/se registro).
    Funnel: html_views -> leads -> signups."""
    tenant = await db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {"_id": 0, "referral_stats": 1},
    ) or {}
    stats = tenant.get("referral_stats") or {}

    # Total preview/html views agregando todas las celebrations del tenant
    pipeline = [
        {"$match": {"tenant_id": current_user.tenant_id}},
        {"$group": {
            "_id": None,
            "preview_views": {"$sum": {"$ifNull": ["$shares.preview_views", 0]}},
            "html_views": {"$sum": {"$ifNull": ["$shares.html_views", 0]}},
            "shares_total": {"$sum": {"$ifNull": ["$shares.total", 0]}},
        }},
    ]
    agg = await db.coach_celebrations.aggregate(pipeline).to_list(length=1)
    share_views = agg[0] if agg else {"preview_views": 0, "html_views": 0, "shares_total": 0}

    leads_count = await db.referral_leads.count_documents({"ref_tenant_id": current_user.tenant_id})
    converted = await db.referral_leads.count_documents({
        "ref_tenant_id": current_user.tenant_id,
        "converted_tenant_id": {"$ne": None},
    })

    return {
        "shares_explicit": share_views["shares_total"],
        "preview_views": share_views["preview_views"],
        "html_views": share_views["html_views"],
        "leads_captured": leads_count,
        "signups_converted": converted,
        "tenant_signups_via_ref": stats.get("signups", 0),
        "conversion_rate": min(100.0, round((converted / leads_count) * 100, 1)) if leads_count else 0,
    }


@router.get("/coach/effectiveness")
async def get_coach_effectiveness(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Dashboard de Coach Effectiveness.
    Devuelve funnel agregado + time series + top celebrations.

    Query params:
      days: ventana temporal (default 30, clamped 1..90)
    """
    try:
        d = int(days) if days is not None else 30
    except (TypeError, ValueError):
        d = 30
    days = max(1, min(d, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    tenant_id = current_user.tenant_id

    # Funnel agregado (totales)
    funnel_pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {
            "_id": None,
            "shares_total": {"$sum": {"$ifNull": ["$shares.total", 0]}},
            "shares_twitter": {"$sum": {"$ifNull": ["$shares.twitter", 0]}},
            "shares_linkedin": {"$sum": {"$ifNull": ["$shares.linkedin", 0]}},
            "shares_download": {"$sum": {"$ifNull": ["$shares.download", 0]}},
            "preview_views": {"$sum": {"$ifNull": ["$shares.preview_views", 0]}},
            "html_views": {"$sum": {"$ifNull": ["$shares.html_views", 0]}},
        }},
    ]
    agg = await db.coach_celebrations.aggregate(funnel_pipeline).to_list(length=1)
    share_data = agg[0] if agg else {}

    leads_total = await db.referral_leads.count_documents({"ref_tenant_id": tenant_id})
    leads_in_window = await db.referral_leads.count_documents({
        "ref_tenant_id": tenant_id,
        "created_at": {"$gte": since},
    })
    converted_total = await db.referral_leads.count_documents({
        "ref_tenant_id": tenant_id,
        "converted_tenant_id": {"$ne": None},
    })
    converted_in_window = await db.referral_leads.count_documents({
        "ref_tenant_id": tenant_id,
        "converted_tenant_id": {"$ne": None},
        "converted_at": {"$gte": since},
    })

    # Time series: leads y conversions por dia
    leads_ts_pipeline = [
        {"$match": {"ref_tenant_id": tenant_id, "created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "leads": {"$sum": 1},
            "converted": {"$sum": {"$cond": [
                {"$ne": ["$converted_tenant_id", None]}, 1, 0,
            ]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    ts_docs = await db.referral_leads.aggregate(leads_ts_pipeline).to_list(length=days + 5)
    timeseries = [
        {"date": d["_id"], "leads": d.get("leads", 0), "converted": d.get("converted", 0)}
        for d in ts_docs
    ]

    # Top celebrations por shares + leads
    top_pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$project": {
            "_id": 0,
            "celebration_id": 1,
            "celebration_type": 1,
            "title": 1,
            "shares_total": {"$ifNull": ["$shares.total", 0]},
            "preview_views": {"$ifNull": ["$shares.preview_views", 0]},
            "html_views": {"$ifNull": ["$shares.html_views", 0]},
            "created_at": 1,
        }},
        {"$sort": {"shares_total": -1, "html_views": -1}},
        {"$limit": 10},
    ]
    top_celebrations = await db.coach_celebrations.aggregate(top_pipeline).to_list(length=10)

    # Para cada top, contar leads asociados (separate query, mas claro que $lookup)
    for tc in top_celebrations:
        cid = tc.get("celebration_id")
        if cid:
            tc["leads"] = await db.referral_leads.count_documents({
                "ref_tenant_id": tenant_id,
                "ref_celebration_id": cid,
            })
            tc["converted"] = await db.referral_leads.count_documents({
                "ref_tenant_id": tenant_id,
                "ref_celebration_id": cid,
                "converted_tenant_id": {"$ne": None},
            })
        if isinstance(tc.get("created_at"), datetime):
            tc["created_at"] = tc["created_at"].isoformat()

    # Conversion rates en cada etapa del funnel
    shares = share_data.get("shares_total", 0)
    html_views = share_data.get("html_views", 0)
    preview_views = share_data.get("preview_views", 0)

    def _rate(num, denom):
        if not denom:
            return 0
        return min(100.0, round((num / denom) * 100, 1))

    return {
        "window_days": days,
        "funnel": {
            "shares_explicit": shares,
            "preview_views": preview_views,  # crawlers + visits a la imagen .png
            "html_views": html_views,         # paginas HTML visitadas (visitor real)
            "leads_captured": leads_total,
            "signups_converted": converted_total,
        },
        "funnel_rates": {
            "view_to_lead": _rate(leads_total, html_views),
            "lead_to_signup": _rate(converted_total, leads_total),
            "share_to_view": _rate(html_views, shares),
            "overall_share_to_signup": _rate(converted_total, shares),
        },
        "by_platform": {
            "twitter": share_data.get("shares_twitter", 0),
            "linkedin": share_data.get("shares_linkedin", 0),
            "download": share_data.get("shares_download", 0),
        },
        "in_window": {
            "leads": leads_in_window,
            "converted": converted_in_window,
        },
        "timeseries": timeseries,
        "top_celebrations": top_celebrations,
    }
