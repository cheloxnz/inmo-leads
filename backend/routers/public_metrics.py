"""Router de métricas públicas para landing/marketing (Shopify).

Endpoints sin auth que exponen datos agregados (anonimizados) de la plataforma
para mostrar en widgets de la landing: "$XXX detectados · YYY leads salvados
este mes". Cache TTL corto para no martillar Mongo.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict

from fastapi import APIRouter

from auth_routes import get_db

router = APIRouter(tags=["public-metrics"])
logger = logging.getLogger(__name__)
_db = get_db()

# Cache simple in-memory (suficiente: widget se llama ~c/minuto)
_cache: Dict[str, tuple] = {}
_CACHE_TTL_SEC = 300  # 5 minutos


def _cached(key: str):
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if datetime.now(timezone.utc).timestamp() > expires_at:
        return None
    return value


def _set_cache(key: str, value):
    expires_at = datetime.now(timezone.utc).timestamp() + _CACHE_TTL_SEC
    _cache[key] = (expires_at, value)


@router.get("/public/demand-detected")
async def get_demand_detected():
    """Métrica pública: USD en demanda detectada por InmoBot en los últimos 30 días.

    Usado en la landing de Shopify para mostrar proof-of-value orgánico:
    "InmoBot detectó $XXX en demanda insatisfecha este mes para sus clientes".

    Response:
    ```
    {
      "total_detected_usd": 42580,
      "unique_products_tracked": 127,
      "unique_tenants": 12,
      "days": 30,
      "cached": true
    }
    ```
    """
    cached = _cached("demand_detected")
    if cached is not None:
        cached["cached"] = True
        return cached

    days = 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    # Aggregation cross-tenant de waitlist × precio
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff_iso}, "notified_at": None}},
        {"$group": {
            "_id": {"tenant_id": "$tenant_id", "product_id": "$product_id"},
            "leads_count": {"$sum": 1},
        }},
    ]
    rows = await _db.product_waitlist.aggregate(pipeline).to_list(5000)
    total_usd = 0.0
    tenants = set()
    for r in rows:
        tid = r["_id"]["tenant_id"]
        pid = r["_id"]["product_id"]
        tenants.add(tid)
        prod = await _db.products.find_one(
            {"tenant_id": tid, "product_id": pid}, {"_id": 0, "price": 1},
        )
        price = (prod or {}).get("price", 0) or 0
        total_usd += r["leads_count"] * price

    result = {
        "total_detected_usd": round(total_usd, 2),
        "unique_products_tracked": len(rows),
        "unique_tenants": len(tenants),
        "days": days,
        "cached": False,
    }
    _set_cache("demand_detected", result)
    return result


@router.get("/public/platform-stats")
async def get_platform_stats():
    """Métrica pública agregada: tenants activos + total leads gestionados + WA messages.
    Útil para el hero de la landing: "InmoBot gestiona 12,800 leads en 47 negocios".
    """
    cached = _cached("platform_stats")
    if cached is not None:
        cached["cached"] = True
        return cached

    active_tenants = await _db.tenants.count_documents({
        "active": True,
        "subscription_status": {"$ne": "cancelled"},
    })
    total_leads = await _db.leads.count_documents({})
    # Mensajes IA procesados (hoy usage_log puede no estar; best-effort)
    try:
        ai_messages = await _db.usage_log.count_documents({"type": "ai_message"})
    except Exception:
        ai_messages = 0

    result = {
        "active_tenants": active_tenants,
        "total_leads": total_leads,
        "ai_messages_processed": ai_messages,
        "cached": False,
    }
    _set_cache("platform_stats", result)
    return result
