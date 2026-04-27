"""
Backend tests for InmoBot SaaS:
- Catalog CRUD (per-tenant)
- Catalog send to WhatsApp (graceful when WA not configured)
- Catalog tenant isolation
- Bot generic_flow catalog integration (unit-level)
- Billing overage endpoint (superadmin / 403 for tenant admin)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inmobot-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TENANT_EMAIL = "demo@inmobot.com"
TENANT_PASS = "Demo123!"
SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASS = "Admin123!"

UNIQ = uuid.uuid4().hex[:8]
PROD_NAME = f"TEST_Producto_{UNIQ}"
PROD_NAME_2 = f"TEST_Producto2_{UNIQ}"


# ---------- Auth helpers ----------

def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login fail {email}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token, data


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


# ---------- Auth basic ----------

def test_login_tenant_admin():
    token, data = _login(TENANT_EMAIL, TENANT_PASS)
    assert token
    user = data.get("user") or data
    # Should belong to demo-inmobiliaria tenant
    assert user.get("tenant_id") == "demo-inmobiliaria" or data.get("tenant_id") == "demo-inmobiliaria"


def test_login_superadmin():
    token, data = _login(SUPER_EMAIL, SUPER_PASS)
    assert token
    user = data.get("user") or data
    assert user.get("role") == "superadmin" or data.get("role") == "superadmin"


# ---------- Catalog CRUD ----------

def test_catalog_list_empty_or_existing(tenant_headers):
    r = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_catalog_create_product(tenant_headers):
    payload = {
        "name": PROD_NAME,
        "description": "Departamento 2 amb test",
        "price": 120000,
        "currency": "USD",
        "category": "TEST_Departamentos",
        "image_url": "https://example.com/img.jpg",
    }
    r = requests.post(f"{API}/catalog", json=payload, headers=tenant_headers, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == PROD_NAME
    assert data["tenant_id"] == "demo-inmobiliaria"
    assert data["price"] == 120000
    assert data["active"] is True
    # GET should now list it
    r2 = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    names = [p["name"] for p in r2.json()]
    assert PROD_NAME in names


def test_catalog_categories(tenant_headers):
    # ensure product exists
    requests.post(f"{API}/catalog", json={
        "name": PROD_NAME_2, "description": "x", "price": 50,
        "currency": "USD", "category": "TEST_Departamentos"
    }, headers=tenant_headers, timeout=10)

    r = requests.get(f"{API}/catalog/categories", headers=tenant_headers, timeout=10)
    assert r.status_code == 200, r.text
    cats = r.json()
    assert isinstance(cats, list)
    assert "TEST_Departamentos" in cats


def test_catalog_filter_by_category(tenant_headers):
    r = requests.get(f"{API}/catalog?category=TEST_Departamentos", headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    data = r.json()
    for p in data:
        assert p["category"] == "TEST_Departamentos"


def test_catalog_update_product(tenant_headers):
    r = requests.put(
        f"{API}/catalog/{PROD_NAME}",
        json={"price": 150000, "description": "Updated desc"},
        headers=tenant_headers, timeout=10,
    )
    assert r.status_code == 200, r.text
    # Verify persisted
    r2 = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    item = next((p for p in r2.json() if p["name"] == PROD_NAME), None)
    assert item is not None
    assert item["price"] == 150000
    assert item["description"] == "Updated desc"


def test_catalog_update_not_found(tenant_headers):
    r = requests.put(
        f"{API}/catalog/__no_existe_{UNIQ}",
        json={"price": 1}, headers=tenant_headers, timeout=10,
    )
    assert r.status_code == 404


def test_catalog_delete_product(tenant_headers):
    r = requests.delete(f"{API}/catalog/{PROD_NAME_2}", headers=tenant_headers, timeout=10)
    assert r.status_code == 200, r.text
    # GET (active_only by default) should not list it
    r2 = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    names = [p["name"] for p in r2.json()]
    assert PROD_NAME_2 not in names


def test_catalog_requires_auth():
    r = requests.get(f"{API}/catalog", timeout=10)
    assert r.status_code in (401, 403)


# ---------- Catalog Send (WhatsApp not configured -> graceful) ----------

def test_catalog_send_when_wa_not_configured(tenant_headers):
    """Endpoint must not 500. Either returns 200 with success=False/error info or
    returns a known WA-not-configured signal. /app brief says expected behaviour
    is graceful 'WhatsApp no configurado'."""
    r = requests.post(
        f"{API}/catalog/send/+5491100000000",
        json={"product_name": PROD_NAME},
        headers=tenant_headers, timeout=15,
    )
    # acceptable: 200 with graceful payload, OR 400 telling WhatsApp not configured.
    assert r.status_code in (200, 400, 503), f"Unexpected {r.status_code}: {r.text}"
    body = r.text.lower()
    if r.status_code == 200:
        # In dev WA returns success=False
        data = r.json()
        # Must contain result info; should NOT raise 500
        assert "result" in data or "message" in data
    else:
        assert "whatsapp" in body or "configurado" in body or "configured" in body


def test_catalog_send_full_catalog_no_wa(tenant_headers):
    r = requests.post(
        f"{API}/catalog/send/+5491100000000",
        json={},  # no product_name -> sends list/buttons
        headers=tenant_headers, timeout=15,
    )
    assert r.status_code in (200, 400, 404, 503), f"Unexpected {r.status_code}: {r.text}"


# ---------- Tenant isolation ----------

def test_tenant_isolation_responses_only_own_tenant(tenant_headers):
    """All products listed must belong to demo-inmobiliaria."""
    r = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
    assert r.status_code == 200
    for p in r.json():
        assert p.get("tenant_id") == "demo-inmobiliaria"


def test_tenant_isolation_via_db(tenant_headers):
    """Insert a product with another tenant_id directly in DB and verify it does NOT show up."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _setup():
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "inmobot_db")]
        foreign_name = f"TEST_Foreign_{UNIQ}"
        await db.products.insert_one({
            "tenant_id": "OTRO_TENANT_TEST",
            "name": foreign_name,
            "description": "no debe ser visible",
            "price": 1,
            "currency": "USD",
            "category": "X",
            "active": True,
            "created_at": "2025-01-01T00:00:00",
        })
        return foreign_name, db

    async def _teardown(db, fname):
        await db.products.delete_one({"tenant_id": "OTRO_TENANT_TEST", "name": fname})

    try:
        loop = asyncio.new_event_loop()
        foreign_name, db = loop.run_until_complete(_setup())

        # tenant admin should NOT see it
        r = requests.get(f"{API}/catalog", headers=tenant_headers, timeout=10)
        names = [p["name"] for p in r.json()]
        assert foreign_name not in names

        # tenant admin cannot update it (their tenant_id is demo-inmobiliaria)
        r2 = requests.put(
            f"{API}/catalog/{foreign_name}",
            json={"price": 999}, headers=tenant_headers, timeout=10,
        )
        assert r2.status_code == 404, "Cross-tenant update must fail with 404"

        # tenant admin cannot delete it
        r3 = requests.delete(f"{API}/catalog/{foreign_name}", headers=tenant_headers, timeout=10)
        assert r3.status_code == 404, "Cross-tenant delete must fail with 404"

        loop.run_until_complete(_teardown(db, foreign_name))
        loop.close()
    except Exception as e:
        pytest.fail(f"Tenant isolation test failed: {e}")


