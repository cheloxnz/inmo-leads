"""
InmoBot SaaS - Servicio de control de uso (rate limiting por tenant)
Controla conversaciones IA y leads por mes.
Soporta: limites por plan, bloques extras, y overage automatico.
"""
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Bloques de mensajes IA que se pueden comprar
AI_MESSAGE_PACKS = {
    "pack_1000": {"messages": 1000, "price": 29, "name": "+1,000 mensajes IA"},
    "pack_5000": {"messages": 5000, "price": 99, "name": "+5,000 mensajes IA"},
    "pack_10000": {"messages": 10000, "price": 149, "name": "+10,000 mensajes IA"},
}

# Precio por mensaje excedente (auto-cobro)
OVERAGE_PRICE = {
    "pro": 0.05,
    "enterprise": 0.03
}


class UsageService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    def _current_period_key(self) -> str:
        """Retorna clave del periodo actual (YYYY-MM)"""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    async def get_usage(self, tenant_id: str) -> dict:
        """Obtiene uso actual del tenant en el periodo"""
        period = self._current_period_key()
        usage = await self.db.usage.find_one(
            {"tenant_id": tenant_id, "period": period},
            {"_id": 0}
        )
        if not usage:
            return {"ai_messages": 0, "leads_created": 0, "extra_messages": 0, "overage_messages": 0, "period": period}
        return usage

    async def increment_ai_messages(self, tenant_id: str) -> bool:
        """
        Incrementa contador de mensajes IA.
        Logica:
        1. Si tiene key propia → sin limite
        2. Si esta dentro del plan → OK
        3. Si tiene bloques extra comprados → descuenta de ahi
        4. Si excede todo → marca como overage (se cobra despues)
        Retorna True siempre (nunca corta el servicio), registra overage.
        """
        period = self._current_period_key()

        # Get tenant info
        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant:
            return False

        # If tenant has own OpenAI key, unlimited
        if tenant.get("openai_api_key"):
            await self.db.usage.update_one(
                {"tenant_id": tenant_id, "period": period},
                {"$inc": {"ai_messages": 1}, "$set": {"tenant_id": tenant_id, "period": period}},
                upsert=True
            )
            return True

        max_ai = tenant.get("max_ai_messages", 2000)

        # Get current usage
        usage = await self.db.usage.find_one(
            {"tenant_id": tenant_id, "period": period},
            {"_id": 0}
        )
        current = usage.get("ai_messages", 0) if usage else 0
        extra_balance = usage.get("extra_messages", 0) if usage else 0

        if current < max_ai:
            # Within plan limit
            await self.db.usage.update_one(
                {"tenant_id": tenant_id, "period": period},
                {"$inc": {"ai_messages": 1}, "$set": {"tenant_id": tenant_id, "period": period}},
                upsert=True
            )
        elif extra_balance > 0:
            # Use from extra packs
            await self.db.usage.update_one(
                {"tenant_id": tenant_id, "period": period},
                {"$inc": {"ai_messages": 1, "extra_messages": -1}},
            )
        else:
            # Overage - still process but track for billing
            await self.db.usage.update_one(
                {"tenant_id": tenant_id, "period": period},
                {"$inc": {"ai_messages": 1, "overage_messages": 1}, "$set": {"tenant_id": tenant_id, "period": period}},
                upsert=True
            )
            new_overage = (usage.get("overage_messages", 0) if usage else 0) + 1
            if new_overage % 100 == 0:
                logger.info(f"Tenant {tenant_id} overage: {new_overage} msgs extra")

        return True

    async def add_extra_messages(self, tenant_id: str, pack_id: str) -> dict:
        """Agrega mensajes extra al balance del tenant (despues de pago)"""
        pack = AI_MESSAGE_PACKS.get(pack_id)
        if not pack:
            return {"error": "Pack no valido"}

        period = self._current_period_key()
        await self.db.usage.update_one(
            {"tenant_id": tenant_id, "period": period},
            {"$inc": {"extra_messages": pack["messages"]}, "$set": {"tenant_id": tenant_id, "period": period}},
            upsert=True
        )

        logger.info(f"Tenant {tenant_id} compro {pack['name']}")
        return {"status": "ok", "added": pack["messages"]}

    async def increment_leads(self, tenant_id: str) -> bool:
        """Incrementa contador de leads creados."""
        period = self._current_period_key()

        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant:
            return False

        max_leads = tenant.get("max_leads", 2000)

        usage = await self.db.usage.find_one(
            {"tenant_id": tenant_id, "period": period},
            {"_id": 0}
        )
        current = usage.get("leads_created", 0) if usage else 0

        if current >= max_leads:
            logger.warning(f"Tenant {tenant_id} excedio limite leads: {current}/{max_leads}")
            return False

        await self.db.usage.update_one(
            {"tenant_id": tenant_id, "period": period},
            {"$inc": {"leads_created": 1}, "$set": {"tenant_id": tenant_id, "period": period}},
            upsert=True
        )
        return True

    async def get_usage_summary(self, tenant_id: str) -> dict:
        """Retorna resumen de uso con porcentaje y costos de overage"""
        period = self._current_period_key()
        usage = await self.get_usage(tenant_id)
        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})

        max_ai = tenant.get("max_ai_messages", 2000) if tenant else 2000
        max_leads = tenant.get("max_leads", 2000) if tenant else 2000
        has_own_key = bool(tenant.get("openai_api_key")) if tenant else False
        plan = tenant.get("subscription_plan", "pro") if tenant else "pro"

        ai_used = usage.get("ai_messages", 0)
        leads_used = usage.get("leads_created", 0)
        extra_balance = usage.get("extra_messages", 0)
        overage = usage.get("overage_messages", 0)
        overage_rate = OVERAGE_PRICE.get(plan, 0.05)
        overage_cost = round(overage * overage_rate, 2)

        return {
            "period": period,
            "ai_messages": {
                "used": ai_used,
                "limit": max_ai,
                "extra_balance": extra_balance,
                "total_available": max_ai + extra_balance,
                "percentage": round((ai_used / max_ai * 100), 1) if max_ai > 0 else 0,
                "unlimited": has_own_key,
                "overage": overage,
                "overage_rate": overage_rate,
                "overage_cost": overage_cost
            },
            "leads": {
                "used": leads_used,
                "limit": max_leads,
                "percentage": round((leads_used / max_leads * 100), 1) if max_leads > 0 else 0
            },
            "packs_available": AI_MESSAGE_PACKS
        }
