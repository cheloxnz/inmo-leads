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
                allow_promotion_codes=True,
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
            elif event.type == "invoice.upcoming":
                await self._handle_invoice_upcoming(event.data.object)
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

    async def _attribute_via_promo_code(self, session, tenant_id: str):
        """Si el checkout incluyó un promotion_code, atribuir al referrer.
        Se llama antes de _handle_checkout_completed para que la atribución
        quede grabada antes de cualquier facturación recurrente.
        """
        if not tenant_id:
            return

        # Si el tenant ya tiene referred_by, NO sobrescribir (atribución congelada)
        existing = await self.db.tenants.find_one(
            {"tenant_id": tenant_id, "referred_by": {"$exists": True, "$ne": None}},
            {"_id": 1},
        )
        if existing:
            return

        # 1) Buscar promotion_code en el session
        promo_code_str = None
        try:
            # Stripe expone el código aplicado en session.total_details.breakdown.discounts[].discount.promotion_code
            # o como session.discounts si fue creado con discounts en checkout.
            if hasattr(session, "total_details") and session.total_details:
                breakdown = getattr(session.total_details, "breakdown", None)
                if breakdown and getattr(breakdown, "discounts", None):
                    for d in breakdown.discounts:
                        promo_id = getattr(getattr(d, "discount", None), "promotion_code", None)
                        if promo_id:
                            try:
                                promo = stripe.PromotionCode.retrieve(promo_id)
                                promo_code_str = getattr(promo, "code", None)
                                # También podemos leer directo metadata.referrer_tenant_id
                                meta = getattr(promo, "metadata", None) or {}
                                ref_meta = meta.get("referrer_tenant_id") if isinstance(meta, dict) else getattr(meta, "referrer_tenant_id", None)
                                if ref_meta:
                                    await self.db.tenants.update_one(
                                        {"tenant_id": tenant_id},
                                        {"$set": {"referred_by": ref_meta,
                                                  "referred_via_promo_code": promo_code_str}},
                                    )
                                    logger.info(f"Attribution via promo metadata: {tenant_id} <- {ref_meta} ({promo_code_str})")
                                    return
                            except Exception as e:
                                logger.debug(f"No se pudo retrieve promo {promo_id}: {e}")
                                continue
        except Exception as e:
            logger.debug(f"Parse session.total_details falló: {e}")

        # 2) Fallback: buscar el código en nuestra DB
        if promo_code_str:
            from commission_service import find_referrer_by_promo_code
            ref_tid = await find_referrer_by_promo_code(self.db, promo_code_str)
            if ref_tid and ref_tid != tenant_id:
                await self.db.tenants.update_one(
                    {"tenant_id": tenant_id},
                    {"$set": {"referred_by": ref_tid,
                              "referred_via_promo_code": promo_code_str}},
                )
                logger.info(f"Attribution via DB lookup: {tenant_id} <- {ref_tid} ({promo_code_str})")

    async def _handle_checkout_completed(self, session):
        """Checkout completado: activar suscripcion del tenant"""
        tenant_id = session.metadata.get("tenant_id", "")
        plan_id = session.metadata.get("plan_id", "pro")
        subscription_id = session.subscription

        # Detectar promotion_code aplicado para attribution via Stripe
        try:
            await self._attribute_via_promo_code(session, tenant_id)
        except Exception as e:
            logger.warning(f"Attribution via promo code falló para {tenant_id}: {e}")

        if tenant_id and subscription_id:
            plan = SUBSCRIPTION_PLANS.get(plan_id) or SUBSCRIPTION_PLANS.get("pro")
            now_iso = datetime.utcnow().isoformat()
            await self.db.tenants.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "subscription_status": "active",
                    "subscription_plan": plan_id,
                    "subscription_updated_at": now_iso,
                    "stripe_subscription_id": subscription_id,
                    "stripe_customer_id": session.customer,
                    "max_leads": plan.get("max_leads", 500),
                    "max_agents": plan.get("max_agents", 3),
                    "updated_at": now_iso
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
        """Factura pagada: registrar pago recurrente + activar comisión si aplica"""
        subscription_id = invoice.subscription
        if not subscription_id:
            return

        tenant = await self.db.tenants.find_one({"stripe_subscription_id": subscription_id})
        if tenant:
            # Detectar si es la PRIMERA factura paga del tenant
            prior_paid = await self.db.payment_transactions.count_documents({
                "tenant_id": tenant["tenant_id"],
                "type": "recurring",
                "payment_status": "paid",
            })
            is_first_paid = prior_paid == 0

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

            # Activar comisión si es la primera factura del referido
            if is_first_paid and tenant.get("referred_by"):
                try:
                    from commission_service import create_commission_on_first_payment
                    await create_commission_on_first_payment(self.db, tenant["tenant_id"])
                except Exception as e:
                    logger.warning(f"No se pudo crear commission: {e}")

            # Registrar el descuento aplicado (si la invoice incluyó nuestros line items negativos)
            try:
                await self._record_applied_commission(tenant["tenant_id"], invoice)
            except Exception as e:
                logger.warning(f"No se pudo registrar applied commission: {e}")

    async def _handle_invoice_upcoming(self, invoice):
        """Factura proxima (~1h antes del cobro). Inyectar credito de comisiones del referrer."""
        subscription_id = invoice.subscription
        customer_id = invoice.customer
        if not subscription_id or not customer_id:
            return

        tenant = await self.db.tenants.find_one(
            {"stripe_subscription_id": subscription_id},
            {"_id": 0, "tenant_id": 1, "stripe_customer_id": 1},
        )
        if not tenant:
            return

        try:
            from commission_service import calculate_active_credit_for_tenant
            credit = await calculate_active_credit_for_tenant(self.db, tenant["tenant_id"])
            amount = credit.get("capped_amount_usd", 0)
            if amount <= 0:
                return

            # Crear invoice item negativo (descuento) sobre la proxima factura
            stripe.InvoiceItem.create(
                customer=customer_id,
                amount=-int(round(amount * 100)),  # cents, negativo = descuento
                currency=invoice.currency or "usd",
                description=f"Crédito por referidos ({credit.get('active_count', 0)} activos)",
                subscription=subscription_id,
            )
            logger.info(
                f"Descuento aplicado a tenant={tenant['tenant_id']}: "
                f"-${amount} ({credit.get('active_count', 0)} comisiones activas)"
            )
        except Exception as e:
            logger.error(f"Error aplicando descuento de referidos: {e}")

    async def _record_applied_commission(self, tenant_id: str, invoice):
        """Si la invoice paga incluyó descuento, registrar el monto en applied_invoices.
        Buscamos invoice items con descripcion 'Crédito por referidos'."""
        try:
            items = invoice.lines.data if hasattr(invoice, "lines") else []
        except Exception:
            return
        total_credit = 0
        for it in items:
            desc = (getattr(it, "description", "") or "")
            amount = getattr(it, "amount", 0)
            if "Crédito por referidos" in desc and amount < 0:
                total_credit += -amount / 100  # convertir a USD positivo

        if total_credit <= 0:
            return

        # Distribuir el credito entre commissions activas (FIFO por created_at)
        actives_cursor = self.db.commissions.find(
            {"referrer_tenant_id": tenant_id, "status": "active"},
            {"_id": 0, "commission_id": 1, "amount_per_month_usd": 1},
        ).sort("created_at", 1)
        remaining = total_credit
        async for c in actives_cursor:
            per_month = c.get("amount_per_month_usd", 0)
            if remaining <= 0 or per_month <= 0:
                break
            chunk = min(per_month, remaining)
            await self.db.commissions.update_one(
                {"commission_id": c["commission_id"]},
                {
                    "$inc": {"total_credited_usd": chunk},
                    "$push": {"applied_invoices": {
                        "invoice_id": getattr(invoice, "id", ""),
                        "amount_usd": chunk,
                        "applied_at": datetime.utcnow().isoformat(),
                    }},
                },
            )
            remaining -= chunk

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
        # Cancelar comisiones donde este tenant era el REFERIDO (su referrer deja de cobrar)
        try:
            from commission_service import cancel_commissions_for_referred
            await cancel_commissions_for_referred(self.db, tenant["tenant_id"])
        except Exception as e:
            logger.warning(f"No se pudieron cancelar commissions: {e}")
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

        plan_id = tenant.get("subscription_plan", "pro")
        plan = SUBSCRIPTION_PLANS.get(plan_id) or SUBSCRIPTION_PLANS.get("pro")

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

    async def bill_overage_for_tenant(self, tenant_id: str, period: str = None) -> Dict:
        """
        Crea un InvoiceItem en Stripe por el overage de IA del periodo.
        Se aplica a la proxima factura recurrente del tenant.

        Logica:
        - Lee overage_messages del periodo actual
        - Multiplica por OVERAGE_PRICE segun el plan
        - Crea InvoiceItem (se cobra en proximo billing cycle)
        - Marca el overage como facturado (reset)
        """
        if not self.api_key:
            return {"status": "error", "message": "Stripe no configurado"}

        from usage_service import OVERAGE_PRICE
        from datetime import datetime, timezone

        if not period:
            period = datetime.now(timezone.utc).strftime("%Y-%m")

        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant:
            return {"status": "error", "message": "Tenant no encontrado"}

        if not tenant.get("stripe_customer_id") or not tenant.get("stripe_subscription_id"):
            return {"status": "skipped", "message": "Sin suscripcion Stripe activa"}

        # Skip if has own OpenAI key (sin overage)
        if tenant.get("openai_api_key"):
            return {"status": "skipped", "message": "Tenant tiene su propia OpenAI key"}

        usage = await self.db.usage.find_one(
            {"tenant_id": tenant_id, "period": period},
            {"_id": 0}
        )
        overage_count = usage.get("overage_messages", 0) if usage else 0
        if overage_count <= 0:
            return {"status": "skipped", "message": "Sin overage en el periodo"}

        # Idempotency: skip if ya facturado
        if usage.get("overage_billed"):
            return {"status": "skipped", "message": "Overage ya facturado este periodo"}

        plan_id = tenant.get("subscription_plan", "pro")
        rate = OVERAGE_PRICE.get(plan_id, 0.05)
        amount_usd = round(overage_count * rate, 2)
        amount_cents = int(round(overage_count * rate * 100))

        if amount_cents <= 0:
            return {"status": "skipped", "message": "Monto demasiado bajo"}

        try:
            invoice_item = stripe.InvoiceItem.create(
                customer=tenant["stripe_customer_id"],
                amount=amount_cents,
                currency="usd",
                description=f"IA overage {period}: {overage_count} mensajes x ${rate} = ${amount_usd}",
                subscription=tenant["stripe_subscription_id"],
                metadata={
                    "tenant_id": tenant_id,
                    "period": period,
                    "overage_messages": str(overage_count),
                    "rate": str(rate),
                    "type": "ai_overage"
                }
            )

            # Mark as billed in DB (idempotency)
            await self.db.usage.update_one(
                {"tenant_id": tenant_id, "period": period},
                {"$set": {
                    "overage_billed": True,
                    "overage_billed_at": datetime.utcnow().isoformat(),
                    "overage_invoice_item_id": invoice_item.id,
                    "overage_amount_billed": amount_usd
                }}
            )

            # Save transaction record
            await self.db.payment_transactions.insert_one({
                "tenant_id": tenant_id,
                "type": "ai_overage",
                "period": period,
                "amount": amount_usd,
                "currency": "usd",
                "overage_messages": overage_count,
                "rate": rate,
                "stripe_invoice_item_id": invoice_item.id,
                "stripe_subscription_id": tenant["stripe_subscription_id"],
                "payment_status": "pending",
                "created_at": datetime.utcnow().isoformat()
            })

            logger.info(f"Overage facturado: tenant={tenant_id} period={period} msgs={overage_count} amount=${amount_usd}")
            return {
                "status": "ok",
                "tenant_id": tenant_id,
                "period": period,
                "overage_messages": overage_count,
                "amount": amount_usd,
                "invoice_item_id": invoice_item.id
            }

        except Exception as e:
            logger.error(f"Error facturando overage tenant {tenant_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def bill_all_overages(self, period: str = None) -> Dict:
        """
        Itera todos los tenants activos y factura el overage del periodo.
        Para correr al final del mes (cron) o manualmente desde superadmin.
        """
        from datetime import datetime, timezone
        if not period:
            # Default: facturar el mes anterior cuando se corre el primer dia del mes
            now = datetime.now(timezone.utc)
            if now.day <= 3:
                # Use previous month
                prev_month = now.month - 1 if now.month > 1 else 12
                prev_year = now.year if now.month > 1 else now.year - 1
                period = f"{prev_year:04d}-{prev_month:02d}"
            else:
                period = now.strftime("%Y-%m")

        tenants = await self.db.tenants.find(
            {"subscription_status": "active"},
            {"_id": 0, "tenant_id": 1}
        ).to_list(1000)

        results = {"period": period, "processed": 0, "billed": 0, "skipped": 0, "errors": 0, "details": []}

        for t in tenants:
            res = await self.bill_overage_for_tenant(t["tenant_id"], period)
            results["processed"] += 1
            if res.get("status") == "ok":
                results["billed"] += 1
            elif res.get("status") == "skipped":
                results["skipped"] += 1
            else:
                results["errors"] += 1
            results["details"].append({"tenant_id": t["tenant_id"], **res})

        return results
