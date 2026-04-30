"""Founder Seats — plan de lanzamiento con cupos limitados.

Pattern "graduated pricing" (opción 2):
- Los primeros N clientes entran como "fundadores" y conservan su precio de por vida.
- Cuando se llega a N, se cierra el plan y los nuevos clientes pagan un precio mayor.

Expone:
- `GET /api/public/founder-seats` — público, consumido por la landing Shopify.
- `GET /api/superadmin/founder-seats/config` — config completa (solo superadmin).
- `PUT /api/superadmin/founder-seats/config` — update de total/boost/closes_at/active.

La cuenta de `taken` es híbrida:
- **Reales**: tenants con `is_founder=True` en DB (los que entraron dentro del cupo).
- **Boost inicial**: valor manual del superadmin para empezar en ≠ 0 al lanzamiento.
"""
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_routes import get_current_user, get_db
from cache_util import ttl_cache_get, ttl_cache_set, ttl_cache_invalidate
from models import User

router = APIRouter(tags=["founder"])

_db = get_db()

_CACHE_NS = "founder_seats"
_CACHE_KEY = "public_state"
_CACHE_TTL = 30.0  # 30s — balance entre freshness y carga a Mongo

_DEFAULT_CONFIG = {
    "total": 50,
    "boost": 8,
    "closes_at": "2026-05-31",
    "active": True,
}


def _require_superadmin(user: User):
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadmin")


async def _load_config() -> dict:
    """Upsert + retrieve del único documento de config en `settings.founder_plan`."""
    doc = await _db.settings.find_one(
        {"_id": "founder_plan"}, {"_id": 0}
    )
    if not doc:
        doc = dict(_DEFAULT_CONFIG)
        await _db.settings.update_one(
            {"_id": "founder_plan"},
            {"$setOnInsert": {**doc, "_id": "founder_plan"}},
            upsert=True,
        )
    # Defaults defensivos si el doc existe pero le falta algún campo
    for k, v in _DEFAULT_CONFIG.items():
        doc.setdefault(k, v)
    return doc


async def _count_real_founders() -> int:
    """Cuenta tenants con flag is_founder=True."""
    return await _db.tenants.count_documents({"is_founder": True})


