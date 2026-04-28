"""
Backend tests for InmoBot SaaS - Iteration 5:
- POST /api/catalog/recommend (auth) -> {recommendations, ai_enabled}
- POST /api/public/catalog/{tenant_id}/recommend (no auth)
- GET /api/public/catalog/{tenant_id} (no auth, sin tenant_id en productos)
- GET /api/public/catalog/{tenant_id-inexistente} -> 404
- Bulk-write backfill product_id (insert sin product_id, GET, verify in DB)
- Router metrics: leads-by-day, leads-by-status, leads-by-intent,
  conversion-funnel, messages
- Regresion endpoints iter_4 (catalog CRUD, billing/plans)
"""
import os
import uuid
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
TENANT_ID = "demo-inmobiliaria"

UNIQ = uuid.uuid4().hex[:8]


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def tenant_headers():
    r = requests.post(f"{API}/auth/login", json={"email": TENANT_EMAIL, "password": TENANT_PASS}, timeout=15)
    assert r.status_code == 200, f"login fail: {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def seed_products(db, tenant_headers):
    """Garantiza al menos 2 productos activos en demo para los tests"""
    p1 = {"name": f"TEST_Casa_Iter5_{UNIQ}", "price": "USD 150000", "description": "Casa 3 amb con jardin en zona norte", "category": "casa"}
    p2 = {"name": f"TEST_Depto_Iter5_{UNIQ}", "price": "USD 95000", "description": "Departamento 2 ambientes en Palermo", "category": "departamento"}
    r1 = requests.post(f"{API}/catalog", json=p1, headers=tenant_headers)
    r2 = requests.post(f"{API}/catalog", json=p2, headers=tenant_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    yield
    # cleanup
    db.products.delete_many({"tenant_id": TENANT_ID, "name": {"$regex": "^TEST_.*Iter5"}})


# ---------- AI Recommendations (auth) ----------

def test_recommend_auth_returns_structure(tenant_headers):
    r = requests.post(f"{API}/catalog/recommend", json={"query": "busco casa con jardin", "max_results": 2}, headers=tenant_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "recommendations" in data
    assert "ai_enabled" in data
    assert isinstance(data["recommendations"], list)
    # OPENAI_API_KEY no configurada -> ai_enabled debe ser False
    assert data["ai_enabled"] is False
    # fallback: devuelve los primeros N productos
    assert len(data["recommendations"]) <= 2


def test_recommend_auth_query_required(tenant_headers):
    r = requests.post(f"{API}/catalog/recommend", json={"query": ""}, headers=tenant_headers)
    assert r.status_code == 400


def test_recommend_no_auth_unauthorized():
    r = requests.post(f"{API}/catalog/recommend", json={"query": "casa"})
    assert r.status_code in (401, 403)


# ---------- AI Recommendations Public ----------

def test_public_recommend_no_auth():
    r = requests.post(f"{API}/public/catalog/{TENANT_ID}/recommend", json={"query": "depto en palermo", "max_results": 3})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "recommendations" in data
    assert "ai_enabled" in data
    assert data["ai_enabled"] is False
    # Sin tenant_id leak en productos
    for p in data["recommendations"]:
        assert "tenant_id" not in p


def test_public_recommend_404_invalid_tenant():
    r = requests.post(f"{API}/public/catalog/tenant-inexistente-xyz/recommend", json={"query": "x"})
    assert r.status_code == 404


def test_public_recommend_query_required():
    r = requests.post(f"{API}/public/catalog/{TENANT_ID}/recommend", json={"query": ""})
    assert r.status_code == 400


# ---------- Public Catalog ----------

def test_public_catalog_get():
    r = requests.get(f"{API}/public/catalog/{TENANT_ID}")
    assert r.status_code == 200
    data = r.json()
    assert "tenant" in data
    assert "products" in data
    assert "categories" in data
    assert data["tenant"].get("name") or data["tenant"].get("business_name")
    # No leak de tenant_id
    for p in data["products"]:
        assert "tenant_id" not in p
    assert isinstance(data["categories"], list)


def test_public_catalog_404():
    r = requests.get(f"{API}/public/catalog/tenant-no-existe-xyz-{UNIQ}")
    assert r.status_code == 404


def test_public_catalog_no_auth_required():
    # explicit: no Authorization header
    r = requests.get(f"{API}/public/catalog/{TENANT_ID}", headers={})
    assert r.status_code == 200


# ---------- Bulk-write backfill product_id ----------

def test_backfill_product_id(db, tenant_headers):
    """Inserta producto sin product_id, GET, verifica que product_id existe en DB"""
    legacy_name = f"TEST_Legacy_{UNIQ}"
    db.products.insert_one({
        "tenant_id": TENANT_ID,
        "name": legacy_name,
        "price": "USD 1",
        "active": True,
        "description": "legacy producto sin product_id"
    })
    try:
        # Verifica que NO tiene product_id antes
        before = db.products.find_one({"tenant_id": TENANT_ID, "name": legacy_name})
        assert before is not None
        assert "product_id" not in before or not before.get("product_id")

        # Trigger backfill via GET
        r = requests.get(f"{API}/catalog", headers=tenant_headers)
        assert r.status_code == 200
        prods = r.json()
        # Encontrar el producto en la respuesta
        target = next((p for p in prods if p.get("name") == legacy_name), None)
        assert target is not None
        assert target.get("product_id"), "GET debe devolver product_id (backfill)"

        # Verifica persistencia en DB
        after = db.products.find_one({"tenant_id": TENANT_ID, "name": legacy_name})
        assert after.get("product_id"), "product_id debe estar persistido en DB tras GET"
        assert after["product_id"] == target["product_id"]
    finally:
        db.products.delete_many({"tenant_id": TENANT_ID, "name": legacy_name})


# ---------- Metrics router ----------

def test_metrics_leads_by_day(tenant_headers):
    r = requests.get(f"{API}/metrics/leads-by-day?days=30", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for item in data:
        assert "date" in item
        assert "count" in item


def test_metrics_leads_by_status(tenant_headers):
    r = requests.get(f"{API}/metrics/leads-by-status", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for item in data:
        assert "status" in item and "count" in item


def test_metrics_leads_by_intent(tenant_headers):
    r = requests.get(f"{API}/metrics/leads-by-intent", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for item in data:
        assert "intent" in item and "count" in item


def test_metrics_conversion_funnel(tenant_headers):
    r = requests.get(f"{API}/metrics/conversion-funnel", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    for k in ["total_leads", "qualified", "with_appointment", "hot_leads",
              "qualification_rate", "appointment_rate", "conversion_rate"]:
        assert k in data, f"missing key {k}"


def test_metrics_messages(tenant_headers):
    r = requests.get(f"{API}/metrics/messages?days=30", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    for k in ["total_messages", "incoming_messages", "outgoing_messages",
              "messages_last_period", "messages_by_day", "avg_per_day",
              "total_leads", "avg_messages_per_lead"]:
        assert k in data


def test_metrics_no_auth():
    r = requests.get(f"{API}/metrics/leads-by-day")
    assert r.status_code in (401, 403)


# ---------- Regression catalog CRUD ----------

def test_regression_catalog_get_with_product_id(tenant_headers):
    r = requests.get(f"{API}/catalog", headers=tenant_headers)
    assert r.status_code == 200
    products = r.json()
    assert isinstance(products, list)
    if products:
        for p in products:
            assert p.get("product_id"), "todo producto debe tener product_id"


def test_regression_catalog_create_returns_product_id(tenant_headers, db):
    payload = {"name": f"TEST_Reg_{UNIQ}", "price": "USD 1", "description": "x"}
    r = requests.post(f"{API}/catalog", json=payload, headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    pid = data.get("product_id") or data.get("id")
    assert pid
    # cleanup
    db.products.delete_many({"tenant_id": TENANT_ID, "name": payload["name"]})


def test_regression_billing_plans():
    r = requests.get(f"{API}/plans")
    assert r.status_code == 200
    data = r.json()
    # Acepta dict o list (api retorna dict de planes)
    assert isinstance(data, (list, dict))
    assert len(data) > 0


def test_regression_billing_status(tenant_headers):
    r = requests.get(f"{API}/billing", headers=tenant_headers)
    assert r.status_code == 200


def test_regression_leads_endpoint(tenant_headers):
    r = requests.get(f"{API}/leads", headers=tenant_headers)
    assert r.status_code == 200
