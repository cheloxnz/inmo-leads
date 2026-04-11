"""
Servicio de pagos con Stripe para suscripciones SaaS
"""
import os
import logging
import stripe
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
        "setup_price": 99.00,
        "description": "Ideal para empezar",
        "whatsapp_numbers": 1,
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
        "setup_price": 149.00,
        "description": "Para inmobiliarias en crecimiento",
        "whatsapp_numbers": 1,
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
        "setup_price": 249.00,
        "description": "Para operaciones medianas",
        "whatsapp_numbers": 5,
        "features": [
            "Hasta 5 números WhatsApp",
            "Conversaciones ilimitadas",
            "10 usuarios",
            "Dashboard completo",
            "Métricas por sucursal",
            "Soporte prioritario",
            "Onboarding personalizado"
        ]
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 799.00,
        "setup_price": 499.00,
        "description": "Solución completa para grandes operaciones",
        "whatsapp_numbers": 999,
        "features": [
            "Números WhatsApp ilimitados",
            "Conversaciones ilimitadas",
            "Usuarios ilimitados",
            "Dashboard completo",
            "Métricas avanzadas",
            "API completa",
            "Integraciones personalizadas",
            "Soporte 24/7",
            "Onboarding VIP",
            "SLA garantizado"
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
        """Retorna los planes disponibles"""
        return SUBSCRIPTION_PLANS
    
    async def create_checkout_session(
        self, 
        plan_id: str, 
        customer_email: str,
        customer_name: str,
        origin_url: str
    ) -> Dict:
        """Crea una sesión de checkout de Stripe"""
        if not self.api_key:
            raise ValueError("Stripe no está configurado")
        
        if plan_id not in SUBSCRIPTION_PLANS:
            raise ValueError(f"Plan no válido: {plan_id}")
        
        plan = SUBSCRIPTION_PLANS[plan_id]
        
        try:
            # URLs de redirección
            success_url = f"{origin_url}/pago-exitoso?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{origin_url}/planes"
            
            # Crear sesión de checkout
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f"InmoBot - Plan {plan['name']}",
                            'description': plan['description'],
                        },
                        'unit_amount': int(plan['price'] * 100),  # Stripe usa centavos
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=customer_email,
                metadata={
                    "plan_id": plan_id,
                    "plan_name": plan["name"],
                    "customer_email": customer_email,
                    "customer_name": customer_name
                }
            )
            
            # Guardar transacción pendiente
            transaction = {
                "session_id": session.id,
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
            logger.info(f"Checkout session creada: {session.id} para {customer_email}")
            
            return {
                "checkout_url": session.url,
                "session_id": session.id
            }
            
        except Exception as e:
            logger.error(f"Error creando checkout session: {e}")
            raise
    
    async def get_checkout_status(self, session_id: str) -> Dict:
        """Obtiene el estado de una sesión de checkout"""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Actualizar transacción en DB
            if session.payment_status == "paid":
                await self.db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "paid_at": datetime.utcnow().isoformat()
                    }}
                )
                logger.info(f"Pago confirmado para session: {session_id}")
            
            return {
                "status": session.status,
                "payment_status": session.payment_status,
                "amount": session.amount_total / 100,  # Convertir de centavos
                "currency": session.currency,
                "metadata": session.metadata
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo status: {e}")
            raise
    
    async def handle_webhook(self, body: bytes, signature: str) -> Dict:
        """Maneja webhooks de Stripe"""
        try:
            if self.webhook_secret:
                event = stripe.Webhook.construct_event(
                    body, signature, self.webhook_secret
                )
            else:
                # Sin verificación de firma (solo para desarrollo)
                import json
                event = stripe.Event.construct_from(
                    json.loads(body), stripe.api_key
                )
            
            logger.info(f"Webhook recibido: {event.type}")
            
            # Manejar evento de pago completado
            if event.type == "checkout.session.completed":
                session = event.data.object
                await self._handle_successful_payment(session)
            
            return {"status": "success", "event_type": event.type}
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Error verificando firma del webhook: {e}")
            raise
        except Exception as e:
            logger.error(f"Error en webhook: {e}")
            raise
    
    async def _handle_successful_payment(self, session) -> None:
        """Procesa un pago exitoso"""
        try:
            session_id = session.id
            metadata = session.metadata
            
            # Actualizar transacción
            await self.db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": "paid",
                    "stripe_payment_intent": session.payment_intent,
                    "paid_at": datetime.utcnow().isoformat()
                }}
            )
            
            # Crear registro de suscripción
            subscription = {
                "session_id": session_id,
                "plan_id": metadata.get("plan_id"),
                "plan_name": metadata.get("plan_name"),
                "customer_email": metadata.get("customer_email"),
                "customer_name": metadata.get("customer_name"),
                "status": "active",
                "started_at": datetime.utcnow().isoformat()
            }
            
            await self.db.subscriptions.insert_one(subscription)
            logger.info(f"Suscripción creada para: {metadata.get('customer_email')}")
            
        except Exception as e:
            logger.error(f"Error procesando pago exitoso: {e}")
            raise
    
    async def get_transaction_history(self, limit: int = 50) -> list:
        """Obtiene historial de transacciones"""
        cursor = self.db.payment_transactions.find().sort("created_at", -1).limit(limit)
        transactions = await cursor.to_list(length=limit)
        
        # Convertir ObjectId a string
        for t in transactions:
            t["_id"] = str(t["_id"])
        
        return transactions
