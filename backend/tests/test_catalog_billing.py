"""
Backend tests for InmoBot SaaS - Iteration 4:
- Catalog CRUD using product_id UUID (new)
- Catalog backfill: productos viejos sin product_id reciben uno via GET
- Cross-tenant validation en POST /catalog/send/{phone} (new)
- Regression: endpoints tras refactor a /app/backend/routers/
  (catalog.py, billing.py). Otros endpoints (leads, usage, templates,
  flow/config, agents) siguen accesibles.
- Billing overage (superadmin / 403 para tenant admin)
- Scheduler: bill_monthly_overage existe
"""
import os
import uuid
import asyncio
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "inmobot_db")

TENANT_EMAIL = "demo@inmobot.com"
TENANT_PASS = "Demo123!"
SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASS = "Admin123!"

UNIQ = uuid.uuid4().hex[:8]
PROD_NAME = f"TEST_Producto_{UNIQ}"
PROD_NAME_2 = f"TEST_Producto2_{UNIQ}"


# ---------- Helpers ----------

def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login fail {email}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token: {data}"
    return token, data


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(scope="module")
def tenant_token():
    t, _ = _login(TENANT_EMAIL, TENANT_PASS)
    return t


@pytest.fixture(scope="module")
def super_token():
    t, _ = _login(SUPER_EMAIL, SUPER_PASS)
    return t


