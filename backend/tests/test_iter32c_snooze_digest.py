"""
Tests Iter32c: snooze unmet-demand + weekly digest enriched con unmet_top.
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
ADMIN = ("admin@inmobot.com", "Admin123!")


def _login(email, pwd):
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": pwd},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ----------------------------------------------------------------
# Snooze: producto silenciado desaparece del top y vuelve al expirar
# ----------------------------------------------------------------

def test_snooze_hides_product(headers, db):
    tag = uuid.uuid4().hex[:6]
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"SnoozeTest {tag}",
            "price": 500,
            "category": f"snz-{tag}",
            "stock_quantity": 0,
        },
        timeout=15,
    )
    pid = r.json()["product_id"]
    tid = r.json()["tenant_id"]
    db.product_waitlist.insert_many([
        {
            "tenant_id": tid, "product_id": pid,
            "lead_phone": f"54977{tag}{i}",
            "product_name": r.json()["name"],
            "asked_at": "2026-05-01T00:00:00+00:00",
            "notified_at": None,
            "created_at": "2026-05-01T00:00:00+00:00",
        } for i in range(2)
    ])

    # 1. Aparece en el top
    r = requests.get(f"{BASE}/api/superadmin/unmet-demand?limit=20", headers=headers, timeout=15)
    body = r.json()
    found = any(p["product_id"] == pid for p in body["top_products"])
    assert found, "El producto debería aparecer antes de snooze"

    # 2. Snooze por 7 días
    r = requests.post(
        f"{BASE}/api/superadmin/unmet-demand/snooze",
        headers=headers,
        json={"tenant_id": tid, "product_id": pid, "days": 7},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # 3. Ya no aparece en el top + snoozed_count >= 1
    r = requests.get(f"{BASE}/api/superadmin/unmet-demand?limit=20", headers=headers, timeout=15)
    body = r.json()
    found = any(p["product_id"] == pid for p in body["top_products"])
    assert not found, "Producto debería estar oculto tras snooze"
    assert body["snoozed_count"] >= 1

    # 4. Unsnooze
    r = requests.request(
        "DELETE",
        f"{BASE}/api/superadmin/unmet-demand/snooze",
        headers=headers,
        json={"tenant_id": tid, "product_id": pid},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["removed"] == 1

    # 5. Vuelve a aparecer
    r = requests.get(f"{BASE}/api/superadmin/unmet-demand?limit=20", headers=headers, timeout=15)
    body = r.json()
    found = any(p["product_id"] == pid for p in body["top_products"])
    assert found, "Producto debería volver al top tras unsnooze"

    # Cleanup
    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)
    db.product_waitlist.delete_many({"tenant_id": tid, "product_id": pid})
    db.unmet_demand_snooze.delete_many({"tenant_id": tid, "product_id": pid})


def test_snooze_validates_input(headers):
    # Body incompleto
    r = requests.post(
        f"{BASE}/api/superadmin/unmet-demand/snooze",
        headers=headers,
        json={"tenant_id": "x"},
        timeout=15,
    )
    assert r.status_code == 400

    # days fuera de rango
    r = requests.post(
        f"{BASE}/api/superadmin/unmet-demand/snooze",
        headers=headers,
        json={"tenant_id": "x", "product_id": "y", "days": 500},
        timeout=15,
    )
    assert r.status_code == 400


# ----------------------------------------------------------------
# Weekly digest: _send_digest_to_all_tenants incluye unmet_top
# ----------------------------------------------------------------

def test_weekly_digest_includes_unmet_top(db):
    """Test directo del scheduler: stats.unmet_top debe poblarse para tenants
    con productos agotados + waitlist."""
    import asyncio
    import os as _os
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        from scheduler import ScheduledTasks
        from email_service import EmailService

        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]

        # Mock email_service para capturar el stats que recibe
        captured = []

        class _MockEmail:
            async def send_weekly_digest(self, **kw):
                captured.append(kw)
                return True

        # Crear tenant, agente admin, producto agotado y 2 leads en waitlist
        tag = uuid.uuid4().hex[:6]
        tid = f"digest-test-{tag}"
        await mdb.tenants.insert_one({
            "tenant_id": tid,
            "business_name": f"Digest Biz {tag}",
            "name": f"Digest Biz {tag}",
            "active": True,
            "subscription_status": "trial",
        })
        await mdb.agents.insert_one({
            "tenant_id": tid,
            "email": f"digest-{tag}@example.com",
            "role": "admin",
            "active": True,
        })
        pid = f"dprod-{tag}"
        await mdb.products.insert_one({
            "product_id": pid,
            "tenant_id": tid,
            "name": f"DigestProd {tag}",
            "active": False,
            "stock_quantity": 0,
            "price": 250,
        })
        await mdb.product_waitlist.insert_many([
            {
                "tenant_id": tid, "product_id": pid,
                "lead_phone": f"5499{tag}{i}",
                "product_name": f"DigestProd {tag}",
                "asked_at": "2026-05-01T00:00:00+00:00",
                "notified_at": None,
                "created_at": "2026-05-01T00:00:00+00:00",
            } for i in range(3)
        ])

        try:
            tasks = ScheduledTasks(mdb, _MockEmail())
            sent = await tasks._send_digest_to_all_tenants()
            # Buscar nuestro tenant en captured
            ours = [c for c in captured if f"Digest Biz {tag}" == c.get("business_name")]
            assert len(ours) >= 1, f"No se llamó send_weekly_digest para {tid}. Captured: {len(captured)} entries"
            stats = ours[0]["stats"]
            assert "unmet_top" in stats
            assert len(stats["unmet_top"]) >= 1
            top = stats["unmet_top"][0]
            assert top["leads_count"] == 3
            assert "DigestProd" in top["name"]
            assert top["price"] == 250
        finally:
            await mdb.tenants.delete_one({"tenant_id": tid})
            await mdb.agents.delete_many({"tenant_id": tid})
            await mdb.products.delete_one({"product_id": pid})
            await mdb.product_waitlist.delete_many({"tenant_id": tid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())
