"""Router de ROI del tenant: muestra al cliente cuánto valor le generó InmoBot.

Métricas que expone:
- hot_leads_generated: leads marcados como "hot" en los últimos N días
- estimated_pipeline_usd: valor estimado del pipeline (leads × avg deal value)
- ai_messages_answered: mensajes IA que el bot respondió solo (tiempo salvado)
- hours_saved: AI messages × 2 min promedio / 60
- conversion_rate: hot / total_leads
- unmet_demand_usd: USD en productos agotados que leads pidieron (Iter32)
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends

from auth_routes import get_current_user, tenant_filter, get_db
from models import User

router = APIRouter(tags=["roi"])
logger = logging.getLogger(__name__)
_db = get_db()

# Configurables por tenant (defaults razonables para real estate)
DEFAULT_AVG_DEAL_USD = 500.0  # comisión/deal promedio si el tenant no lo define
MINUTES_PER_AI_MESSAGE = 2.0  # tiempo humano que el bot "salva" por mensaje


@router.get("/dashboard/roi")
async def get_tenant_roi(
    days: int = 30,
    current_user: User = Depends(get_current_user),
):
    """ROI del tenant: valor generado por InmoBot en los últimos N días.

    Response:
    ```
    {
      "days": 30,
      "hot_leads": 12,
      "warm_leads": 34,
      "total_leads": 87,
      "conversion_rate": 13.79,
      "estimated_pipeline_usd": 6000,
      "ai_messages_answered": 1432,
      "hours_saved": 47.7,
      "unmet_demand_usd": 3200,
      "avg_deal_usd": 500,
      "summary_sentence": "InmoBot te ahorró 47.7h y generó $6,000 en pipeline este mes."
    }
    ```
    """
    days = max(1, min(days, 365))
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    tf = tenant_filter(current_user)

    # Avg deal value (configurable por tenant)
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id},
        {"_id": 0, "avg_deal_value_usd": 1, "business_name": 1},
    )
    avg_deal = (tenant or {}).get("avg_deal_value_usd") or DEFAULT_AVG_DEAL_USD

    # Leads en el período
    hot = await _db.leads.count_documents({
        **tf, "status": "hot", "created_at": {"$gte": cutoff_iso},
    })
    warm = await _db.leads.count_documents({
        **tf, "status": "warm", "created_at": {"$gte": cutoff_iso},
    })
    total = await _db.leads.count_documents({
        **tf, "created_at": {"$gte": cutoff_iso},
    })

    conversion_rate = round((hot / total * 100) if total > 0 else 0, 2)
    # Pipeline estimado: hot × avg (más likely) + warm × avg × 0.3
    pipeline_usd = round(hot * avg_deal + warm * avg_deal * 0.3, 2)

    # AI messages (usage_log)
    try:
        ai_msgs = await _db.usage_log.count_documents({
            "tenant_id": current_user.tenant_id,
            "type": "ai_message",
            "created_at": {"$gte": cutoff_iso},
        })
    except Exception:
        ai_msgs = 0
    hours_saved = round(ai_msgs * MINUTES_PER_AI_MESSAGE / 60, 1)

    # Demanda insatisfecha USD (productos agotados × leads_waiting × precio)
    unmet_usd = 0.0
    try:
        pipeline_unmet = [
            {"$match": {
                "tenant_id": current_user.tenant_id,
                "notified_at": None,
            }},
            {"$group": {
                "_id": "$product_id",
                "leads_count": {"$sum": 1},
            }},
        ]
        rows = await _db.product_waitlist.aggregate(pipeline_unmet).to_list(500)
        for r in rows:
            prod = await _db.products.find_one(
                {"tenant_id": current_user.tenant_id, "product_id": r["_id"]},
                {"_id": 0, "price": 1},
            )
            price = (prod or {}).get("price", 0) or 0
            unmet_usd += r["leads_count"] * price
    except Exception as e:
        logger.warning(f"[roi] unmet_usd calc failed: {e}")

    summary = (
        f"InmoBot te ahorró {hours_saved}h y generó ${pipeline_usd:,.0f} "
        f"en pipeline en los últimos {days} días."
    )

    return {
        "days": days,
        "hot_leads": hot,
        "warm_leads": warm,
        "total_leads": total,
        "conversion_rate": conversion_rate,
        "estimated_pipeline_usd": pipeline_usd,
        "ai_messages_answered": ai_msgs,
        "hours_saved": hours_saved,
        "unmet_demand_usd": round(unmet_usd, 2),
        "avg_deal_usd": avg_deal,
        "summary_sentence": summary,
    }
