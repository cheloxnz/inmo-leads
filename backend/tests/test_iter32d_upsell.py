"""Tests Iter32d: upsell automatic emails."""
import os
import uuid
import asyncio

import pytest
from pymongo import MongoClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


def test_upsell_threshold_and_idempotency(db):
    """Tenant Pro con leads >= 50 dispara upsell. Segundo run dentro del cooldown
    NO redispara. Calculate retorna stats correctos."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from upsell_service import calculate_unmet_demand_for_tenant, check_and_send_upsells

        captured = []

        class MockEmail:
            async def send_upsell_unmet_demand(self, **kw):
                captured.append(kw)
                return True

        tag = uuid.uuid4().hex[:6]
        tid = f"upsell-test-{tag}"

        # Crear tenant Pro activo + agente admin
        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"Upsell Biz {tag}",
            "name": f"Upsell Biz {tag}",
            "active": True,
            "subscription_plan": "pro",
            "subscription_status": "active",
        })
        await mdb.agents.insert_one({
            "tenant_id": tid,
            "email": f"upsell-{tag}@example.com",
            "role": "admin",
            "active": True,
        })
        # Producto agotado con precio alto
        pid = f"upsellprod-{tag}"
        await mdb.products.insert_one({
            "product_id": pid,
            "tenant_id": tid,
            "name": f"BigItem {tag}",
            "active": False,
            "stock_quantity": 0,
            "price": 100,
        })
        # 60 leads en waitlist (cruza UPSELL_THRESHOLD_LEADS=50 default)
        docs = [
            {
                "tenant_id": tid, "product_id": pid,
                "lead_phone": f"5499{tag}{i:03d}",
                "product_name": f"BigItem {tag}",
                "asked_at": "2026-05-01T00:00:00+00:00",
                "notified_at": None,
                "created_at": "2026-05-01T00:00:00+00:00",
            } for i in range(60)
        ]
        await mdb.product_waitlist.insert_many(docs)

        try:
            # 1. calculate_unmet_demand_for_tenant
            demand = await calculate_unmet_demand_for_tenant(mdb, tid)
            assert demand["leads_count"] == 60
            assert demand["value_usd"] == 6000  # 60 × 100
            assert len(demand["top_products"]) == 1
            assert demand["top_products"][0]["leads_count"] == 60

            # 2. Primer run → debe enviar
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            r1 = await check_and_send_upsells(mdb, MockEmail())
            ours_first = [c for c in captured if c["business_name"] == f"Upsell Biz {tag}"]
            assert len(ours_first) == 1, f"primer run debió enviar 1; envió {len(ours_first)}"
            assert ours_first[0]["to_email"] == f"upsell-{tag}@example.com"
            assert ours_first[0]["demand"]["leads_count"] == 60
            evt = await mdb.upsell_events.find_one({"tenant_id": tid})
            assert evt is not None
            assert evt["delivered"] is True

            # 3. Segundo run inmediato → cooldown salta, NO envía de nuevo
            captured.clear()
            r2 = await check_and_send_upsells(mdb, MockEmail())
            ours_second = [c for c in captured if c["business_name"] == f"Upsell Biz {tag}"]
            assert len(ours_second) == 0, "segundo run dentro de cooldown NO debe enviar"
            assert r2["skipped_cooldown"] >= 1

        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.agents.delete_many({"tenant_id": tid})
            await mdb.products.delete_one({"product_id": pid})
            await mdb.product_waitlist.delete_many({"tenant_id": tid})
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())


def test_upsell_skips_below_threshold(db):
    """Tenant con solo 5 leads NO recibe upsell."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from upsell_service import check_and_send_upsells

        captured = []

        class MockEmail:
            async def send_upsell_unmet_demand(self, **kw):
                captured.append(kw)
                return True

        tag = uuid.uuid4().hex[:6]
        tid = f"upsell-low-{tag}"
        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"LowDemand {tag}",
            "active": True,
            "subscription_plan": "pro",
            "subscription_status": "active",
        })
        await mdb.agents.insert_one({
            "tenant_id": tid,
            "email": f"low-{tag}@example.com",
            "role": "admin",
            "active": True,
        })
        pid = f"lowprod-{tag}"
        await mdb.products.insert_one({
            "product_id": pid, "tenant_id": tid,
            "name": "Low", "active": False, "stock_quantity": 0, "price": 10,
        })
        # Solo 5 leads, valor 5×10=50 (debajo de threshold 1500)
        docs = [
            {
                "tenant_id": tid, "product_id": pid,
                "lead_phone": f"5400{tag}{i}",
                "product_name": "Low",
                "asked_at": "2026-05-01T00:00:00+00:00",
                "notified_at": None,
                "created_at": "2026-05-01T00:00:00+00:00",
            } for i in range(5)
        ]
        await mdb.product_waitlist.insert_many(docs)

        try:
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            await check_and_send_upsells(mdb, MockEmail())
            ours = [c for c in captured if tag in c.get("business_name", "")]
            assert len(ours) == 0, "no debe enviar para tenant con baja demanda"
            evt = await mdb.upsell_events.find_one({"tenant_id": tid})
            assert evt is None, "no debe registrar evento si no envió"
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.agents.delete_many({"tenant_id": tid})
            await mdb.products.delete_one({"product_id": pid})
            await mdb.product_waitlist.delete_many({"tenant_id": tid})
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())


def test_upsell_skips_enterprise_already(db):
    """Tenant ya en Enterprise NO recibe upsell."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from upsell_service import check_and_send_upsells

        captured = []

        class MockEmail:
            async def send_upsell_unmet_demand(self, **kw):
                captured.append(kw)
                return True

        tag = uuid.uuid4().hex[:6]
        tid = f"ent-{tag}"
        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"AlreadyEnt {tag}",
            "active": True,
            "subscription_plan": "enterprise",  # ya Enterprise
            "subscription_status": "active",
        })
        await mdb.agents.insert_one({
            "tenant_id": tid, "email": f"ent-{tag}@x.com",
            "role": "admin", "active": True,
        })
        pid = f"entprod-{tag}"
        await mdb.products.insert_one({
            "product_id": pid, "tenant_id": tid,
            "name": "X", "active": False, "stock_quantity": 0, "price": 200,
        })
        docs = [{
            "tenant_id": tid, "product_id": pid,
            "lead_phone": f"5460{tag}{i:03d}",
            "product_name": "X",
            "asked_at": "2026-05-01T00:00:00+00:00",
            "notified_at": None,
            "created_at": "2026-05-01T00:00:00+00:00",
        } for i in range(80)]
        await mdb.product_waitlist.insert_many(docs)

        try:
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            await check_and_send_upsells(mdb, MockEmail())
            ours = [c for c in captured if tag in c.get("business_name", "")]
            assert len(ours) == 0, "no debe enviar a Enterprise"
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.agents.delete_many({"tenant_id": tid})
            await mdb.products.delete_one({"product_id": pid})
            await mdb.product_waitlist.delete_many({"tenant_id": tid})
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())
