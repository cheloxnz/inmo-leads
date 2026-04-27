"""
Servicio de pagos con Stripe - Suscripciones SaaS multi-tenant
"""
import os
import logging
import stripe
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Planes SaaS con precios mensuales en USD
SUBSCRIPTION_PLANS = {
    "pro": {
        "name": "Pro",
        "price_monthly": 99,
        "description": "Para negocios en crecimiento",
        "max_leads": 2000,
        "max_agents": 10,
        "max_ai_messages": 2000,
        "features": [
            "1 numero de WhatsApp",
            "2,000 leads/mes",
            "2,000 conversaciones IA/mes",
            "10 usuarios",
            "Bot con IA (GPT-4) incluida",
            "Dashboard completo",
            "Metricas avanzadas",
            "Broadcast masivo",
            "Flujo personalizable",
            "Soporte prioritario",
            "6 Bonus exclusivos"
        ]
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 249,
        "description": "Para operaciones grandes",
        "max_leads": 10000,
        "max_agents": 50,
        "max_ai_messages": 10000,
        "features": [
            "Multiples numeros WhatsApp",
            "10,000 leads/mes",
            "10,000 conversaciones IA/mes",
            "50 usuarios",
            "Bot con IA (GPT-4) incluida",
            "Dashboard completo",
            "Metricas avanzadas",
            "Broadcast masivo",
            "Flujo personalizable",
            "API completa",
            "Soporte 24/7",
            "Onboarding personalizado",
            "Key propia de OpenAI (opcional)",
            "6 Bonus exclusivos"
        ]
    }
}