async def _build_public_state(force: bool = False) -> dict:
    if not force:
        cached = ttl_cache_get(_CACHE_NS, _CACHE_KEY)
        if cached is not None:
            return cached

    cfg = await _load_config()
    real = await _count_real_founders()
    total = int(cfg.get("total", 50))
    boost = int(cfg.get("boost", 0))
    taken = min(total, real + boost)
    left = max(0, total - taken)
    percent = round((taken / total) * 100, 1) if total > 0 else 0.0
    closes_at = cfg.get("closes_at")

    # is_open: true si hay cupos Y no vencio la fecha Y está activo
    is_open = bool(cfg.get("active", True)) and left > 0
    if closes_at:
        try:
            # Permitimos "YYYY-MM-DD" (end of day UTC)
            d = date.fromisoformat(closes_at)
            end_dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > end_dt:
                is_open = False
        except (ValueError, TypeError):
            pass

    state = {
        "total": total,
        "taken": taken,
        "left": left,
        "percent": percent,
        "closes_at": closes_at,
        "is_open": is_open,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    ttl_cache_set(_CACHE_NS, _CACHE_KEY, state, ttl=_CACHE_TTL)
    return state


# ============================================================
# Public endpoint (no auth) — consumed by Shopify landing
# ============================================================

@router.get("/public/founder-seats")
async def public_founder_seats():
    """Estado público del plan fundador — consumido por la landing Shopify.

    Retorna shape estable: `{total, taken, left, percent, closes_at, is_open}`.
    Cacheado 30s en memoria para absorber tráfico alto sin castigar Mongo.
    """
    state = await _build_public_state()
    # Shape público: no exponemos `boost` ni el conteo real separado
    return {
        "total": state["total"],
        "taken": state["taken"],
        "left": state["left"],
        "percent": state["percent"],
        "closes_at": state["closes_at"],
        "is_open": state["is_open"],
    }


def _initials_from_name(name: str) -> str:
    """Devuelve iniciales anonimizadas de un business_name (ej: 'Acme Corp' -> 'AC')."""
    if not name:
        return "XX"
    words = [w for w in name.split() if w]
    if not words:
        return "XX"
    if len(words) == 1:
        return (words[0][:2] or "XX").upper()
    return (words[0][0] + words[-1][0]).upper()


def _time_ago_es(dt: datetime) -> str:
    """Devuelve string relativo en español: 'hace 3 min', 'hace 2 hs', 'hace 1 día'."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta_s = max(0, int((now - dt).total_seconds()))
    if delta_s < 60:
        return "hace un momento"
    if delta_s < 3600:
        m = delta_s // 60
        return f"hace {m} min"
    if delta_s < 86400:
        h = delta_s // 3600
        return f"hace {h} {'h' if h == 1 else 'hs'}"
    d = delta_s // 86400
    return f"hace {d} día" + ("s" if d > 1 else "")


@router.get("/public/founder-recent-signups")
async def public_recent_signups(limit: int = 5):
    """Firehose público (anonimizado) de charter members recientes.

    Consumido por el widget "live" de la landing Shopify. Retorna solo iniciales
    + tiempo relativo. No expone nombres reales, emails ni ubicación precisa.
    Cacheado 60s.
    """
    limit = max(1, min(limit, 10))
    cache_key = f"recent_signups_{limit}"
    cached = ttl_cache_get(_CACHE_NS, cache_key)
    if cached is not None:
        return cached

    cursor = _db.tenants.find(
        {"is_founder": True},
        {"_id": 0, "business_name": 1, "name": 1, "founder_joined_at": 1,
         "created_at": 1, "tenant_id": 1},
    ).sort("founder_joined_at", -1).limit(limit)

    items = []
    async for t in cursor:
        joined_raw = t.get("founder_joined_at") or t.get("created_at")
        if not joined_raw:
            continue
        try:
            joined_dt = datetime.fromisoformat(str(joined_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        name = t.get("business_name") or t.get("name") or ""
        items.append({
            "initials": _initials_from_name(name),
            "time_ago": _time_ago_es(joined_dt),
            "joined_at": joined_dt.isoformat(),
        })

    out = {"items": items, "count": len(items)}
    ttl_cache_set(_CACHE_NS, cache_key, out, ttl=60.0)
    return out


# ============================================================
# SuperAdmin config management
# ============================================================

class FounderConfigUpdate(BaseModel):
    total: Optional[int] = Field(default=None, ge=1, le=10000)
    boost: Optional[int] = Field(default=None, ge=0, le=10000)
    closes_at: Optional[str] = None  # "YYYY-MM-DD"
    active: Optional[bool] = None


@router.get("/superadmin/founder-seats/config")
async def get_founder_config(current_user: User = Depends(get_current_user)):
    _require_superadmin(current_user)
    cfg = await _load_config()
    real = await _count_real_founders()
    state = await _build_public_state(force=True)
    return {
        "config": cfg,
        "real_founders_count": real,
        "public_state": state,
    }


@router.put("/superadmin/founder-seats/config")
async def update_founder_config(
    payload: FounderConfigUpdate,
    current_user: User = Depends(get_current_user),
):
    _require_superadmin(current_user)
    db = _db

    # Validar closes_at si fue enviado
    if payload.closes_at is not None:
        try:
            date.fromisoformat(payload.closes_at)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="closes_at debe ser formato YYYY-MM-DD",
            )

    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    await db.settings.update_one(
        {"_id": "founder_plan"},
        {"$set": updates},
        upsert=True,
    )

    # Audit log
    await db.audit_log.insert_one({
        "tenant_id": None,
        "user_email": current_user.email,
        "action": "founder_config_updated",
        "updates": updates,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    ttl_cache_invalidate(_CACHE_NS)
    state = await _build_public_state(force=True)
    cfg = await _load_config()
    return {"config": cfg, "public_state": state}


@router.post("/superadmin/founder-seats/invalidate-cache")
async def invalidate_founder_cache(current_user: User = Depends(get_current_user)):
    """Fuerza recalculo inmediato (útil tras marcar tenants como founder manualmente)."""
    _require_superadmin(current_user)
    ttl_cache_invalidate(_CACHE_NS)
    state = await _build_public_state(force=True)
    return {"ok": True, "public_state": state}


# ============================================================
# Charter Members — listado + toggle manual
# ============================================================

@router.get("/superadmin/founders")
async def list_charter_members(current_user: User = Depends(get_current_user)):
    """Lista de charter members (tenants con is_founder=True).

    Devuelve campos útiles para el panel: tenant_id, business_name, email admin,
    founder_joined_at, plan, subscription_status. Ordenado desc por join date.
    """
    _require_superadmin(current_user)
    cursor = _db.tenants.find(
        {"is_founder": True},
        {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1,
         "founder_joined_at": 1, "created_at": 1, "subscription_plan": 1,
         "subscription_status": 1, "active": 1},
    ).sort("founder_joined_at", -1).limit(200)

    items = []
    async for t in cursor:
        tid = t["tenant_id"]
        agent = await _db.agents.find_one(
            {"tenant_id": tid, "role": "admin", "active": True},
            {"_id": 0, "email": 1},
        )
        items.append({
            "tenant_id": tid,
            "business_name": t.get("business_name") or t.get("name") or tid,
            "admin_email": (agent or {}).get("email"),
            "founder_joined_at": t.get("founder_joined_at") or t.get("created_at"),
            "subscription_plan": t.get("subscription_plan"),
            "subscription_status": t.get("subscription_status"),
            "active": bool(t.get("active", True)),
        })
    return {"items": items, "count": len(items)}


class ToggleFounderPayload(BaseModel):
    is_founder: bool


@router.post("/superadmin/tenants/{tenant_id}/toggle-founder")
async def toggle_founder_status(
    tenant_id: str,
    payload: ToggleFounderPayload,
    current_user: User = Depends(get_current_user),
):
    """Marca/desmarca manualmente un tenant como charter member.

    Útil para clientes que vinieron por fuera del flujo de signup (ventas directas,
    migraciones) o para corregir errores de atribución.
    """
    _require_superadmin(current_user)
    tenant = await _db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    update_fields = {"is_founder": payload.is_founder}
    if payload.is_founder and not tenant.get("founder_joined_at"):
        update_fields["founder_joined_at"] = datetime.now(timezone.utc).isoformat()

    await _db.tenants.update_one(
        {"tenant_id": tenant_id}, {"$set": update_fields}
    )

    # Audit log
    await _db.audit_log.insert_one({
        "tenant_id": tenant_id,
        "user_email": current_user.email,
        "action": "founder_toggle",
        "is_founder": payload.is_founder,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    ttl_cache_invalidate(_CACHE_NS)
    return {
        "ok": True,
        "tenant_id": tenant_id,
        "is_founder": payload.is_founder,
    }
