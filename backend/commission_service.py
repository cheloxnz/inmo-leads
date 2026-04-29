"""Servicio de comisiones por referidos.

Reglas (decididas con el usuario):
- $5/mes de descuento por cada referido convertido y pagando
- Duración: 12 meses por cada referido (despues expira)
- Cap: 100% del precio del plan del referrer (no genera deuda a InmoBot)
- Activacion: cuando el referido paga su PRIMERA factura
- Aplicacion: Stripe Invoice Item con monto negativo en la proxima factura del referrer

Anti-fraude:
- Mismo email exacto entre referrer y referido
- Mismo dominio de email
- Misma IP en ultimas 24h
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Configuracion (constantes simples por ahora; se podrian leer de env si crecen)
COMMISSION_AMOUNT_USD = 5.0
COMMISSION_DURATION_DAYS = 365  # 12 meses
ANTI_FRAUD_IP_WINDOW_HOURS = 24


class CommissionStatus:
    PENDING = "pending"      # Referido se registró, no pagó aún
    ACTIVE = "active"        # Referido ya pagó al menos 1 vez, comisión activa
    EXPIRED = "expired"      # Cumplió 365 días
    CANCELLED = "cancelled"  # Referido canceló su suscripción


# ---------------- Anti-fraude ----------------

def _email_domain(email: str) -> str:
    return email.split("@", 1)[1].lower() if "@" in email else ""


async def is_self_referral(
    db: AsyncIOMotorDatabase,
    ref_tenant_id: str,
    new_email: str,
    new_ip: Optional[str],
) -> tuple[bool, str]:
    """Detecta auto-referido. Devuelve (is_fraud, reason).

    Triggers:
      1. Email exacto del referrer matchea
      2. Dominio de email matchea (si el referrer tiene dominio propio, no gmail)
      3. IP del signup matchea ultimas IPs del referrer (24h)
    """
    if not ref_tenant_id or not new_email:
        return False, ""

    new_email = new_email.lower().strip()

    # Buscar agents del referrer
    agents = await db.agents.find(
        {"tenant_id": ref_tenant_id}, {"_id": 0, "email": 1}
    ).to_list(length=20)

    for ag in agents:
        ag_email = (ag.get("email") or "").lower().strip()
        if not ag_email:
            continue
        if ag_email == new_email:
            return True, "same_email_as_referrer"

        # Dominio match (solo si NO es un free provider tipo gmail/outlook)
        ref_domain = _email_domain(ag_email)
        new_domain = _email_domain(new_email)
        FREE_PROVIDERS = {
            "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
            "icloud.com", "live.com", "aol.com", "protonmail.com",
        }
        if (ref_domain and new_domain
                and ref_domain == new_domain
                and ref_domain not in FREE_PROVIDERS):
            return True, "same_corporate_domain"

    # IP check (ultimas 24h en audit_log)
    if new_ip:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ANTI_FRAUD_IP_WINDOW_HOURS)
        recent = await db.audit_log.find_one({
            "tenant_id": ref_tenant_id,
            "ip": new_ip,
            "timestamp": {"$gte": cutoff.isoformat()},
        }, {"_id": 1})
        if recent:
            return True, "same_ip_recently"

    return False, ""


# ---------------- Lifecycle de Comisiones ----------------

async def create_commission_on_first_payment(
    db: AsyncIOMotorDatabase,
    referred_tenant_id: str,
) -> Optional[dict]:
    """Llamar cuando el referido paga su 1ra factura.
    Si tiene referrer y NO existe ya una commission para este referido, la crea.
    Retorna el doc creado o None.
    """
    referred = await db.tenants.find_one(
        {"tenant_id": referred_tenant_id},
        {"_id": 0, "tenant_id": 1, "referred_by": 1, "referred_via_celebration": 1},
    )
    if not referred or not referred.get("referred_by"):
        return None
    referrer_id = referred["referred_by"]

    # Idempotencia: 1 commission por par (referrer, referred)
    existing = await db.commissions.find_one(
        {"referrer_tenant_id": referrer_id, "referred_tenant_id": referred_tenant_id},
        {"_id": 1, "status": 1},
    )
    if existing:
        # Si estaba pending, activarla
        if existing.get("status") == CommissionStatus.PENDING:
            await db.commissions.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "status": CommissionStatus.ACTIVE,
                    "activated_at": datetime.now(timezone.utc),
                }},
            )
            logger.info(f"Commission re-activada: {referrer_id} <- {referred_tenant_id}")
        return None

    now = datetime.now(timezone.utc)
    doc = {
        "commission_id": str(uuid.uuid4()),
        "referrer_tenant_id": referrer_id,
        "referred_tenant_id": referred_tenant_id,
        "referred_via_celebration": referred.get("referred_via_celebration"),
        "amount_per_month_usd": COMMISSION_AMOUNT_USD,
        "status": CommissionStatus.ACTIVE,
        "created_at": now,
        "activated_at": now,
        "expires_at": now + timedelta(days=COMMISSION_DURATION_DAYS),
        "total_credited_usd": 0.0,
        "applied_invoices": [],  # [{invoice_id, amount, applied_at}]
    }
    await db.commissions.insert_one(doc)
    logger.info(f"Commission creada: {referrer_id} <- {referred_tenant_id}, expires {doc['expires_at']}")
    return doc


async def calculate_active_credit_for_tenant(
    db: AsyncIOMotorDatabase,
    referrer_tenant_id: str,
) -> dict:
    """Suma todas las commissions ACTIVE no expiradas del referrer.
    Devuelve {amount_usd, capped_amount_usd, active_count, plan_price, breakdown[]}.
    """
    now = datetime.now(timezone.utc)
    # Auto-expirar las que ya pasaron expires_at
    await db.commissions.update_many(
        {
            "referrer_tenant_id": referrer_tenant_id,
            "status": CommissionStatus.ACTIVE,
            "expires_at": {"$lt": now},
        },
        {"$set": {"status": CommissionStatus.EXPIRED}},
    )

    cursor = db.commissions.find(
        {"referrer_tenant_id": referrer_tenant_id, "status": CommissionStatus.ACTIVE},
        {"_id": 0},
    )
    actives = await cursor.to_list(length=500)
    raw_amount = sum(c.get("amount_per_month_usd", 0) for c in actives)

    # Cap al precio del plan del referrer
    from payment_service import SUBSCRIPTION_PLANS
    referrer = await db.tenants.find_one(
        {"tenant_id": referrer_tenant_id},
        {"_id": 0, "subscription_plan": 1},
    ) or {}
    plan_id = referrer.get("subscription_plan") or "pro"
    plan = SUBSCRIPTION_PLANS.get(plan_id) or SUBSCRIPTION_PLANS.get("pro") or {}
    plan_price = float(plan.get("price_monthly") or 0)

    capped = min(raw_amount, plan_price) if plan_price > 0 else raw_amount

    return {
        "amount_usd": raw_amount,
        "capped_amount_usd": capped,
        "active_count": len(actives),
        "plan_price_usd": plan_price,
        "plan_id": plan_id,
        "is_capped": raw_amount > plan_price > 0,
        "breakdown": [
            {
                "commission_id": c.get("commission_id"),
                "referred_tenant_id": c.get("referred_tenant_id"),
                "amount_per_month_usd": c.get("amount_per_month_usd"),
                "expires_at": (
                    c["expires_at"].isoformat()
                    if isinstance(c.get("expires_at"), datetime)
                    else c.get("expires_at")
                ),
            }
            for c in actives
        ],
    }


async def cancel_commissions_for_referred(
    db: AsyncIOMotorDatabase,
    referred_tenant_id: str,
):
    """Cuando el referido cancela su suscripcion, marcar sus commissions como cancelled."""
    res = await db.commissions.update_many(
        {
            "referred_tenant_id": referred_tenant_id,
            "status": {"$in": [CommissionStatus.ACTIVE, CommissionStatus.PENDING]},
        },
        {"$set": {
            "status": CommissionStatus.CANCELLED,
            "cancelled_at": datetime.now(timezone.utc),
        }},
    )
    if res.modified_count:
        logger.info(f"Comisiones canceladas para referred={referred_tenant_id}: {res.modified_count}")


async def expire_due_commissions(db: AsyncIOMotorDatabase) -> int:
    """Cron job: marcar como EXPIRED las commissions que cumplieron 365d.
    Retorna count de modificados."""
    now = datetime.now(timezone.utc)
    res = await db.commissions.update_many(
        {"status": CommissionStatus.ACTIVE, "expires_at": {"$lt": now}},
        {"$set": {"status": CommissionStatus.EXPIRED}},
    )
    if res.modified_count:
        logger.info(f"Comisiones expiradas: {res.modified_count}")
    return res.modified_count
