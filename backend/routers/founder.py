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
