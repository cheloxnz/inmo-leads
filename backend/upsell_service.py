"""
Upsell Service (Iter32d)
========================

Detecta tenants en plan Pro con alta demanda insatisfecha y dispara emails
de upsell automático para movérselos a Enterprise.

Trigger principal: leads en waitlist (`product_waitlist.notified_at=null`)
filtrados por productos que SIGUEN agotados. El "valor en juego" se calcula
sumando precio × leads_count por producto.

Idempotencia: registramos cada envío en `upsell_events` y NO mandamos a un
mismo tenant más de 1 vez cada `cooldown_days` (default 30) por el mismo
trigger.

Configuración (env override):
- UPSELL_THRESHOLD_LEADS (default 50): mínimo de leads esperando para gatillar.
- UPSELL_THRESHOLD_VALUE_USD (default 1500): mínimo de "demanda en juego" en USD.
- UPSELL_COOLDOWN_DAYS (default 30): días mínimos entre envíos por tenant.
- UPSELL_FORCE=1: fuerza disparo aunque no haya cumplido threshold (testing).
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Plan que tiene sentido upsellear (Pro → Enterprise)
ELIGIBLE_PLANS = {"pro"}
TARGET_PLAN = "enterprise"


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


async def calculate_unmet_demand_for_tenant(
    db: AsyncIOMotorDatabase, tenant_id: str,
) -> Dict:
    """Calcula leads esperando + USD en juego para un tenant.

    Retorna dict con `leads_count`, `value_usd`, `top_products` (lista de top-5
    {name, leads_count, price}).
    """
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "notified_at": None}},
        {"$group": {
            "_id": "$product_id",
            "leads_count": {"$sum": 1},
            "product_name": {"$first": "$product_name"},
        }},
        {"$sort": {"leads_count": -1}},
        {"$limit": 50},
    ]
    rows = await db.product_waitlist.aggregate(pipeline).to_list(50)
    leads_total = 0
    value_total = 0.0
    top_products: List[Dict] = []
    for r in rows:
        prod = await db.products.find_one(
            {"tenant_id": tenant_id, "product_id": r["_id"]}, {"_id": 0},
        )
        # Solo contar productos QUE SIGUEN agotados (consistente con dashboard)
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
        price = (prod or {}).get("price", 0) or 0
        leads_total += r["leads_count"]
        value_total += r["leads_count"] * price
        if len(top_products) < 5:
            top_products.append({
                "name": r.get("product_name") or (prod or {}).get("name", ""),
                "leads_count": r["leads_count"],
                "price": price,
            })
    return {
        "leads_count": leads_total,
        "value_usd": round(value_total, 2),
        "top_products": top_products,
    }


async def check_and_send_upsells(
    db: AsyncIOMotorDatabase,
    email_service,
) -> Dict:
    """Recorre todos los tenants Pro activos y dispara upsell si:
    - leads esperando >= UPSELL_THRESHOLD_LEADS
    - O valor en juego >= UPSELL_THRESHOLD_VALUE_USD
    - Y NO se le mandó upsell en los últimos UPSELL_COOLDOWN_DAYS días.

    Retorna `{"evaluated": N, "sent": M, "skipped_cooldown": K}`.
    """
    threshold_leads = _get_int_env("UPSELL_THRESHOLD_LEADS", 50)
    threshold_value = _get_int_env("UPSELL_THRESHOLD_VALUE_USD", 1500)
    cooldown_days = _get_int_env("UPSELL_COOLDOWN_DAYS", 30)
    force = os.environ.get("UPSELL_FORCE") == "1"

    cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
    cutoff_iso = cutoff.isoformat()

    evaluated = 0
    sent = 0
    skipped_cooldown = 0

    cursor = db.tenants.find(
        {
            "active": True,
            "subscription_plan": {"$in": list(ELIGIBLE_PLANS)},
            "subscription_status": {"$ne": "cancelled"},
        },
        {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1},
    )
    async for t in cursor:
        evaluated += 1
        tid = t["tenant_id"]
        biz = t.get("business_name") or t.get("name") or tid

        # Cooldown check
        last = await db.upsell_events.find_one(
            {
                "tenant_id": tid,
                "trigger": "unmet_demand",
                "sent_at": {"$gte": cutoff_iso},
            },
            {"_id": 0},
        )
        if last and not force:
            skipped_cooldown += 1
            continue

        # Calcular demanda
        demand = await calculate_unmet_demand_for_tenant(db, tid)
        meets_threshold = (
            demand["leads_count"] >= threshold_leads
            or demand["value_usd"] >= threshold_value
        )
        if not (meets_threshold or force):
            continue

        # Conseguir email del admin
        agent = await db.agents.find_one(
            {"tenant_id": tid, "role": "admin", "active": True},
            {"_id": 0, "email": 1},
        )
        if not agent or not agent.get("email"):
            continue

        # Enviar email
        try:
            ok = await email_service.send_upsell_unmet_demand(
                to_email=agent["email"],
                business_name=biz,
                demand=demand,
            )
        except Exception as e:
            logger.warning(f"[upsell] send failed tenant={tid}: {e}")
            ok = False

        # Registrar evento (incluso si falló el envío para no spamear)
        await db.upsell_events.insert_one({
            "tenant_id": tid,
            "trigger": "unmet_demand",
            "to_email": agent["email"],
            "leads_count": demand["leads_count"],
            "value_usd": demand["value_usd"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "delivered": bool(ok),
        })
        if ok:
            sent += 1
            logger.info(
                f"[upsell] sent tenant={tid} leads={demand['leads_count']} "
                f"value=${demand['value_usd']}"
            )

    return {
        "evaluated": evaluated,
        "sent": sent,
        "skipped_cooldown": skipped_cooldown,
    }


async def mark_upsell_conversions(
    db: AsyncIOMotorDatabase,
    lookback_days: int = 90,
) -> int:
    """Marca eventos de upsell como `converted=true` si el tenant upgradeó
    a Enterprise DESPUÉS de recibir el upsell.

    Idempotente: solo procesa eventos con `converted` no seteado o en `false`.
    Retorna cantidad de eventos actualizados a converted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    cutoff_iso = cutoff.isoformat()

    cursor = db.upsell_events.find(
        {
            "sent_at": {"$gte": cutoff_iso},
            "delivered": True,
            "$or": [{"converted": {"$exists": False}}, {"converted": False}],
        },
        {"_id": 0},
    )
    updated = 0
    async for evt in cursor:
        tid = evt["tenant_id"]
        tenant = await db.tenants.find_one(
            {"tenant_id": tid},
            {"_id": 0, "subscription_plan": 1, "subscription_updated_at": 1, "subscription_started_at": 1},
        )
        if not tenant:
            continue
        if tenant.get("subscription_plan") != TARGET_PLAN:
            continue
        # Conversión cuenta solo si el upgrade fue DESPUÉS del envío
        plan_change_at = (
            tenant.get("subscription_updated_at")
            or tenant.get("subscription_started_at")
        )
        if plan_change_at and plan_change_at < evt["sent_at"]:
            continue
        await db.upsell_events.update_one(
            {
                "tenant_id": tid,
                "sent_at": evt["sent_at"],
            },
            {
                "$set": {
                    "converted": True,
                    "converted_at": plan_change_at or datetime.now(timezone.utc).isoformat(),
                    "conversion_plan": TARGET_PLAN,
                },
            },
        )
        updated += 1
    return updated


async def get_upsell_stats(db: AsyncIOMotorDatabase, days: int = 90) -> Dict:
    """Stats agregadas del upsell para dashboard."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    match = {"sent_at": {"$gte": cutoff_iso}}
    total = await db.upsell_events.count_documents(match)
    delivered = await db.upsell_events.count_documents({**match, "delivered": True})
    converted = await db.upsell_events.count_documents({**match, "converted": True})
    total_value = 0.0
    async for e in db.upsell_events.find(match, {"_id": 0, "value_usd": 1, "converted": 1}):
        if e.get("converted"):
            total_value += float(e.get("value_usd", 0) or 0)
    return {
        "days": days,
        "total_sent": total,
        "delivered": delivered,
        "converted": converted,
        "conversion_rate": round((converted / delivered * 100) if delivered else 0.0, 2),
        "converted_value_usd": round(total_value, 2),
    }
