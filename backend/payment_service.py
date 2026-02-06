"""
Servicio de pagos con Stripe para suscripciones SaaS
"""
import os
import logging
from datetime import datetime
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Planes de suscripción (precios en USD)
SUBSCRIPTION_PLANS = {
    "starter": {
        "name": "Starter",
        "price": 49.00,
        "description": "Ideal para empezar",
        "features": [
            "1 número de WhatsApp",
            "500 conversaciones/mes",
            "2 usuarios",
            "Dashboard básico",
            "Soporte por email"
        ]
    },
    "pro": {
        "name": "Profesional",
        "price": 129.00,
        "description": "Para inmobiliarias en crecimiento",
        "features": [
            "1 número de WhatsApp",
            "Conversaciones ilimitadas",
            "5 usuarios",
            "Dashboard completo",
            "Métricas avanzadas",
            "Soporte prioritario"
        ]
    },
    "agency": {
        "name": "Agencia",
        "price": 299.00,
        "description": "Para grandes operaciones",
        "features": [
            "Múltiples números WhatsApp",
            "Conversaciones ilimitadas",
            "Usuarios ilimitados",
            "White-label",
            "API access",
            "Soporte dedicado",
            "Onboarding personalizado"
        ]
    }
}


class PaymentService:
    def __init__(self, db):
        self.db = db
        self.api_key = os.getenv("STRIPE_API_KEY")
        if not self.api_key:
            logger.warning("STRIPE_API_KEY no configurada")
    
    async def create_checkout_session(
        self, 
        plan_id: str, 
        customer_email: str,
        customer_name: str,
        origin_url: str
    ) -> Dict:
        """Crea una sesión de checkout para suscripción"""
        
        if plan_id not in SUBSCRIPTION_PLANS:
            raise ValueError(f"Plan inválido: {plan_id}")
        
        plan = SUBSCRIPTION_PLANS[plan_id]
        
        try:
            from emergentintegrations.payments.stripe.checkout import (
                StripeCheckout, 
                CheckoutSessionRequest
            )
            
            # URLs de redirección
            success_url = f"{origin_url}/pago-exitoso?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{origin_url}/planes"
            webhook_url = f"{origin_url}/api/webhook/stripe"
            
            stripe_checkout = StripeCheckout(
                api_key=self.api_key, 
                webhook_url=webhook_url
            )
            
            # Crear sesión de checkout
            checkout_request = CheckoutSessionRequest(
                amount=plan["price"],
                currency="usd",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "plan_id": plan_id,
                    "plan_name": plan["name"],
                    "customer_email": customer_email,
                    "customer_name": customer_name
                }
            )
            
            session = await stripe_checkout.create_checkout_session(checkout_request)
            
            # Guardar transacción pendiente
            transaction = {
                "session_id": session.session_id,
                "plan_id": plan_id,
                "plan_name": plan["name"],
                "amount": plan["price"],
                "currency": "usd",
                "customer_email": customer_email,
                "customer_name": customer_name,
                "payment_status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }
            
            await self.db.payment_transactions.insert_one(transaction)
            logger.info(f"Checkout session creada: {session.session_id} para {customer_email}")
            
            return {
                "checkout_url": session.url,
                "session_id": session.session_id
            }
            
        except Exception as e:
            logger.error(f"Error creando checkout session: {e}")
            raise
    
    async def get_checkout_status(self, session_id: str) -> Dict:
        """Obtiene el estado de una sesión de checkout"""
        try:
            from emergentintegrations.payments.stripe.checkout import StripeCheckout
            
            stripe_checkout = StripeCheckout(api_key=self.api_key, webhook_url="")
            status = await stripe_checkout.get_checkout_status(session_id)
            
            # Actualizar transacción en DB
            if status.payment_status == "paid":
                await self.db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "paid_at": datetime.utcnow().isoformat()
                    }}
                )
                logger.info(f"Pago confirmado para session: {session_id}")
            
            return {
                "status": status.status,
                "payment_status": status.payment_status,
                "amount": status.amount_total / 100,  # Convertir de centavos
                "currency": status.currency,
                "metadata": status.metadata
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo status: {e}")
            raise
    
    async def handle_webhook(self, body: bytes, signature: str) -> Dict:
        """Maneja webhooks de Stripe"""
        try:
            from emergentintegrations.payments.stripe.checkout import StripeCheckout
            
            stripe_checkout = StripeCheckout(api_key=self.api_key, webhook_url="")
            event = await stripe_checkout.handle_webhook(body, signature)
            
            logger.info(f"Webhook recibido: {event.event_type}")
            
            if event.payment_status == "paid":
                await self.db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "paid_at": datetime.utcnow().isoformat(),
                        "event_id": event.event_id
                    }}
                )
            
            return {
                "event_type": event.event_type,
                "session_id": event.session_id,
                "payment_status": event.payment_status
            }
            
        except Exception as e:
            logger.error(f"Error procesando webhook: {e}")
            raise
    
    async def get_all_transactions(self) -> list:
        """Obtiene todas las transacciones"""
        cursor = self.db.payment_transactions.find({}).sort("created_at", -1)
        transactions = await cursor.to_list(100)
        for t in transactions:
            t["_id"] = str(t["_id"])
        return transactions
    
    def get_plans(self) -> Dict:
        """Retorna los planes disponibles"""
        return SUBSCRIPTION_PLANS
