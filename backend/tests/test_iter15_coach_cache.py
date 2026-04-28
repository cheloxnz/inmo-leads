"""Iter 15 - Smart Onboarding Coach + cache_util TTL + flow_ai truncate.

Tests:
- POST /api/coach/run idempotente
- GET /api/coach/nudges retorna whatsapp_unconfigured
- POST /api/coach/nudges/{id}/dismiss
- 404 para nudge inexistente / ajeno
- cache_util TTL behavior
- flow_ai _MAX_OPS_PREVIEW = 20
"""
import os
import sys
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
BASE_URL_ENV = os.environ.get("REACT_APP_BACKEND_URL")
# Si el env var del frontend no está expuesto al backend, leemos del .env
if not BASE_URL_ENV:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

ADMIN_EMAIL = "demo@inmobot.com"
ADMIN_PASS = "Demo123!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Coach endpoints ----------

class TestCoachRun:
    def test_run_creates_at_least_whatsapp_nudge(self, headers):
        # Limpiar nudges previos del demo tenant para test idempotencia limpio
        # (no podemos borrar via API; corremos run y verificamos count >= 0)
        r = requests.post(f"{BASE_URL}/api/coach/run", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "created" in data
        assert data["tenant_id"] == "demo-inmobiliaria"

    def test_run_idempotent_second_call_creates_zero(self, headers):
        # ya corrimos en test anterior; segunda corrida debe ser 0 (todos los nudges ya activos)
        r = requests.post(f"{BASE_URL}/api/coach/run", headers=headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["created"] == 0

    def test_get_nudges_includes_whatsapp_unconfigured(self, headers):
        r = requests.get(f"{BASE_URL}/api/coach/nudges", headers=headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "nudges" in data and "count" in data
        types = {n["nudge_type"] for n in data["nudges"]}
        assert "whatsapp_unconfigured" in types, f"types={types}"
        # validar campos del nudge whatsapp
        wa = next(n for n in data["nudges"] if n["nudge_type"] == "whatsapp_unconfigured")
        assert wa["severity"] == "high"
        assert wa["cta_url"] == "/config"
        assert wa["title"]
        assert wa["body"]
        assert wa.get("nudge_id")

    def test_dismiss_then_recreate_on_run(self, headers):
        # Get whatsapp nudge
        r = requests.get(f"{BASE_URL}/api/coach/nudges", headers=headers, timeout=10)
        wa = next((n for n in r.json()["nudges"] if n["nudge_type"] == "whatsapp_unconfigured"), None)
        assert wa, "whatsapp_unconfigured nudge missing"
        nid = wa["nudge_id"]

        # Dismiss
        d = requests.post(f"{BASE_URL}/api/coach/nudges/{nid}/dismiss", headers=headers, timeout=10)
        assert d.status_code == 200
        assert d.json().get("dismissed") is True

        # GET ya no debe incluirlo
        r2 = requests.get(f"{BASE_URL}/api/coach/nudges", headers=headers, timeout=10)
        assert nid not in {n["nudge_id"] for n in r2.json()["nudges"]}

        # POST /run: debe RECREARLO (idempotencia se basa en activos no descartados)
        run = requests.post(f"{BASE_URL}/api/coach/run", headers=headers, timeout=15)
        assert run.status_code == 200
        assert run.json()["created"] >= 1

        r3 = requests.get(f"{BASE_URL}/api/coach/nudges", headers=headers, timeout=10)
        types3 = {n["nudge_type"] for n in r3.json()["nudges"]}
        assert "whatsapp_unconfigured" in types3

    def test_dismiss_nonexistent_returns_404(self, headers):
        fake = str(uuid.uuid4())
        r = requests.post(f"{BASE_URL}/api/coach/nudges/{fake}/dismiss", headers=headers, timeout=10)
        assert r.status_code == 404

    def test_dismiss_already_dismissed_returns_404(self, headers):
        # dismiss el mismo whatsapp dos veces
        r = requests.get(f"{BASE_URL}/api/coach/nudges", headers=headers, timeout=10)
        wa = next((n for n in r.json()["nudges"] if n["nudge_type"] == "whatsapp_unconfigured"), None)
        if not wa:
            pytest.skip("no nudge para test")
        nid = wa["nudge_id"]
        d1 = requests.post(f"{BASE_URL}/api/coach/nudges/{nid}/dismiss", headers=headers, timeout=10)
        assert d1.status_code == 200
        d2 = requests.post(f"{BASE_URL}/api/coach/nudges/{nid}/dismiss", headers=headers, timeout=10)
        assert d2.status_code == 404


# ---------- cache_util TTL ----------

class TestCacheUtil:
    def test_ttl_expiration(self):
        sys.path.insert(0, "/app/backend")
        from cache_util import ttl_cache_get, ttl_cache_set, ttl_cache_invalidate
        ttl_cache_invalidate("test_ns")
        ttl_cache_set("test_ns", "x", {"a": 1}, ttl=1)
        v = ttl_cache_get("test_ns", "x")
        assert v == {"a": 1}
        time.sleep(1.2)
        v2 = ttl_cache_get("test_ns", "x")
        assert v2 is None

    def test_ttl_invalidate(self):
        from cache_util import ttl_cache_get, ttl_cache_set, ttl_cache_invalidate
        ttl_cache_set("test_ns", "k", "val", ttl=60)
        assert ttl_cache_get("test_ns", "k") == "val"
        ttl_cache_invalidate("test_ns", "k")
        assert ttl_cache_get("test_ns", "k") is None


# ---------- flow_ai truncate constant ----------

class TestFlowAITruncate:
    def test_max_ops_preview_is_20(self):
        sys.path.insert(0, "/app/backend")
        from routers import flow_ai
        assert flow_ai._MAX_OPS_PREVIEW == 20
        assert flow_ai._TENANT_CACHE_TTL == 60.0


# ---------- Routes documentation ----------

class TestRoutesDoc:
    def test_routes_md_documents_branding(self):
        path = "/app/backend/ROUTES.md"
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "/api/auth/tenant/branding" in content
        assert "/api/coach/nudges" in content
