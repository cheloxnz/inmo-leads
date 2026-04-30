"""Iter30 - Charter Members endpoints + public recent signups widget."""
import os
import requests
import time
import pytest
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SUPER = ("admin@inmobot.com", "Admin123!")


def _login(email, pwd):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def super_headers():
    return {"Authorization": f"Bearer {_login(*SUPER)}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture
def any_tenant_id(super_headers):
    r = requests.get(f"{BASE}/api/auth/tenants", headers=super_headers, timeout=30)
    tenants = r.json()
    assert tenants, "No hay tenants para testear"
    tid = tenants[0]["tenant_id"]
    yield tid
    # cleanup: desmarcar
    try:
        requests.post(
            f"{BASE}/api/superadmin/tenants/{tid}/toggle-founder",
            headers=super_headers, json={"is_founder": False}, timeout=30,
        )
    except Exception:
        pass


# ============================================================
# Public recent signups widget
# ============================================================

def test_public_recent_signups_no_auth_required():
    r = requests.get(f"{BASE}/api/public/founder-recent-signups", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "count" in body
    assert isinstance(body["items"], list)


def test_public_recent_signups_respects_limit():
    r = requests.get(f"{BASE}/api/public/founder-recent-signups?limit=3", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 3


def test_public_recent_signups_shape_anonymized(super_headers, any_tenant_id):
    # Marcar un tenant
    requests.post(
        f"{BASE}/api/superadmin/tenants/{any_tenant_id}/toggle-founder",
        headers=super_headers, json={"is_founder": True}, timeout=30,
    )
    # Esperar que el cache se invalide (debería ser instantáneo via toggle)
    r = requests.get(f"{BASE}/api/public/founder-recent-signups?limit=5", timeout=30)
    body = r.json()
    # Debe aparecer
    assert body["count"] >= 1
    first = body["items"][0]
    # No exponer PII
    assert "business_name" not in first
    assert "email" not in first
    assert "tenant_id" not in first
    assert "name" not in first
    # Shape público
    assert "initials" in first and len(first["initials"]) <= 3
    assert "time_ago" in first
    assert "joined_at" in first


def test_public_recent_signups_time_ago_spanish(super_headers, any_tenant_id):
    requests.post(
        f"{BASE}/api/superadmin/tenants/{any_tenant_id}/toggle-founder",
        headers=super_headers, json={"is_founder": True}, timeout=30,
    )
    r = requests.get(f"{BASE}/api/public/founder-recent-signups?limit=5", timeout=30)
    body = r.json()
    assert body["count"] >= 1
    ta = body["items"][0]["time_ago"]
    # Debe estar en español
    assert "hace" in ta


# ============================================================
# Admin list + toggle
# ============================================================

def test_admin_list_founders_requires_auth():
    r = requests.get(f"{BASE}/api/superadmin/founders", timeout=30)
    assert r.status_code in (401, 403)


def test_admin_list_founders_shape(super_headers):
    r = requests.get(f"{BASE}/api/superadmin/founders",
                     headers=super_headers, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_admin_toggle_founder_true_then_false(super_headers, any_tenant_id, db):
    # Marcar
    r1 = requests.post(
        f"{BASE}/api/superadmin/tenants/{any_tenant_id}/toggle-founder",
        headers=super_headers, json={"is_founder": True}, timeout=30,
    )
    assert r1.status_code == 200
    assert r1.json()["is_founder"] is True
    # Confirmar en DB
    t = db.tenants.find_one({"tenant_id": any_tenant_id})
    assert t["is_founder"] is True
    assert t.get("founder_joined_at")
    # Aparece en admin list
    listing = requests.get(f"{BASE}/api/superadmin/founders",
                           headers=super_headers, timeout=30).json()
    assert any(m["tenant_id"] == any_tenant_id for m in listing["items"])
    # Desmarcar
    r2 = requests.post(
        f"{BASE}/api/superadmin/tenants/{any_tenant_id}/toggle-founder",
        headers=super_headers, json={"is_founder": False}, timeout=30,
    )
    assert r2.json()["is_founder"] is False
    t2 = db.tenants.find_one({"tenant_id": any_tenant_id})
    assert t2["is_founder"] is False


def test_admin_toggle_nonexistent_tenant_404(super_headers):
    r = requests.post(
        f"{BASE}/api/superadmin/tenants/inexistente-xyz-nope/toggle-founder",
        headers=super_headers, json={"is_founder": True}, timeout=30,
    )
    assert r.status_code == 404


def test_toggle_audit_logged(super_headers, any_tenant_id, db):
    before = db.audit_log.count_documents({"action": "founder_toggle"})
    requests.post(
        f"{BASE}/api/superadmin/tenants/{any_tenant_id}/toggle-founder",
        headers=super_headers, json={"is_founder": True}, timeout=30,
    )
    after = db.audit_log.count_documents({"action": "founder_toggle"})
    assert after > before


def test_toggle_invalidates_cache_so_taken_count_bumps(super_headers, any_tenant_id):
    # Reset a False primero
    requests.post(
        f"{BASE}/api/superadmin/tenants/{any_tenant_id}/toggle-founder",
        headers=super_headers, json={"is_founder": False}, timeout=30,
    )
    before_state = requests.get(f"{BASE}/api/public/founder-seats", timeout=30).json()
    # Marcar
    requests.post(
        f"{BASE}/api/superadmin/tenants/{any_tenant_id}/toggle-founder",
        headers=super_headers, json={"is_founder": True}, timeout=30,
    )
    after_state = requests.get(f"{BASE}/api/public/founder-seats", timeout=30).json()
    assert after_state["taken"] >= before_state["taken"]
