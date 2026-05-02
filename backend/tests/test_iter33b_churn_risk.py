"""Tests Iter33b: Churn risk detection en admin report."""
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

import pytest
from pymongo import MongoClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


def test_churn_risk_detected_for_dropping_tenant(db):
    """Tenant activo con leads esta semana < 50% del promedio de las últimas
    4 semanas → aparece en churn_risk."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from scheduler import ScheduledTasks
        captured = []

        class MockEmail:
            async def send_admin_weekly_report(self, **kw):
                captured.append(kw)
                return True

        tag = uuid.uuid4().hex[:6]
        tid = f"churn-{tag}"

        now = datetime.now(timezone.utc)
        # Tenant creado hace 60 días (baseline sólido)
        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"Churning {tag}",
            "active": True,
            "subscription_plan": "pro",
            "subscription_status": "active",
            "created_at": (now - timedelta(days=60)).isoformat(),
        })

        # Últimas 4 semanas (días 28-7 atrás): 40 leads = 10/semana
        leads_old = []
        for i in range(40):
            leads_old.append({
                "tenant_id": tid,
                "phone": f"549{tag}{i:04d}",
                "status": "new",
                "created_at": (now - timedelta(days=(7 + (i % 20)))).isoformat(),
            })
        # Esta semana (0-7d): solo 2 leads → ratio 2/10 = 20% (<50% → churn risk)
        for i in range(2):
            leads_old.append({
                "tenant_id": tid,
                "phone": f"549{tag}W{i}",
                "status": "new",
                "created_at": (now - timedelta(days=2)).isoformat(),
            })
        await mdb.leads.insert_many(leads_old)

        try:
            os.environ["SUPERADMIN_EMAIL"] = "test@nowhere.local"
            tasks = ScheduledTasks(mdb, MockEmail())
            await tasks._send_admin_report()
            assert len(captured) >= 1
            stats = captured[0]["stats"]
            assert "churn_risk" in stats
            our = [c for c in stats["churn_risk"] if c["tenant_id"] == tid]
            assert len(our) == 1, f"Expected churn_risk entry for {tid}, got: {stats['churn_risk']}"
            entry = our[0]
            assert entry["leads_this_week"] == 2
            assert entry["avg_weekly"] == 10.0
            assert entry["drop_pct"] >= 50
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.leads.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())


def test_churn_risk_skips_new_tenants(db):
    """Tenant creado hace <28 días no entra en churn_risk (no hay baseline)."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from scheduler import ScheduledTasks
        captured = []

        class MockEmail:
            async def send_admin_weekly_report(self, **kw):
                captured.append(kw)
                return True

        tag = uuid.uuid4().hex[:6]
        tid = f"new-{tag}"
        now = datetime.now(timezone.utc)

        # Tenant nuevo (10 días)
        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"New {tag}",
            "active": True,
            "subscription_plan": "pro",
            "subscription_status": "active",
            "created_at": (now - timedelta(days=10)).isoformat(),
        })
        # Leads solo hace 5 días (caída aparente pero sin baseline)
        for i in range(3):
            await mdb.leads.insert_one({
                "tenant_id": tid,
                "phone": f"549{tag}{i}",
                "status": "new",
                "created_at": (now - timedelta(days=5)).isoformat(),
            })

        try:
            os.environ["SUPERADMIN_EMAIL"] = "test@nowhere.local"
            tasks = ScheduledTasks(mdb, MockEmail())
            await tasks._send_admin_report()
            stats = captured[0]["stats"]
            our = [c for c in stats["churn_risk"] if c["tenant_id"] == tid]
            assert len(our) == 0, "Tenant nuevo no debería entrar en churn_risk"
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.leads.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())


def test_churn_risk_skips_low_baseline(db):
    """Tenant con baseline <5 leads/sem no se incluye (ruido estadístico)."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from scheduler import ScheduledTasks
        captured = []

        class MockEmail:
            async def send_admin_weekly_report(self, **kw):
                captured.append(kw)
                return True

        tag = uuid.uuid4().hex[:6]
        tid = f"low-{tag}"
        now = datetime.now(timezone.utc)

        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"LowBase {tag}",
            "active": True,
            "subscription_plan": "pro",
            "subscription_status": "active",
            "created_at": (now - timedelta(days=60)).isoformat(),
        })
        # Baseline: 8 leads en 4 semanas = 2/sem (<5)
        for i in range(8):
            await mdb.leads.insert_one({
                "tenant_id": tid,
                "phone": f"549{tag}L{i}",
                "status": "new",
                "created_at": (now - timedelta(days=(7 + (i % 20)))).isoformat(),
            })

        try:
            os.environ["SUPERADMIN_EMAIL"] = "test@nowhere.local"
            tasks = ScheduledTasks(mdb, MockEmail())
            await tasks._send_admin_report()
            stats = captured[0]["stats"]
            our = [c for c in stats["churn_risk"] if c["tenant_id"] == tid]
            assert len(our) == 0, "Baseline bajo no debería dispararse"
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.leads.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())