@pytest.fixture(scope="module")
def tenant_headers(tenant_token):
    return {"Authorization": f"Bearer {tenant_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def super_headers(super_token):
    return {"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"}


# ---------- Auth ----------

def test_login_tenant_admin():
    token, data = _login(TENANT_EMAIL, TENANT_PASS)
    user = data.get("user") or data
    assert user.get("tenant_id") == "demo-inmobiliaria" or data.get("tenant_id") == "demo-inmobiliaria"


def test_login_superadmin():
    token, data = _login(SUPER_EMAIL, SUPER_PASS)
    user = data.get("user") or data
    assert user.get("role") == "superadmin" or data.get("role") == "superadmin"


# ---------- Catalog: product_id UUID (NEW) ----------

def test_catalog_create_returns_product_id(tenant_headers):
    payload = {
        "name": PROD_NAME, "description": "Dep test", "price": 120000,
        "currency": "USD", "category": "TEST_Departamentos",
        "image_url": "https://example.com/img.jpg",
    }
    r = requests.post(f"{API}/catalog", json=payload, headers=tenant_headers, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "product_id" in data and data["product_id"]
    # UUID-like
    assert len(data["product_id"]) >= 32
    assert data["tenant_id"] == "demo-inmobiliaria"
    assert data["active"] is True
    # save for later
    pytest.PROD_ID = data["product_id"]


def test_catalog_get_includes_product_id(tenant_headers):
    r = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    # Todos deben tener product_id (backfill para viejos)
    for p in items:
        assert p.get("product_id"), f"Producto sin product_id: {p.get('name')}"


def test_catalog_backfill_legacy_product(tenant_headers):
    """Insert producto sin product_id directo a Mongo, GET debe asignar uno."""
    legacy_name = f"TEST_Legacy_{UNIQ}"
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.products.insert_one({
        "tenant_id": "demo-inmobiliaria",
        "name": legacy_name,
        "description": "sin product_id",
        "price": 1, "currency": "USD", "category": "TEST_X",
        "active": True, "created_at": "2025-01-01T00:00:00",
    })
    try:
        r = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
        assert r.status_code == 200
        item = next((p for p in r.json() if p["name"] == legacy_name), None)
        assert item is not None, "legacy product no aparece"
        assert item.get("product_id"), "backfill no funcionó"

        doc = db.products.find_one({"name": legacy_name})
        assert doc.get("product_id") == item["product_id"], "product_id no persistido"
    finally:
        db.products.delete_many({"name": legacy_name})
        client.close()


def test_catalog_update_by_product_id(tenant_headers):
    pid = getattr(pytest, "PROD_ID", None)
    assert pid, "PROD_ID not set"
    r = requests.put(
        f"{API}/catalog/{pid}",
        json={"price": 150000, "description": "Updated via UUID"},
        headers=tenant_headers, timeout=10,
    )
    assert r.status_code == 200, r.text
    r2 = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    item = next((p for p in r2.json() if p.get("product_id") == pid), None)
    assert item is not None
    assert item["price"] == 150000
    assert item["description"] == "Updated via UUID"


def test_catalog_update_bad_uuid_returns_404(tenant_headers):
    r = requests.put(
        f"{API}/catalog/non-existent-uuid-{UNIQ}",
        json={"price": 1}, headers=tenant_headers, timeout=10,
    )
    assert r.status_code == 404


def test_catalog_delete_by_product_id(tenant_headers):
    # Crear uno para borrar
    r = requests.post(f"{API}/catalog", json={
        "name": PROD_NAME_2, "description": "del", "price": 10,
        "currency": "USD", "category": "TEST_Departamentos",
    }, headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    pid2 = r.json()["product_id"]

    r2 = requests.delete(f"{API}/catalog/{pid2}", headers=tenant_headers, timeout=10)
    assert r2.status_code == 200, r2.text

    r3 = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    ids = [p.get("product_id") for p in r3.json()]
    assert pid2 not in ids


def test_catalog_delete_bad_uuid_returns_404(tenant_headers):
    r = requests.delete(f"{API}/catalog/bad-uuid-{UNIQ}", headers=tenant_headers, timeout=10)
    assert r.status_code == 404


# ---------- Cross-tenant send validation (NEW) ----------

def test_catalog_send_blocks_cross_tenant_phone(tenant_headers):
    """Phone registrado en otro tenant -> 403."""
    foreign_phone = f"555999{UNIQ[:4]}"
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.leads.insert_one({
        "tenant_id": "OTRO_TENANT_TEST",
        "phone": foreign_phone,
        "name": "foreign lead",
        "created_at": "2025-01-01T00:00:00",
    })
    try:
        r = requests.post(
            f"{API}/catalog/send/{foreign_phone}",
            json={},
            headers=tenant_headers, timeout=15,
        )
        assert r.status_code == 403, f"Se esperaba 403 cross-tenant, got {r.status_code}: {r.text}"
        assert "tenant" in r.text.lower()
    finally:
        db.leads.delete_many({"phone": foreign_phone})
        client.close()


def test_catalog_send_allows_own_tenant_phone(tenant_headers):
    """Phone registrado en propio tenant -> permite envío (graceful sin WA)."""
    own_phone = f"549111{UNIQ[:4]}"
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.leads.insert_one({
        "tenant_id": "demo-inmobiliaria",
        "phone": own_phone,
        "name": "own lead test",
        "created_at": "2025-01-01T00:00:00",
    })
    try:
        r = requests.post(
            f"{API}/catalog/send/{own_phone}",
            json={},
            headers=tenant_headers, timeout=15,
        )
        assert r.status_code != 403, f"own-tenant phone bloqueado erroneamente: {r.text}"
        assert r.status_code in (200, 404), r.text
    finally:
        db.leads.delete_many({"phone": own_phone})
        client.close()


def test_catalog_send_allows_unknown_phone(tenant_headers):
    """Phone no existe en ningún tenant -> permite envío."""
    unknown_phone = f"5490000{UNIQ[:4]}"
    r = requests.post(
        f"{API}/catalog/send/{unknown_phone}",
        json={},
        headers=tenant_headers, timeout=15,
    )
    assert r.status_code != 403, f"unknown phone fue bloqueado, body: {r.text}"
    assert r.status_code in (200, 404), r.text


# ---------- Other catalog endpoints (regression) ----------

def test_catalog_categories(tenant_headers):
    r = requests.get(f"{API}/catalog/categories", headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    cats = r.json()
    assert isinstance(cats, list)


def test_catalog_filter_by_category(tenant_headers):
    r = requests.get(f"{API}/catalog?category=TEST_Departamentos", headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    for p in r.json():
        assert p["category"] == "TEST_Departamentos"


def test_catalog_requires_auth():
    r = requests.get(f"{API}/catalog", timeout=10)
    assert r.status_code in (401, 403)


def test_tenant_isolation_responses_only_own_tenant(tenant_headers):
    r = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    for p in r.json():
        assert p.get("tenant_id") == "demo-inmobiliaria"


# ---------- Router refactor regression ----------

def test_billing_plans_public():
    r = requests.get(f"{API}/plans", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "pro" in data or len(data) > 0


def test_billing_get_info_admin(tenant_headers):
    r = requests.get(f"{API}/billing", headers=tenant_headers, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict)


def test_billing_transactions_admin(tenant_headers):
    r = requests.get(f"{API}/transactions", headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_billing_subscribe_requires_plan_id(tenant_headers):
    r = requests.post(f"{API}/billing/subscribe", json={}, headers=tenant_headers, timeout=10)
    assert r.status_code == 400


def test_billing_cancel_graceful(tenant_headers):
    r = requests.post(f"{API}/billing/cancel", headers=tenant_headers, timeout=15)
    # Sin Stripe: 200 o 400 graceful; no 500
    assert r.status_code in (200, 400, 404), r.text


def test_webhook_stripe_endpoint_exists():
    r = requests.post(f"{API}/webhook/stripe", data="{}", timeout=10)
    # sin firma -> 200 con error string en body (manejado graceful)
    assert r.status_code in (200, 400), r.text


def test_non_moved_endpoints_still_work(tenant_headers):
    """Verificar que endpoints NO movidos siguen funcionando."""
    for path in ("/leads", "/usage", "/templates", "/flow/config", "/agents"):
        r = requests.get(f"{API}{path}", headers=tenant_headers, timeout=10)
        assert r.status_code in (200, 404), f"{path} roto: {r.status_code} {r.text[:200]}"
        # 404 sería aceptable solo si el endpoint no existe en este build
        if r.status_code == 200:
            body = r.json()
            assert isinstance(body, (list, dict))


# ---------- Billing overage ----------

def test_overage_requires_superadmin(tenant_headers):
    r = requests.post(f"{API}/billing/bill-overage", json={}, headers=tenant_headers, timeout=15)
    assert r.status_code == 403


def test_overage_superadmin_no_stripe_graceful(super_headers):
    r = requests.post(f"{API}/billing/bill-overage", json={}, headers=super_headers, timeout=20)
    assert r.status_code in (200, 400), r.text
    if r.status_code == 200:
        assert isinstance(r.json(), (dict, list))


def test_overage_specific_tenant_no_stripe(super_headers):
    r = requests.post(
        f"{API}/billing/bill-overage",
        json={"tenant_id": "demo-inmobiliaria"},
        headers=super_headers, timeout=20,
    )
    assert r.status_code in (200, 400), r.text


# ---------- Scheduler unit ----------

def test_scheduler_has_bill_monthly_overage():
    from scheduler import ScheduledTasks
    assert hasattr(ScheduledTasks, "bill_monthly_overage")


def test_scheduler_accepts_payment_service():
    from scheduler import ScheduledTasks
    import inspect
    sig = inspect.signature(ScheduledTasks.__init__)
    assert "payment_service" in sig.parameters


# ---------- Cleanup ----------

def test_zz_cleanup(tenant_headers):
    """Wipe TEST_ prefixed data."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.products.delete_many({"name": {"$regex": "^TEST_"}})
    db.leads.delete_many({"tenant_id": "OTRO_TENANT_TEST"})
    client.close()
