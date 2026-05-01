"""Router de metricas globales para SuperAdmin"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_routes import get_current_user, get_db
from payment_service import SUBSCRIPTION_PLANS
from feature_flags import (
    FEATURE_FLAGS, get_tenant_features, update_tenant_feature,
)
from models import User

router = APIRouter(tags=["superadmin"])

_db = get_db()


def _require_superadmin(user: User):
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadmin")


@router.get("/superadmin/metrics")
async def get_global_metrics(current_user: User = Depends(get_current_user)):
    """Dashboard SuperAdmin: MRR, tenants, plans distribution, overage, leads totales, churn"""
    _require_superadmin(current_user)

    now = datetime.now(timezone.utc)
    period_key = now.strftime("%Y-%m")
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    # Tenants totales y por plan
    total_tenants = await _db.tenants.count_documents({})
    active_tenants = await _db.tenants.count_documents({"subscription_status": "active"})
    past_due = await _db.tenants.count_documents({"subscription_status": "past_due"})
    cancelled = await _db.tenants.count_documents({"subscription_status": {"$in": ["cancelled", "cancelling"]}})

    # Distribucion por plan + MRR
    plans_pipeline = [
        {"$match": {"subscription_status": "active"}},
        {"$group": {"_id": "$subscription_plan", "count": {"$sum": 1}}},
    ]
    plans_raw = await _db.tenants.aggregate(plans_pipeline).to_list(20)
    plans_distribution = []
    mrr = 0.0
    for p in plans_raw:
        plan_id = p["_id"] or "unknown"
        count = p["count"]
        price = SUBSCRIPTION_PLANS.get(plan_id, {}).get("price_monthly", 0)
        plans_distribution.append({
            "plan_id": plan_id,
            "plan_name": SUBSCRIPTION_PLANS.get(plan_id, {}).get("name", plan_id),
            "count": count,
            "price_monthly": price,
            "subtotal_mrr": count * price
        })
        mrr += count * price

    # Overage del periodo actual - todos los tenants
    overage_pipeline = [
        {"$match": {"period": period_key}},
        {"$group": {
            "_id": None,
            "total_overage": {"$sum": "$overage_messages"},
            "total_ai_messages": {"$sum": "$ai_messages"},
            "total_extra": {"$sum": "$extra_messages"},
        }}
    ]
    overage_res = await _db.usage.aggregate(overage_pipeline).to_list(1)
    overage_stats = overage_res[0] if overage_res else {"total_overage": 0, "total_ai_messages": 0, "total_extra": 0}

    # Leads totales y nuevos ultimos 30 dias
    total_leads = await _db.leads.count_documents({})
    new_leads_30d = await _db.leads.count_documents({"created_at": {"$gte": thirty_days_ago}})

    # Transacciones ultimos 30 dias
    revenue_pipeline = [
        {"$match": {
            "created_at": {"$gte": thirty_days_ago},
            "payment_status": "paid"
        }},
        {"$group": {
            "_id": "$type",
            "total_amount": {"$sum": "$amount"},
            "count": {"$sum": 1}
        }}
    ]
    revenue_raw = await _db.payment_transactions.aggregate(revenue_pipeline).to_list(20)
    revenue_30d = sum(r["total_amount"] for r in revenue_raw)
    revenue_by_type = [{"type": r["_id"], "amount": r["total_amount"], "count": r["count"]} for r in revenue_raw]

    # Churn: tenants cancelados ultimos 30 dias
    churned_30d = await _db.tenants.count_documents({
        "subscription_status": {"$in": ["cancelled", "cancelling"]},
        "updated_at": {"$gte": thirty_days_ago}
    })
    churn_rate = round((churned_30d / total_tenants * 100), 2) if total_tenants > 0 else 0.0

    return {
        "mrr": round(mrr, 2),
        "arr_estimated": round(mrr * 12, 2),
        "tenants": {
            "total": total_tenants,
            "active": active_tenants,
            "past_due": past_due,
            "cancelled": cancelled,
            "churned_last_30d": churned_30d,
            "churn_rate_pct": churn_rate,
        },
        "plans_distribution": plans_distribution,
        "usage": {
            "period": period_key,
            "total_ai_messages": overage_stats.get("total_ai_messages", 0),
            "total_overage_messages": overage_stats.get("total_overage", 0),
            "total_extra_messages": overage_stats.get("total_extra", 0),
        },
        "leads": {
            "total": total_leads,
            "new_last_30d": new_leads_30d,
        },
        "revenue_last_30d": {
            "total": round(revenue_30d, 2),
            "by_type": revenue_by_type,
        }
    }


@router.get("/superadmin/tenants/usage")
async def get_tenants_usage(current_user: User = Depends(get_current_user)):
    """Tabla de uso de cada tenant en el periodo actual"""
    _require_superadmin(current_user)

    now = datetime.now(timezone.utc)
    period_key = now.strftime("%Y-%m")

    tenants = await _db.tenants.find({}, {"_id": 0}).to_list(200)
    result = []
    for t in tenants:
        usage = await _db.usage.find_one(
            {"tenant_id": t["tenant_id"], "period": period_key},
            {"_id": 0}
        ) or {}
        leads_count = await _db.leads.count_documents({"tenant_id": t["tenant_id"]})
        result.append({
            "tenant_id": t["tenant_id"],
            "name": t.get("name", ""),
            "plan": t.get("subscription_plan", "unknown"),
            "status": t.get("subscription_status", "unknown"),
            "ai_messages": usage.get("ai_messages", 0),
            "max_ai_messages": t.get("max_ai_messages", 0),
            "overage_messages": usage.get("overage_messages", 0),
            "overage_billed": usage.get("overage_billed", False),
            "total_leads": leads_count,
        })
    return result


# ---------------- Feature Flags ----------------

@router.get("/superadmin/feature-flags/registry")
async def get_feature_flags_registry(current_user: User = Depends(get_current_user)):
    """Catálogo de features disponibles (para construir la UI del SuperAdmin Panel)."""
    _require_superadmin(current_user)
    return {
        "flags": [
            {"key": k, **v} for k, v in FEATURE_FLAGS.items()
        ]
    }


@router.get("/superadmin/tenants/{tenant_id}/features")
async def get_tenant_feature_flags(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
):
    """Estado efectivo de todas las features para un tenant (combina defaults + overrides)."""
    _require_superadmin(current_user)
    db = get_db()
    t = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0, "features": 1, "tenant_id": 1})
    if not t:
        raise HTTPException(404, "Tenant no encontrado")
    return {
        "tenant_id": tenant_id,
        "features": get_tenant_features(t),
        "raw_overrides": t.get("features") or {},
    }


class FeatureFlagUpdate(BaseModel):
    feature: str
    enabled: bool
    config: dict | None = None


@router.put("/superadmin/tenants/{tenant_id}/features")
async def update_tenant_feature_flag(
    tenant_id: str,
    body: FeatureFlagUpdate,
    current_user: User = Depends(get_current_user),
):
    """Activa/desactiva un feature flag para un tenant. Solo superadmin."""
    _require_superadmin(current_user)
    if body.feature not in FEATURE_FLAGS:
        raise HTTPException(400, f"Feature desconocida: {body.feature}")
    db = get_db()
    ok = await update_tenant_feature(db, tenant_id, body.feature, body.enabled, body.config)
    if not ok:
        raise HTTPException(404, "Tenant no encontrado")
    # Audit log
    await db.audit_log.insert_one({
        "tenant_id": tenant_id,
        "user_email": current_user.email,
        "action": "feature_flag_updated",
        "feature": body.feature,
        "enabled": body.enabled,
        "config": body.config or None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "tenant_id": tenant_id, "feature": body.feature, "enabled": body.enabled}



# ============================================================
# Demanda Insatisfecha (Iter32) — productos pedidos pero agotados
# ============================================================

@router.get("/superadmin/unmet-demand")
async def get_unmet_demand_global(
    current_user: User = Depends(get_current_user),
    limit: int = 20,
):
    """SuperAdmin: top productos con mayor demanda insatisfecha cross-tenant.

    Score = leads_pending × log(1+price). Devuelve top N por demanda.
    Útil para detectar qué productos reponer primero.
    """
    _require_superadmin(current_user)
    import math

    pipeline = [
        {"$match": {"notified_at": None}},
        {"$group": {
            "_id": {"tenant_id": "$tenant_id", "product_id": "$product_id"},
            "leads_count": {"$sum": 1},
            "product_name": {"$first": "$product_name"},
            "first_asked": {"$min": "$asked_at"},
            "last_asked": {"$max": "$asked_at"},
        }},
        {"$sort": {"leads_count": -1}},
        {"$limit": limit * 3},  # over-fetch para descartar productos ya repuestos
    ]
    rows = await _db.product_waitlist.aggregate(pipeline).to_list(limit * 3)

    # Enriquecer con datos del producto + tenant + filtrar los ya repuestos
    enriched = []
    for r in rows:
        tid = r["_id"]["tenant_id"]
        pid = r["_id"]["product_id"]
        prod = await _db.products.find_one(
            {"tenant_id": tid, "product_id": pid}, {"_id": 0},
        )
        # Solo incluir productos que SIGUEN agotados o ya no existen
        if prod:
            stock = prod.get("stock_quantity")
            still_out = (
                prod.get("active") is False
                or (stock is not None and stock <= 0)
            )
        else:
            still_out = True
        if not still_out:
            continue

        tenant = await _db.tenants.find_one(
            {"tenant_id": tid}, {"_id": 0, "business_name": 1, "owner_email": 1},
        )
        price = (prod or {}).get("price", 0) or 0
        urgency_score = round(r["leads_count"] * math.log(1 + max(price, 1)), 2)

        enriched.append({
            "tenant_id": tid,
            "tenant_name": (tenant or {}).get("business_name", ""),
            "tenant_email": (tenant or {}).get("owner_email", ""),
            "product_id": pid,
            "product_name": r.get("product_name") or (prod or {}).get("name", ""),
            "category": (prod or {}).get("category", ""),
            "price": price,
            "currency": (prod or {}).get("currency", "USD"),
            "leads_count": r["leads_count"],
            "first_asked": r.get("first_asked"),
            "last_asked": r.get("last_asked"),
            "urgency_score": urgency_score,
            "product_exists": prod is not None,
        })
        if len(enriched) >= limit:
            break

    # Ordenar por urgency_score
    enriched.sort(key=lambda x: x["urgency_score"], reverse=True)

    # Métricas agregadas
    total_pending = await _db.product_waitlist.count_documents({"notified_at": None})
    total_unique_products = len({(r["_id"]["tenant_id"], r["_id"]["product_id"]) for r in rows})

    return {
        "total_pending_leads": total_pending,
        "total_unique_products": total_unique_products,
        "top_products": enriched,
    }
