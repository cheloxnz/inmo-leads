"""Endpoints del programa de comisiones por referidos."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from pydantic import BaseModel

from auth_routes import require_admin, get_db, get_current_user
from models import User
from feature_flags import FEATURE_FLAGS, get_tenant_features
from commission_service import (
    calculate_active_credit_for_tenant,
    get_or_create_referral_code,
    find_referrer_by_promo_code,
    COMMISSION_AMOUNT_USD,
    COMMISSION_DURATION_DAYS,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["commissions"])


@router.get("/tenant/features-showcase")
async def get_tenant_features_showcase(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Para el dashboard del tenant: lista de features con su estado y metadata.
    Devuelve {active:[...], available:[...]} para que la UI muestre activas + upsell de las disponibles."""
    tenant = await db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {"_id": 0, "features": 1},
    ) if current_user.tenant_id else None

    state = get_tenant_features(tenant or {})
    active = []
    available = []
    for key, meta in FEATURE_FLAGS.items():
        item = {
            "key": key,
            "label": meta["label"],
            "description": meta["description"],
            "category": meta["category"],
            "enabled": bool(state.get(key)),
        }
        (active if item["enabled"] else available).append(item)
    return {"active": active, "available": available, "total": len(FEATURE_FLAGS)}


@router.get("/commissions/promo-code")
async def get_promo_code(
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Devuelve (o crea) el referral_code y promotion_code del tenant actual."""
    res = await get_or_create_referral_code(db, current_user.tenant_id)
    if not res.get("code"):
        raise HTTPException(500, detail="No se pudo generar el código de referido")
    return res


class ResolvePromoBody(BaseModel):
    code: str


@router.post("/commissions/resolve-promo")
async def resolve_promo_public(body: ResolvePromoBody, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Endpoint público (sin auth): valida un código y devuelve el tenant_id del referrer +
    el business_name. Lo usa el wizard de signup cuando alguien pega un código.
    """
    code = (body.code or "").upper().strip()
    if not code or len(code) > 40:
        raise HTTPException(400, detail="Código inválido")
    tid = await find_referrer_by_promo_code(db, code)
    if not tid:
        return {"valid": False}
    t = await db.tenants.find_one(
        {"tenant_id": tid},
        {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1},
    )
    return {
        "valid": True,
        "ref_tenant_id": tid,
        "business_name": (t or {}).get("business_name") or (t or {}).get("name") or "—",
    }


@router.get("/commissions/summary")
async def commissions_summary(
    current_user: User = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Dashboard del referrer: cuanto credito tiene activo + total ganado historico + listado."""
    credit = await calculate_active_credit_for_tenant(db, current_user.tenant_id)

    # Total credited historico (suma de todos los applied_invoices)
    pipeline = [
        {"$match": {"referrer_tenant_id": current_user.tenant_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "credited": {"$sum": {"$ifNull": ["$total_credited_usd", 0]}},
        }},
    ]
    by_status = {d["_id"]: d for d in await db.commissions.aggregate(pipeline).to_list(length=10)}

    total_lifetime_credit = sum(d.get("credited", 0) for d in by_status.values())

    # Listado de comisiones (todas, ordenadas por status + created_at)
    cursor = db.commissions.find(
        {"referrer_tenant_id": current_user.tenant_id},
        {"_id": 0},
    ).sort([("status", 1), ("created_at", -1)])
    items = await cursor.to_list(length=200)

    # Enriquecer con business_name del referido
    referred_ids = list({c["referred_tenant_id"] for c in items if c.get("referred_tenant_id")})
    referred_map = {}
    if referred_ids:
        async for t in db.tenants.find(
            {"tenant_id": {"$in": referred_ids}},
            {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1, "subscription_status": 1},
        ):
            referred_map[t["tenant_id"]] = t

    enriched = []
    for c in items:
        rid = c.get("referred_tenant_id")
        ref_t = referred_map.get(rid, {})
        out = {
            "commission_id": c.get("commission_id"),
            "referred_tenant_id": rid,
            "referred_business_name": ref_t.get("business_name") or ref_t.get("name") or "—",
            "referred_subscription_status": ref_t.get("subscription_status"),
            "amount_per_month_usd": c.get("amount_per_month_usd"),
            "status": c.get("status"),
            "total_credited_usd": c.get("total_credited_usd", 0),
            "applied_invoices_count": len(c.get("applied_invoices", [])),
        }
        for k in ("created_at", "activated_at", "expires_at", "cancelled_at"):
            v = c.get(k)
            if isinstance(v, datetime):
                out[k] = v.isoformat()
            elif v is not None:
                out[k] = v
        enriched.append(out)

    return {
        "config": {
            "amount_per_referral_usd": COMMISSION_AMOUNT_USD,
            "duration_days": COMMISSION_DURATION_DAYS,
        },
        "active_credit": credit,
        "total_lifetime_credit_usd": round(total_lifetime_credit, 2),
        "by_status": {
            s: {"count": d.get("count", 0), "credited_usd": round(d.get("credited", 0), 2)}
            for s, d in by_status.items()
        },
        "commissions": enriched,
        "promo_code": await get_or_create_referral_code(db, current_user.tenant_id),
    }
