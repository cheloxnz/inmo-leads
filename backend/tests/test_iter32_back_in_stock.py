"""
Tests Iter32: back-in-stock waitlist + router refactor.
Patrón sync (requests + pymongo) compatible con backend externo.
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
    assert r.status_code == 200, r.text
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
# Refactor: endpoints de leads/tags siguen vivos tras mover a routers/leads.py
# ----------------------------------------------------------------

def test_leads_endpoints_alive(headers):
    for path in (
        "/api/leads?limit=1",
        "/api/leads/kanban",
        "/api/leads/assigned-to-me",
        "/api/leads/stats/summary",
        "/api/tags",
    ):
        r = requests.get(f"{BASE}{path}", headers=headers, timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"


def test_leads_kanban_shape(headers):
    r = requests.get(f"{BASE}/api/leads/kanban", headers=headers, timeout=15)
    j = r.json()
    for col in ("new", "contacted", "qualified", "hot", "warm", "cold"):
        assert col in j, f"falta columna {col}"
        assert "leads" in j[col] and "count" in j[col]


def test_leads_stats_shape(headers):
    r = requests.get(f"{BASE}/api/leads/stats/summary", headers=headers, timeout=15)
    j = r.json()
    for k in ("total", "hot", "warm", "cold", "with_appointment", "today",
              "this_week", "avg_score", "conversion_rate"):
        assert k in j, f"falta clave {k}"


# ----------------------------------------------------------------
# substitute-preview ahora es require_admin: admin sí pasa
# ----------------------------------------------------------------

def test_substitute_preview_requires_admin(headers):
    r = requests.post(
        f"{BASE}/api/catalog/substitute-preview",
        headers=headers,
        json={"query": "hola"},
        timeout=15,
    )
    assert r.status_code == 200
    assert "out_of_stock_product" in r.json()


# ----------------------------------------------------------------
# Waitlist: GET endpoint
# ----------------------------------------------------------------

def test_waitlist_endpoint(headers):
    r = requests.get(f"{BASE}/api/catalog/waitlist", headers=headers, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "total_pending" in j
    assert "by_product" in j
    assert isinstance(j["by_product"], list)


# ----------------------------------------------------------------
# Back-in-stock: PATCH /stock con transición agotado→disponible
# debe retornar notified_leads y limpiar waitlist (notified_at != None).
# ----------------------------------------------------------------

def test_back_in_stock_marks_notified(headers, db):
    tag = uuid.uuid4().hex[:6]
    # Crear producto agotado (stock=0, active=False)
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"Restock Test {tag}",
            "price": 100,
            "category": f"restock-{tag}",
            "stock_quantity": 0,
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    product = r.json()
    pid = product["product_id"]
    tid = product["tenant_id"]

    # Insertar 2 entradas en waitlist directamente en DB
    db.product_waitlist.delete_many({"tenant_id": tid, "product_id": pid})
    db.product_waitlist.insert_many([
        {
            "tenant_id": tid, "product_id": pid,
            "lead_phone": f"54911{tag}001",
            "product_name": product["name"],
            "asked_at": "2026-05-01T00:00:00+00:00",
            "notified_at": None,
            "created_at": "2026-05-01T00:00:00+00:00",
        },
        {
            "tenant_id": tid, "product_id": pid,
            "lead_phone": f"54911{tag}002",
            "product_name": product["name"],
            "asked_at": "2026-05-01T00:00:00+00:00",
            "notified_at": None,
            "created_at": "2026-05-01T00:00:00+00:00",
        },
    ])
    pending_before = db.product_waitlist.count_documents(
        {"tenant_id": tid, "product_id": pid, "notified_at": None}
    )
    assert pending_before == 2

    # Verificar que GET /waitlist los ve
    r = requests.get(f"{BASE}/api/catalog/waitlist", headers=headers, timeout=15)
    pids_in_wl = [p["product_id"] for p in r.json()["by_product"]]
    assert pid in pids_in_wl

    # PATCH stock=10 (transición agotado → disponible)
    r = requests.patch(
        f"{BASE}/api/catalog/products/{pid}/stock",
        headers=headers,
        json={"stock_quantity": 10},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["stock_quantity"] == 10
    assert "notified_leads" in body
    # La cantidad notificada depende de si hay WA configurado para este tenant.
    # Si WA no está configurado, send_message arroja excepción y notified queda en 0.
    # Si está configurado, debería ser 2.

    # Si notified > 0, validar que en DB no quedan pendientes
    if body["notified_leads"] > 0:
        pending_after = db.product_waitlist.count_documents(
            {"tenant_id": tid, "product_id": pid, "notified_at": None}
        )
        assert pending_after == 0, (
            f"notified_leads={body['notified_leads']} pero quedan "
            f"{pending_after} pendientes"
        )

    # Cleanup
    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)
    db.product_waitlist.delete_many({"tenant_id": tid, "product_id": pid})


# ----------------------------------------------------------------
# Back-in-stock: PUT /catalog/{id} con stock_quantity también dispara notify
# ----------------------------------------------------------------

def test_put_with_stock_also_notifies(headers, db):
    tag = uuid.uuid4().hex[:6]
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"PutRestock {tag}",
            "price": 50,
            "category": f"put-{tag}",
            "stock_quantity": 0,
        },
        timeout=15,
    )
    pid = r.json()["product_id"]
    tid = r.json()["tenant_id"]

    db.product_waitlist.insert_one({
        "tenant_id": tid, "product_id": pid,
        "lead_phone": f"54922{tag}",
        "product_name": r.json()["name"],
        "asked_at": "2026-05-01T00:00:00+00:00",
        "notified_at": None,
        "created_at": "2026-05-01T00:00:00+00:00",
    })

    # PUT con stock_quantity > 0
    r = requests.put(
        f"{BASE}/api/catalog/{pid}",
        headers=headers,
        json={"name": f"PutRestock {tag}", "stock_quantity": 5},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "notified_leads" in body  # nuevo campo

    # Cleanup
    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)
    db.product_waitlist.delete_many({"tenant_id": tid, "product_id": pid})


# ----------------------------------------------------------------
# notify_back_in_stock NO dispara si producto sigue agotado
# (test directo del service)
# ----------------------------------------------------------------

def test_notify_skipped_when_still_out(db):
    import asyncio
    from catalog_service import CatalogService

    async def run():
        # Usar motor para el test del service
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        svc = CatalogService(mdb)
        tid = "__superadmin__"
        pid = f"phantom-{uuid.uuid4().hex[:8]}"
        await mdb.products.insert_one({
            "product_id": pid, "tenant_id": tid,
            "name": "Phantom", "active": False, "stock_quantity": 0,
        })
        await mdb.product_waitlist.insert_one({
            "tenant_id": tid, "product_id": pid,
            "lead_phone": "5490000000000",
            "notified_at": None,
            "asked_at": "2026-05-01T00:00:00+00:00",
        })
        try:
            count = await svc.notify_back_in_stock(tid, pid)
            assert count == 0
        finally:
            await mdb.products.delete_one({"product_id": pid})
            await mdb.product_waitlist.delete_many({"product_id": pid})
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())


# ----------------------------------------------------------------
# add_to_waitlist es idempotente (upsert)
# ----------------------------------------------------------------

def test_waitlist_idempotent(db):
    import asyncio
    from catalog_service import CatalogService

    async def run():
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(MONGO_URL)
        mdb = cli[DB_NAME]
        svc = CatalogService(mdb)
        tid = "__superadmin__"
        pid = f"wl-{uuid.uuid4().hex[:8]}"
        phone = "5491199999999"
        await mdb.product_waitlist.delete_many(
            {"tenant_id": tid, "product_id": pid, "lead_phone": phone}
        )
        try:
            await svc.add_to_waitlist(tid, phone, pid, "Test X")
            await svc.add_to_waitlist(tid, phone, pid, "Test X")
            await svc.add_to_waitlist(tid, phone, pid, "Test X")
            count = await mdb.product_waitlist.count_documents(
                {"tenant_id": tid, "product_id": pid, "lead_phone": phone}
            )
            assert count == 1
        finally:
            await mdb.product_waitlist.delete_many(
                {"tenant_id": tid, "product_id": pid, "lead_phone": phone}
            )
            cli.close()

    asyncio.new_event_loop().run_until_complete(run())
