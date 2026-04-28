"""
InmoBot SaaS - Widget Analytics Service
Tracking de conversion del catalogo publico embebible.
"""
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

EVENT_TYPES = ("view", "click_product", "click_whatsapp", "ai_search", "lead_generated")


class WidgetAnalyticsService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    def _hash_ip(self, ip: Optional[str]) -> str:
        if not ip:
            return ""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    async def track_event(
        self,
        tenant_id: str,
        event_type: str,
        product_id: Optional[str] = None,
        query: Optional[str] = None,
        referrer: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> dict:
        """Registra un evento del widget publico.
        IP se hashea para no guardar PII.
        """
        if event_type not in EVENT_TYPES:
            return {"status": "error", "message": "event_type invalido"}

        doc = {
            "tenant_id": tenant_id,
            "event_type": event_type,
            "product_id": product_id,
            "query": (query or "")[:200] if query else None,
            "referrer": (referrer or "")[:500] if referrer else None,
            "user_agent": (user_agent or "")[:200] if user_agent else None,
            "ip_hash": self._hash_ip(client_ip),
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        await self.db.widget_analytics.insert_one(doc)
        return {"status": "ok"}

    async def get_analytics(self, tenant_id: str, days: int = 30) -> dict:
        """Retorna metricas del widget del tenant en los ultimos N dias"""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        base_match = {"tenant_id": tenant_id, "created_at": {"$gte": since}}

        # Total by event type
        pipeline_events = [
            {"$match": base_match},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        ]
        events = await self.db.widget_analytics.aggregate(pipeline_events).to_list(10)
        events_map = {e["_id"]: e["count"] for e in events}

        # Unique sessions (visitors)
        unique_visitors_pipeline = [
            {"$match": {**base_match, "ip_hash": {"$ne": ""}}},
            {"$group": {"_id": "$ip_hash"}},
            {"$count": "total"}
        ]
        uv_result = await self.db.widget_analytics.aggregate(unique_visitors_pipeline).to_list(1)
        unique_visitors = uv_result[0]["total"] if uv_result else 0

        # Events by day
        pipeline_by_day = [
            {"$match": base_match},
            {"$group": {
                "_id": "$date",
                "views": {"$sum": {"$cond": [{"$eq": ["$event_type", "view"]}, 1, 0]}},
                "clicks_product": {"$sum": {"$cond": [{"$eq": ["$event_type", "click_product"]}, 1, 0]}},
                "clicks_whatsapp": {"$sum": {"$cond": [{"$eq": ["$event_type", "click_whatsapp"]}, 1, 0]}},
                "ai_searches": {"$sum": {"$cond": [{"$eq": ["$event_type", "ai_search"]}, 1, 0]}},
            }},
            {"$sort": {"_id": 1}}
        ]
        by_day = await self.db.widget_analytics.aggregate(pipeline_by_day).to_list(100)
        by_day_clean = [
            {
                "date": r["_id"],
                "views": r.get("views", 0),
                "clicks_product": r.get("clicks_product", 0),
                "clicks_whatsapp": r.get("clicks_whatsapp", 0),
                "ai_searches": r.get("ai_searches", 0),
            }
            for r in by_day
        ]

        # Top products clicked
        pipeline_top_products = [
            {"$match": {**base_match, "event_type": "click_product", "product_id": {"$ne": None}}},
            {"$group": {"_id": "$product_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        top_products_raw = await self.db.widget_analytics.aggregate(pipeline_top_products).to_list(10)
        # Resolve product names
        top_products = []
        for tp in top_products_raw:
            prod = await self.db.products.find_one(
                {"tenant_id": tenant_id, "product_id": tp["_id"]},
                {"_id": 0, "name": 1, "category": 1, "price": 1}
            )
            if prod:
                top_products.append({**prod, "clicks": tp["count"]})

        # Top AI queries
        pipeline_queries = [
            {"$match": {**base_match, "event_type": "ai_search", "query": {"$ne": None, "$ne": ""}}},
            {"$group": {"_id": "$query", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        top_queries_raw = await self.db.widget_analytics.aggregate(pipeline_queries).to_list(10)
        top_queries = [{"query": q["_id"], "count": q["count"]} for q in top_queries_raw]

        views = events_map.get("view", 0)
        clicks_product = events_map.get("click_product", 0)
        clicks_whatsapp = events_map.get("click_whatsapp", 0)
        leads_generated = events_map.get("lead_generated", 0)

        conversion_rate = round((leads_generated / views * 100), 2) if views > 0 else 0.0
        click_through_rate = round(((clicks_product + clicks_whatsapp) / views * 100), 2) if views > 0 else 0.0

        return {
            "period_days": days,
            "summary": {
                "views": views,
                "unique_visitors": unique_visitors,
                "clicks_product": clicks_product,
                "clicks_whatsapp": clicks_whatsapp,
                "ai_searches": events_map.get("ai_search", 0),
                "leads_generated": leads_generated,
                "click_through_rate": click_through_rate,
                "conversion_rate": conversion_rate,
            },
            "by_day": by_day_clean,
            "top_products": top_products,
            "top_queries": top_queries,
        }

    async def get_global_analytics(self) -> dict:
        """SuperAdmin: analytics globales de TODOS los tenants"""
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {
                "_id": "$tenant_id",
                "views": {"$sum": {"$cond": [{"$eq": ["$event_type", "view"]}, 1, 0]}},
                "clicks": {"$sum": {"$cond": [{"$in": ["$event_type", ["click_product", "click_whatsapp"]]}, 1, 0]}},
                "leads": {"$sum": {"$cond": [{"$eq": ["$event_type", "lead_generated"]}, 1, 0]}},
            }},
            {"$sort": {"views": -1}},
        ]
        per_tenant = await self.db.widget_analytics.aggregate(pipeline).to_list(100)
        return {
            "period_days": 30,
            "per_tenant": [{"tenant_id": r["_id"], **{k: v for k, v in r.items() if k != "_id"}} for r in per_tenant]
        }