class PaymentService:
    def __init__(self, db):
        self.db = db
        self.api_key = os.getenv("STRIPE_API_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

        if self.api_key:
            stripe.api_key = self.api_key
            logger.info("Stripe configurado correctamente")
        else:
            logger.warning("STRIPE_API_KEY no configurada")

    def get_plans(self) -> Dict:
        return SUBSCRIPTION_PLANS

    async def create_subscription_checkout(
        self,
        plan_id: str,
        tenant_id: str,
        customer_email: str,
        origin_url: str
    ) -> Dict:
        """Crea sesion de checkout para suscripcion mensual"""
        if not self.api_key:
            raise ValueError("Stripe no esta configurado")

        if plan_id not in SUBSCRIPTION_PLANS:
            raise ValueError(f"Plan no valido: {plan_id}")

        plan = SUBSCRIPTION_PLANS[plan_id]

        try:
            success_url = f"{origin_url}/config?billing=success&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{origin_url}/config?billing=cancelled"

            # Find or create Stripe customer
            customer = await self._get_or_create_customer(customer_email, tenant_id)

            # Create price for recurring subscription
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f"SaaS - Plan {plan['name']}",
                            'description': plan['description'],
                        },
                        'unit_amount': int(plan['price_monthly'] * 100),
                        'recurring': {'interval': 'month'}
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                customer=customer.id,
                metadata={
                    "plan_id": plan_id,
                    "tenant_id": tenant_id,
                    "customer_email": customer_email
                }
            )

            # Save pending transaction
            await self.db.payment_transactions.insert_one({
                "session_id": session.id,
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "plan_name": plan["name"],
                "amount": plan["price_monthly"],
                "currency": "usd",
                "type": "subscription",
                "customer_email": customer_email,
                "payment_status": "pending",
                "created_at": datetime.utcnow().isoformat()
            })

            return {"checkout_url": session.url, "session_id": session.id}

        except Exception as e:
            logger.error(f"Error creando checkout subscription: {e}")
            raise

    async def _get_or_create_customer(self, email: str, tenant_id: str):
        """Busca o crea un customer en Stripe"""
        # Check if tenant has stripe_customer_id
        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id})
        if tenant and tenant.get("stripe_customer_id"):
            try:
                return stripe.Customer.retrieve(tenant["stripe_customer_id"])
            except Exception:
                pass

        # Search by email
        existing = stripe.Customer.list(email=email, limit=1)
        if existing.data:
            customer = existing.data[0]
        else:
            customer = stripe.Customer.create(
                email=email,
                metadata={"tenant_id": tenant_id}
            )

        # Save to tenant
        await self.db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"stripe_customer_id": customer.id}}
        )

        return customer

    async def handle_webhook(self, body: bytes, signature: str) -> Dict:
        """Maneja webhooks de Stripe"""
        try:
            if self.webhook_secret:
                event = stripe.Webhook.construct_event(body, signature, self.webhook_secret)
            else:
                import json
                event = stripe.Event.construct_from(json.loads(body), stripe.api_key)

            logger.info(f"Stripe webhook: {event.type}")

            if event.type == "checkout.session.completed":
                await self._handle_checkout_completed(event.data.object)
            elif event.type == "invoice.paid":
                await self._handle_invoice_paid(event.data.object)
            elif event.type == "invoice.payment_failed":
                await self._handle_payment_failed(event.data.object)
            elif event.type == "customer.subscription.updated":
                await self._handle_subscription_updated(event.data.object)
            elif event.type == "customer.subscription.deleted":
                await self._handle_subscription_deleted(event.data.object)

            return {"status": "success", "event_type": event.type}

        except stripe.error.SignatureVerificationError:
            logger.error("Firma webhook invalida")
            raise
        except Exception as e:
            logger.error(f"Error webhook: {e}")
            raise

    async def _handle_checkout_completed(self, session):
        """Checkout completado: activar suscripcion del tenant"""
        tenant_id = session.metadata.get("tenant_id", "")
        plan_id = session.metadata.get("plan_id", "basic")
        subscription_id = session.subscription

        if tenant_id and subscription_id:
            plan = SUBSCRIPTION_PLANS.get(plan_id, SUBSCRIPTION_PLANS["basic"])
            await self.db.tenants.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "subscription_status": "active",
                    "subscription_plan": plan_id,
                    "stripe_subscription_id": subscription_id,
                    "stripe_customer_id": session.customer,
                    "max_leads": plan.get("max_leads", 500),
                    "max_agents": plan.get("max_agents", 3),
                    "updated_at": datetime.utcnow().isoformat()
                }}
            )
            logger.info(f"Suscripcion activada: tenant={tenant_id} plan={plan_id}")

        # Update transaction
        await self.db.payment_transactions.update_one(
            {"session_id": session.id},
            {"$set": {
                "payment_status": "paid",
                "stripe_subscription_id": subscription_id,
                "paid_at": datetime.utcnow().isoformat()
            }}
        )

    async def _handle_invoice_paid(self, invoice):
        """Factura pagada: registrar pago recurrente"""
        subscription_id = invoice.subscription
        if not subscription_id:
            return

        tenant = await self.db.tenants.find_one({"stripe_subscription_id": subscription_id})
        if tenant:
            await self.db.payment_transactions.insert_one({
                "tenant_id": tenant["tenant_id"],
                "type": "recurring",
                "amount": invoice.amount_paid / 100,
                "currency": invoice.currency,
                "payment_status": "paid",
                "stripe_invoice_id": invoice.id,
                "stripe_subscription_id": subscription_id,
                "created_at": datetime.utcnow().isoformat()
            })
            logger.info(f"Pago recurrente registrado: tenant={tenant['tenant_id']}")

    async def _handle_payment_failed(self, invoice):
        """Pago fallido: marcar tenant como suspendido"""
        subscription_id = invoice.subscription
        if not subscription_id:
            return

        tenant = await self.db.tenants.find_one({"stripe_subscription_id": subscription_id})
        if tenant:
            await self.db.tenants.update_one(
                {"tenant_id": tenant["tenant_id"]},
                {"$set": {
                    "subscription_status": "past_due",
                    "updated_at": datetime.utcnow().isoformat()
                }}
            )
            logger.warning(f"Pago fallido: tenant={tenant['tenant_id']}")

    async def _handle_subscription_updated(self, subscription):
        """Suscripcion actualizada (upgrade/downgrade)"""
        tenant = await self.db.tenants.find_one({"stripe_subscription_id": subscription.id})
        if not tenant:
            return

        status_map = {
            "active": "active",
            "past_due": "past_due",
            "canceled": "cancelled",
            "unpaid": "suspended",
            "trialing": "trial"
        }

        new_status = status_map.get(subscription.status, subscription.status)
        await self.db.tenants.update_one(
            {"tenant_id": tenant["tenant_id"]},
            {"$set": {
                "subscription_status": new_status,
                "updated_at": datetime.utcnow().isoformat()
            }}
        )

    async def _handle_subscription_deleted(self, subscription):
        """Suscripcion cancelada"""
        tenant = await self.db.tenants.find_one({"stripe_subscription_id": subscription.id})
        if not tenant:
            return

        await self.db.tenants.update_one(
            {"tenant_id": tenant["tenant_id"]},
            {"$set": {
                "subscription_status": "cancelled",
                "updated_at": datetime.utcnow().isoformat()
            }}
        )
        logger.info(f"Suscripcion cancelada: tenant={tenant['tenant_id']}")

    async def cancel_subscription(self, tenant_id: str) -> Dict:
        """Cancela suscripcion de un tenant"""
        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id})
        if not tenant or not tenant.get("stripe_subscription_id"):
            return {"status": "error", "message": "No hay suscripcion activa"}

        try:
            # Cancel at period end (no immediate)
            stripe.Subscription.modify(
                tenant["stripe_subscription_id"],
                cancel_at_period_end=True
            )

            await self.db.tenants.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "subscription_status": "cancelling",
                    "updated_at": datetime.utcnow().isoformat()
                }}
            )

            return {"status": "ok", "message": "Suscripcion se cancelara al final del periodo"}

        except Exception as e:
            logger.error(f"Error cancelando suscripcion: {e}")
            return {"status": "error", "message": str(e)}

    async def get_billing_info(self, tenant_id: str) -> Dict:
        """Obtiene info de billing de un tenant"""
        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant:
            return {"error": "Tenant no encontrado"}

        plan_id = tenant.get("subscription_plan", "basic")
        plan = SUBSCRIPTION_PLANS.get(plan_id, SUBSCRIPTION_PLANS["basic"])

        # Get recent transactions
        transactions = await self.db.payment_transactions.find(
            {"tenant_id": tenant_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)

        # Get subscription details from Stripe if available
        next_billing = None
        if tenant.get("stripe_subscription_id") and self.api_key:
            try:
                sub = stripe.Subscription.retrieve(tenant["stripe_subscription_id"])
                next_billing = datetime.fromtimestamp(sub.current_period_end).isoformat()
            except Exception:
                pass

        return {
            "plan": plan_id,
            "plan_name": plan["name"],
            "price_monthly": plan["price_monthly"],
            "subscription_status": tenant.get("subscription_status", "active"),
            "next_billing_date": next_billing,
            "transactions": transactions,
            "stripe_customer_id": tenant.get("stripe_customer_id"),
            "max_leads": tenant.get("max_leads", plan.get("max_leads", 500)),
            "max_agents": tenant.get("max_agents", plan.get("max_agents", 3))
        }

    async def get_all_transactions(self, limit: int = 50) -> list:
        """SuperAdmin: historial de transacciones global"""
        transactions = await self.db.payment_transactions.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return transactions
