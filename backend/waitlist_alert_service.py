"""
Waitlist Threshold Alerts (Quick Win P1)
========================================

Cuando un producto de un tenant acumula >= WAITLIST_ADMIN_ALERT_THRESHOLD leads
en waitlist, dispara un email al SUPERADMIN_EMAIL para detectar oportunidades
de outreach comercial proactivo (señal temprana de upsell).

Idempotencia:
- Se registra cada alerta en `waitlist_admin_alerts` por (tenant_id, product_id).
- Respeta un cooldown (WAITLIST_ADMIN_ALERT_COOLDOWN_DAYS, default 30) antes
  de reenviar para el mismo producto.

Invocado desde `CatalogService.add_to_waitlist` (best-effort, nunca rompe el
flujo principal del bot si falla).
"""
import logging
import os
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


async def maybe_alert_superadmin(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    product_id: str,
    product_name: str = "",
) -> bool:
    """Si el producto cruzó el threshold y no hay alerta vigente, envía email.

    Retorna True si se disparó el email, False en cualquier otro caso.
    """
    threshold = _get_int_env("WAITLIST_ADMIN_ALERT_THRESHOLD", 20)
    cooldown_days = _get_int_env("WAITLIST_ADMIN_ALERT_COOLDOWN_DAYS", 30)
    target_email = os.environ.get("SUPERADMIN_EMAIL")
    if not target_email:
        return False

    # Contar leads NO notificados en el waitlist de este producto
    count = await db.product_waitlist.count_documents({
        "tenant_id": tenant_id,
        "product_id": product_id,
        "notified_at": None,
    })
    if count < threshold:
        return False

    # Cooldown check
    cutoff = (datetime.now(timezone.utc) - timedelta(days=cooldown_days)).isoformat()
    existing = await db.waitlist_admin_alerts.find_one(
        {
            "tenant_id": tenant_id,
            "product_id": product_id,
            "sent_at": {"$gte": cutoff},
        },
        {"_id": 0},
    )
    if existing:
        return False

    # Enriquecer con info del tenant
    tenant = await db.tenants.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "business_name": 1, "name": 1, "subscription_plan": 1, "contact_email": 1},
    ) or {}
    biz = tenant.get("business_name") or tenant.get("name") or tenant_id
    plan = tenant.get("subscription_plan", "")

    try:
        from email_service import EmailService
        svc = EmailService(db)
        ok = await svc.send_waitlist_threshold_alert(
            to_email=target_email,
            tenant_id=tenant_id,
            business_name=biz,
            plan=plan,
            product_name=product_name or product_id,
            product_id=product_id,
            leads_count=count,
            threshold=threshold,
        )
    except Exception as e:
        logger.warning(
            f"[waitlist_alert] send failed tenant={tenant_id} product={product_id}: {e}"
        )
        ok = False

    # Registrar alerta (incluso si falló el envío, para no spamear en cada insert)
    await db.waitlist_admin_alerts.insert_one({
        "tenant_id": tenant_id,
        "product_id": product_id,
        "product_name": product_name,
        "leads_count": count,
        "threshold": threshold,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "delivered": bool(ok),
    })
    if ok:
        logger.info(
            f"[waitlist_alert] sent tenant={tenant_id} product={product_id} "
            f"leads={count} threshold={threshold}"
        )
    return bool(ok)
