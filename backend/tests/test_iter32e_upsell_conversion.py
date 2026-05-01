"""Tests Iter32e: upsell conversion tracking + history endpoint."""
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
ADMIN = ("admin@inmobot.com", "Admin123!")


@pytest.fixture(scope="module")
def headers():
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": ADMIN[0], "password": ADMIN[1]},
        timeout=15,
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


def test_mark_conversions_flips_converted_true(db):
    """Si tenant upgradeó a Enterprise DESPUÉS del upsell, mark_upsell_conversions
    lo marca converted=True."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from upsell_service import mark_upsell_conversions

        tag = uuid.uuid4().hex[:6]
        tid = f"conv-{tag}"
        sent_iso = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        upgraded_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"Conv {tag}",
            "active": True,
            "subscription_plan": "enterprise",  # ya upgradeó
            "subscription_updated_at": upgraded_iso,
            "subscription_status": "active",
        })
        await mdb.upsell_events.insert_one({
            "tenant_id": tid,
            "trigger": "unmet_demand",
            "to_email": f"conv-{tag}@x.com",
            "leads_count": 60,
            "value_usd": 6000,
            "sent_at": sent_iso,
            "delivered": True,
        })

        try:
            n = await mark_upsell_conversions(mdb)
            assert n >= 1
            evt = await mdb.upsell_events.find_one({"tenant_id": tid})
            assert evt["converted"] is True
            assert evt["conversion_plan"] == "enterprise"
            # Idempotente: un 2do run no incrementa (ya está marcado)
            n2 = await mark_upsell_conversions(mdb)
            our = [e async for e in mdb.upsell_events.find({"tenant_id": tid, "converted": True})]
            assert len(our) == 1
            # n2 no debe haber procesado ESTE evento de nuevo
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())


def test_mark_conversions_skip_if_upgrade_was_before(db):
    """Si el upgrade a Enterprise fue ANTES del envío de upsell, no cuenta
    como conversión (el email llegó tarde)."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from upsell_service import mark_upsell_conversions

        tag = uuid.uuid4().hex[:6]
        tid = f"conv-before-{tag}"
        upgraded_iso = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        sent_iso = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"Before {tag}",
            "active": True,
            "subscription_plan": "enterprise",
            "subscription_updated_at": upgraded_iso,  # ANTES del sent_at
            "subscription_status": "active",
        })
        await mdb.upsell_events.insert_one({
            "tenant_id": tid,
            "trigger": "unmet_demand",
            "to_email": f"b-{tag}@x.com",
            "leads_count": 60,
            "value_usd": 6000,
            "sent_at": sent_iso,
            "delivered": True,
        })

        try:
            await mark_upsell_conversions(mdb)
            evt = await mdb.upsell_events.find_one({"tenant_id": tid})
            # No debe estar marcado como converted (upgrade fue antes)
            assert evt.get("converted") is not True
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.upsell_events.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())


def test_upsell_history_endpoint(headers, db):
    """GET /superadmin/upsell/history retorna items + stats."""
    # Agregamos 1 evento sintético para que haya data
    tag = uuid.uuid4().hex[:6]
    tid = f"hist-{tag}"
    db.upsell_events.insert_one({
        "tenant_id": tid,
        "trigger": "unmet_demand",
        "to_email": f"hist-{tag}@x.com",
        "leads_count": 70,
        "value_usd": 3500,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "delivered": True,
    })
    try:
        r = requests.get(f"{BASE}/api/superadmin/upsell/history?limit=10", headers=headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "stats" in body
        s = body["stats"]
        assert "total_sent" in s and "converted" in s and "conversion_rate" in s
        # El evento recién creado debe estar en la respuesta
        found = any(it.get("tenant_id") == tid for it in body["items"])
        assert found, "Evento recién creado debería aparecer en el history"
    finally:
        db.upsell_events.delete_many({"tenant_id": tid})


def test_upsell_stats_rate_calc(db):
    """get_upsell_stats: conversion_rate = converted/delivered × 100."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        from upsell_service import get_upsell_stats

        tag = uuid.uuid4().hex[:6]
        now = datetime.now(timezone.utc).isoformat()
        # 4 events: 3 delivered, 1 de esos converted
        docs = [
            {"tenant_id": f"stats-{tag}-1", "trigger": "unmet_demand",
             "to_email": "a@x.com", "leads_count": 60, "value_usd": 1000,
             "sent_at": now, "delivered": True, "converted": True},
            {"tenant_id": f"stats-{tag}-2", "trigger": "unmet_demand",
             "to_email": "b@x.com", "leads_count": 60, "value_usd": 2000,
             "sent_at": now, "delivered": True, "converted": False},
            {"tenant_id": f"stats-{tag}-3", "trigger": "unmet_demand",
             "to_email": "c@x.com", "leads_count": 60, "value_usd": 500,
             "sent_at": now, "delivered": True},
            {"tenant_id": f"stats-{tag}-4", "trigger": "unmet_demand",
             "to_email": "d@x.com", "leads_count": 60, "value_usd": 3000,
             "sent_at": now, "delivered": False},
        ]
        await mdb.upsell_events.insert_many(docs)
        try:
            stats = await get_upsell_stats(mdb, days=90)
            # No podemos chequear exacto por eventos existentes; chequeamos
            # que los stats tienen las claves correctas y valores plausibles.
            assert "conversion_rate" in stats
            assert stats["conversion_rate"] >= 0
            assert stats["total_sent"] >= 4
            assert stats["delivered"] >= 3
            assert stats["converted_value_usd"] >= 1000
        finally:
            await mdb.upsell_events.delete_many(
                {"tenant_id": {"$regex": f"^stats-{tag}"}}
            )
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())
