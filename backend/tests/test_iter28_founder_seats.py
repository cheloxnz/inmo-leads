"""Iter28 - Founder Seats endpoint público + admin config.

- GET /api/public/founder-seats (sin auth) — shape estable para Shopify
- GET /api/superadmin/founder-seats/config (superadmin only)
- PUT /api/superadmin/founder-seats/config
- POST /api/superadmin/founder-seats/invalidate-cache
- Onboarding marca is_founder=True cuando hay cupos.
"""
import os
import requests
import pytest
from pymongo import MongoClient


BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASSWORD = "Admin123!"
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"


def _login(email, pwd):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": pwd}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def super_headers():
    return {"Authorization": f"Bearer {_login(SUPER_EMAIL, SUPER_PASSWORD)}"}


@pytest.fixture(scope="module")
def tenant_headers():
    return {"Authorization": f"Bearer {_login(DEMO_EMAIL, DEMO_PASSWORD)}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ============================================================
# Public endpoint
# ============================================================

def test_public_endpoint_no_auth_required():
    r = requests.get(f"{BASE}/api/public/founder-seats", timeout=10)
    assert r.status_code == 200
    body = r.json()
    for k in ("total", "taken", "left", "percent", "closes_at", "is_open"):
        assert k in body, f"missing key: {k}"


def test_public_endpoint_shape_and_invariants():
    r = requests.get(f"{BASE}/api/public/founder-seats", timeout=10)
    body = r.json()
    assert isinstance(body["total"], int)
    assert isinstance(body["taken"], int)
    assert isinstance(body["left"], int)
    assert isinstance(body["is_open"], bool)
    assert isinstance(body["percent"], (int, float))
    assert body["total"] >= 1
    assert 0 <= body["taken"] <= body["total"]
    assert body["left"] == body["total"] - body["taken"]
    assert 0 <= body["percent"] <= 100


def test_public_endpoint_no_internal_fields():
    r = requests.get(f"{BASE}/api/public/founder-seats", timeout=10)
    body = r.json()
    # No exponer boost ni generated_at ni config real
    assert "boost" not in body
    assert "generated_at" not in body
    assert "active" not in body


# ============================================================
# Admin endpoints
# ============================================================

def test_admin_get_config_requires_superadmin(tenant_headers):
    r = requests.get(f"{BASE}/api/superadmin/founder-seats/config",
                     headers=tenant_headers, timeout=10)
    assert r.status_code in (403, 401)


def test_admin_get_config_no_auth():
    r = requests.get(f"{BASE}/api/superadmin/founder-seats/config", timeout=10)
    assert r.status_code in (401, 403)


def test_admin_get_config_shape(super_headers):
    r = requests.get(f"{BASE}/api/superadmin/founder-seats/config",
                     headers=super_headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "config" in body
    assert "real_founders_count" in body
    assert "public_state" in body
    cfg = body["config"]
    for k in ("total", "boost", "closes_at", "active"):
        assert k in cfg
    assert isinstance(body["real_founders_count"], int)


def test_admin_put_update_boost(super_headers):
    # Fijar boost en 10
    r = requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                     headers=super_headers, json={"boost": 10}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["config"]["boost"] == 10
    # Verificar en public endpoint (tras invalidación de cache)
    r2 = requests.get(f"{BASE}/api/public/founder-seats", timeout=10)
    assert r2.json()["taken"] >= 10  # boost + reales
    # Restaurar a 8
    requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                 headers=super_headers, json={"boost": 8}, timeout=10)


def test_admin_put_invalid_closes_at_rejected(super_headers):
    r = requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                     headers=super_headers,
                     json={"closes_at": "no-es-fecha"}, timeout=10)
    assert r.status_code == 400


def test_admin_put_empty_payload_400(super_headers):
    r = requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                     headers=super_headers, json={}, timeout=10)
    assert r.status_code == 400


def test_admin_put_requires_superadmin(tenant_headers):
    r = requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                     headers=tenant_headers, json={"boost": 5}, timeout=10)
    assert r.status_code in (401, 403)


def test_admin_invalidate_cache_works(super_headers):
    r = requests.post(f"{BASE}/api/superadmin/founder-seats/invalidate-cache",
                      headers=super_headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "public_state" in body


# ============================================================
# DB-level: cupo cerrado cuando active=false
# ============================================================

def test_is_open_false_when_active_false(super_headers, db):
    # Desactivar
    r = requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                     headers=super_headers, json={"active": False}, timeout=10)
    assert r.status_code == 200
    pub = requests.get(f"{BASE}/api/public/founder-seats", timeout=10).json()
    assert pub["is_open"] is False
    # Reactivar
    requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                 headers=super_headers, json={"active": True}, timeout=10)


def test_settings_doc_created_in_db(db):
    # Al menos un GET público garantiza que el doc exista
    requests.get(f"{BASE}/api/public/founder-seats", timeout=10)
    doc = db.settings.find_one({"_id": "founder_plan"})
    assert doc is not None
    assert "total" in doc
    assert "closes_at" in doc


def test_audit_log_written_on_put(super_headers, db):
    before = db.audit_log.count_documents({"action": "founder_config_updated"})
    requests.put(f"{BASE}/api/superadmin/founder-seats/config",
                 headers=super_headers, json={"boost": 8}, timeout=10)
    after = db.audit_log.count_documents({"action": "founder_config_updated"})
    assert after > before
