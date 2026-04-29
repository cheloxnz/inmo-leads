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
    # Trigger email al referrer (best-effort, no bloquea si falla)
    try:
        await _notify_referrer_new_commission(db, referrer_id, referred_tenant_id)
    except Exception as e:
        logger.warning(f"No se pudo notificar al referrer {referrer_id}: {e}")
    return doc


async def _notify_referrer_new_commission(
    db: AsyncIOMotorDatabase,
    referrer_tenant_id: str,
    referred_tenant_id: str,
):
    """Envía email al admin del referrer cuando entra una nueva comisión activa."""
    referrer = await db.tenants.find_one(
        {"tenant_id": referrer_tenant_id},
        {"_id": 0, "tenant_id": 1, "business_name": 1, "name": 1},
    )
    referred = await db.tenants.find_one(
        {"tenant_id": referred_tenant_id},
        {"_id": 0, "business_name": 1, "name": 1},
    )
    if not referrer:
        return

    # Email del admin del tenant referrer
    agent = await db.agents.find_one(
        {"tenant_id": referrer_tenant_id, "role": "admin", "active": True},
        {"_id": 0, "email": 1},
    )
    if not agent or not agent.get("email"):
        return

    credit = await calculate_active_credit_for_tenant(db, referrer_tenant_id)

    from email_service import EmailService
    es = EmailService(db)
    if not es.smtp_username or not es.smtp_password:
        logger.info("SMTP no configurado, skip email new_referral_commission")
        return

    await es.send_new_referral_commission(
        to_email=agent["email"],
        referrer_business_name=(referrer.get("business_name") or referrer.get("name") or "—"),
        referred_business_name=(referred.get("business_name") or referred.get("name") or "Cliente referido"),
        amount_per_month_usd=COMMISSION_AMOUNT_USD,
        active_count=credit.get("active_count", 0),
        active_credit_capped_usd=credit.get("capped_amount_usd", 0),
        plan_price_usd=credit.get("plan_price_usd", 0),
        is_capped=bool(credit.get("is_capped")),
    )


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


# ---------------- Stripe Promotion Codes (attribution) ----------------

# Coupon global compartido (5% off primer mes para el referido). Lazy created en Stripe.
GLOBAL_REFERRAL_COUPON_ID = "INMOBOT_REFERRAL_5_PERCENT_OFF_FIRST_MONTH"


def _generate_referral_code(tenant_id: str) -> str:
    """Genera un código legible para el tenant: prefijo (slugified) + 6 chars random.
    Ej: tenant_id='demo-inmobiliaria' -> 'DEMO-XYZ123'.
    """
    import re
    import secrets
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin chars confusos (0/O, 1/I)
    prefix = re.sub(r"[^A-Za-z0-9]", "", tenant_id).upper()[:6] or "REF"
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"{prefix}-{suffix}"


async def get_or_create_referral_code(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    create_in_stripe: bool = True,
) -> dict:
    """Obtiene (o crea idempotentemente) el referral_code del tenant.
    Si Stripe está configurado y create_in_stripe=True, también crea el promotion_code en Stripe.
    Devuelve {code, stripe_promotion_code_id, stripe_enabled}.
    """
    tenant = await db.tenants.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "tenant_id": 1, "referral_code": 1,
         "stripe_promotion_code_id": 1, "business_name": 1, "name": 1},
    )
    if not tenant:
        return {"code": None, "stripe_promotion_code_id": None, "stripe_enabled": False, "error": "tenant_not_found"}

    code = tenant.get("referral_code")
    if not code:
        # Generar y persistir (con retry por colisión, aunque la prob es minúscula)
        for _ in range(5):
            candidate = _generate_referral_code(tenant_id)
            existing = await db.tenants.find_one(
                {"referral_code": candidate}, {"_id": 1}
            )
            if not existing:
                code = candidate
                break
        if not code:
            return {"code": None, "stripe_promotion_code_id": None, "stripe_enabled": False, "error": "could_not_generate"}
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"referral_code": code}},
        )
        # Index unique se asegura en startup; si no existe aún, igualmente la búsqueda anterior previene colisiones
        logger.info(f"Referral code generado: {tenant_id} -> {code}")

    promo_id = tenant.get("stripe_promotion_code_id")
    stripe_enabled = False
    stripe_error = None
    if create_in_stripe:
        try:
            import os
            import stripe
            api_key = os.getenv("STRIPE_API_KEY")
            if api_key:
                stripe.api_key = api_key
                if not promo_id:
                    # Lazy create del coupon global (idempotente por id)
                    try:
                        stripe.Coupon.retrieve(GLOBAL_REFERRAL_COUPON_ID)
                    except stripe.error.InvalidRequestError:
                        stripe.Coupon.create(
                            id=GLOBAL_REFERRAL_COUPON_ID,
                            percent_off=5,
                            duration="once",
                            name="InmoBot Referral - 5% off first month",
                        )
                    # Crear PromotionCode mapeado al tenant via metadata
                    promo = stripe.PromotionCode.create(
                        coupon=GLOBAL_REFERRAL_COUPON_ID,
                        code=code,
                        max_redemptions=None,  # ilimitado
                        metadata={"referrer_tenant_id": tenant_id},
                    )
                    promo_id = promo.id
                    await db.tenants.update_one(
                        {"tenant_id": tenant_id},
                        {"$set": {"stripe_promotion_code_id": promo_id}},
                    )
                    logger.info(f"Stripe PromotionCode creado: {code} -> {promo_id}")
                stripe_enabled = True
        except Exception as e:
            stripe_error = str(e)
            logger.warning(f"Stripe promo code skip para {tenant_id}: {e}")

    out = {
        "code": code,
        "stripe_promotion_code_id": promo_id,
        "stripe_enabled": stripe_enabled,
    }
    if stripe_error:
        out["stripe_error"] = stripe_error
    return out


async def find_referrer_by_promo_code(
    db: AsyncIOMotorDatabase,
    code: str,
) -> str | None:
    """Devuelve el tenant_id del referrer que es dueño del referral_code, o None."""
    if not code:
        return None
    tenant = await db.tenants.find_one(
        {"referral_code": code.upper().strip()},
        {"_id": 0, "tenant_id": 1, "active": 1},
    )
    if not tenant or not tenant.get("active"):
        return None
    return tenant["tenant_id"]

