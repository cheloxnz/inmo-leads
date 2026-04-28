"""Router de metricas globales para SuperAdmin"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import get_current_user, get_db
from payment_service import SUBSCRIPTION_PLANS
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