# ---------- Bot generic_flow integration (unit) ----------

def test_generic_flow_detects_catalog_keywords():
    from generic_flow import GenericFlowEngine, CATALOG_KEYWORDS
    eng = GenericFlowEngine.__new__(GenericFlowEngine)  # bypass init
    # detect_catalog_request only uses self for nothing important
    for kw in ["catalogo", "productos", "mostrame", "menu", "ofertas"]:
        assert kw in [k.lower() for k in CATALOG_KEYWORDS] or eng.detect_catalog_request(kw)


def test_generic_flow_has_catalog_handlers():
    from generic_flow import GenericFlowEngine
    assert hasattr(GenericFlowEngine, "_handle_catalog_request")
    assert hasattr(GenericFlowEngine, "_handle_product_selection")
    assert hasattr(GenericFlowEngine, "detect_catalog_request")


def test_generic_flow_product_id_prefix_logic():
    """Verify the source contains both 'prod_' and 'product_' prefix detection."""
    import inspect
    from generic_flow import GenericFlowEngine
    src = inspect.getsource(GenericFlowEngine.process_message)
    assert "prod_" in src
    assert "product_" in src


# ---------- Billing overage ----------

def test_overage_requires_superadmin(tenant_headers):
    r = requests.post(f"{API}/billing/bill-overage", json={}, headers=tenant_headers, timeout=15)
    assert r.status_code == 403
    body = r.json()
    assert "superadmin" in (body.get("detail", "") + body.get("message", "")).lower()


def test_overage_superadmin_no_stripe_graceful(super_headers):
    """Without Stripe configured, endpoint should respond gracefully (not 500)."""
    r = requests.post(f"{API}/billing/bill-overage", json={}, headers=super_headers, timeout=20)
    assert r.status_code in (200, 400), f"Expected graceful response, got {r.status_code}: {r.text}"
    if r.status_code == 200:
        data = r.json()
        # must be an object (skipped/error/total) - not a 500
        assert isinstance(data, (dict, list))
    else:
        body = r.text.lower()
        assert "stripe" in body or "configurado" in body


def test_overage_specific_tenant_no_stripe(super_headers):
    r = requests.post(
        f"{API}/billing/bill-overage",
        json={"tenant_id": "demo-inmobiliaria"},
        headers=super_headers, timeout=20,
    )
    assert r.status_code in (200, 400), r.text
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, dict)
        # should have status field like skipped/error
        assert any(k in data for k in ("status", "message", "skipped", "error", "billed", "amount"))


# ---------- Cleanup ----------

def test_zz_cleanup(tenant_headers):
    """Soft-delete (deactivate) test products created."""
    for n in (PROD_NAME, PROD_NAME_2):
        requests.delete(f"{API}/catalog/{n}", headers=tenant_headers, timeout=10)
    # Hard-delete from DB
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _wipe():
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "inmobot_db")]
        await db.products.delete_many({"name": {"$regex": "^TEST_"}})

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_wipe())
    loop.close()
