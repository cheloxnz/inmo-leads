"""
InmoBot SaaS - Servicio de control de uso (rate limiting por tenant)
Controla conversaciones IA y leads por mes.
"""
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


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
            return {"ai_messages": 0, "leads_created": 0, "period": period}
        return usage

    async def increment_ai_messages(self, tenant_id: str) -> bool:
        """
        Incrementa contador de mensajes IA.
        Retorna True si está dentro del límite, False si excedió.
        """
        period = self._current_period_key()

        # Get tenant limits
        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant:
            return False

        max_ai = tenant.get("max_ai_messages", 2000)

        # If tenant has own OpenAI key, no limit
        if tenant.get("openai_api_key"):
            await self.db.usage.update_one(
                {"tenant_id": tenant_id, "period": period},
                {"$inc": {"ai_messages": 1}, "$set": {"tenant_id": tenant_id, "period": period}},
                upsert=True
            )
            return True

        # Check current usage
        usage = await self.db.usage.find_one(
            {"tenant_id": tenant_id, "period": period},
            {"_id": 0}
        )
        current = usage.get("ai_messages", 0) if usage else 0

        if current >= max_ai:
            logger.warning(f"Tenant {tenant_id} excedio limite IA: {current}/{max_ai}")
            return False

        # Increment
        await self.db.usage.update_one(
            {"tenant_id": tenant_id, "period": period},
            {"$inc": {"ai_messages": 1}, "$set": {"tenant_id": tenant_id, "period": period}},
            upsert=True
        )
        return True

    async def increment_leads(self, tenant_id: str) -> bool:
        """
        Incrementa contador de leads creados.
        Retorna True si está dentro del límite, False si excedió.
        """
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
        """Retorna resumen de uso con porcentaje"""
        period = self._current_period_key()
        usage = await self.get_usage(tenant_id)
        tenant = await self.db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})

        max_ai = tenant.get("max_ai_messages", 2000) if tenant else 2000
        max_leads = tenant.get("max_leads", 2000) if tenant else 2000
        has_own_key = bool(tenant.get("openai_api_key")) if tenant else False

        ai_used = usage.get("ai_messages", 0)
        leads_used = usage.get("leads_created", 0)

        return {
            "period": period,
            "ai_messages": {
                "used": ai_used,
                "limit": max_ai,
                "percentage": round((ai_used / max_ai * 100), 1) if max_ai > 0 else 0,
                "unlimited": has_own_key
            },
            "leads": {
                "used": leads_used,
                "limit": max_leads,
                "percentage": round((leads_used / max_leads * 100), 1) if max_leads > 0 else 0
            }
        }
