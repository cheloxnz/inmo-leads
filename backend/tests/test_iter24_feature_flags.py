"""Iter24 - Feature Flags por tenant.
- Registry exposable
- Helpers has_feature / get_tenant_features
- Endpoints superadmin: registry, GET features, PUT toggle
- /api/auth/tenant/branding incluye features
- Permisos: solo superadmin puede mutar
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_TENANT = "demo-inmobiliaria"
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"
SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASSWORD = "Admin123!"


def _login(email, password):
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def super_headers():
    return {"Authorization": f"Bearer {_login(SUPER_EMAIL, SUPER_PASSWORD)}"}


@pytest.fixture(scope="module")
def tenant_headers():
    return {"Authorization": f"Bearer {_login(DEMO_EMAIL, DEMO_PASSWORD)}"}


@pytest.fixture()
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(autouse=True)
def reset_demo_features():
    """Limpia overrides del demo tenant antes y después de cada test."""
    cli = MongoClient(os.environ["MONGO_URL"])
    d = cli[os.environ["DB_NAME"]]
    d.tenants.update_one(
        {"tenant_id": DEMO_TENANT},
        {"$set": {"features": {}}},
    )
    yield
    d.tenants.update_one(
        {"tenant_id": DEMO_TENANT},
        {"$set": {"features": {}}},
    )
    cli.close()


# ---------------- Helper unit tests ----------------
class TestHelperFunctions:
    def test_has_feature_returns_default_when_no_override(self):
        from feature_flags import has_feature
        tenant = {"tenant_id": "x", "features": {}}
        assert has_feature(tenant, "mortgage_calculator") is False

    def test_has_feature_with_truthy_override(self):
        from feature_flags import has_feature
        tenant = {"tenant_id": "x", "features": {"mortgage_calculator": True}}
        assert has_feature(tenant, "mortgage_calculator") is True

    def test_has_feature_with_dict_override(self):
        from feature_flags import has_feature
        tenant = {
            "tenant_id": "x",
            "features": {"voice_response_tts": {"enabled": True, "voice": "alloy"}},
        }
        assert has_feature(tenant, "voice_response_tts") is True

    def test_has_feature_with_dict_disabled(self):
        from feature_flags import has_feature
        tenant = {"features": {"voice_response_tts": {"enabled": False}}}
        assert has_feature(tenant, "voice_response_tts") is False

    def test_has_feature_unknown_returns_false(self):
        from feature_flags import has_feature
        tenant = {"features": {}}
        assert has_feature(tenant, "non_existent_feature") is False

    def test_get_tenant_features_returns_all_keys(self):
        from feature_flags import get_tenant_features, FEATURE_FLAGS
        tenant = {"features": {"mortgage_calculator": True}}
        out = get_tenant_features(tenant)
        # Todas las keys del registry deben estar
        assert set(out.keys()) == set(FEATURE_FLAGS.keys())
        assert out["mortgage_calculator"] is True
        # Resto debe ser default (False)
        for k, v in out.items():
            if k != "mortgage_calculator":
                assert v is False


# ---------------- Endpoint: registry ----------------
class TestRegistryEndpoint:
    def test_requires_superadmin(self, tenant_headers):
        r = requests.get(
            f"{BASE}/api/superadmin/feature-flags/registry",
            headers=tenant_headers,
        )
        assert r.status_code == 403

    def test_no_auth_blocked(self):
        r = requests.get(f"{BASE}/api/superadmin/feature-flags/registry")
        assert r.status_code in (401, 403)

    def test_returns_registry(self, super_headers):
        r = requests.get(
            f"{BASE}/api/superadmin/feature-flags/registry",
            headers=super_headers,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "flags" in d
        assert len(d["flags"]) >= 5
        keys = [f["key"] for f in d["flags"]]
        assert "mortgage_calculator" in keys
        # Cada flag tiene metadata completa
        first = d["flags"][0]
        for k in ("key", "label", "description", "category", "default"):
            assert k in first


# ---------------- Endpoint: tenant features ----------------
class TestTenantFeaturesEndpoint:
    def test_get_requires_superadmin(self, tenant_headers):
        r = requests.get(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=tenant_headers,
        )
        assert r.status_code == 403

    def test_get_returns_state(self, super_headers):
        r = requests.get(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=super_headers,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["tenant_id"] == DEMO_TENANT
        assert "features" in d
        assert isinstance(d["features"], dict)

    def test_get_unknown_tenant_404(self, super_headers):
        r = requests.get(
            f"{BASE}/api/superadmin/tenants/non_existent_xyz/features",
            headers=super_headers,
        )
        assert r.status_code == 404


# ---------------- Endpoint: update flag ----------------
class TestUpdateFlagEndpoint:
    def test_put_requires_superadmin(self, tenant_headers):
        r = requests.put(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=tenant_headers,
            json={"feature": "mortgage_calculator", "enabled": True},
        )
        assert r.status_code == 403

    def test_enable_flag(self, super_headers, db):
        r = requests.put(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=super_headers,
            json={"feature": "mortgage_calculator", "enabled": True},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["enabled"] is True

        # Persistencia
        t = db.tenants.find_one({"tenant_id": DEMO_TENANT})
        assert t["features"]["mortgage_calculator"] is True

    def test_disable_flag(self, super_headers, db):
        # Enable
        requests.put(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=super_headers,
            json={"feature": "salesforce_sync", "enabled": True},
        )
        # Disable
        r = requests.put(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=super_headers,
            json={"feature": "salesforce_sync", "enabled": False},
        )
        assert r.status_code == 200
        t = db.tenants.find_one({"tenant_id": DEMO_TENANT})
        assert t["features"]["salesforce_sync"] is False

    def test_unknown_feature_400(self, super_headers):
        r = requests.put(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=super_headers,
            json={"feature": "totally_invented_feature_xyz", "enabled": True},
        )
        assert r.status_code == 400

    def test_unknown_tenant_404(self, super_headers):
        r = requests.put(
            f"{BASE}/api/superadmin/tenants/non_existent_xyz/features",
            headers=super_headers,
            json={"feature": "mortgage_calculator", "enabled": True},
        )
        assert r.status_code == 404

    def test_audit_log_written(self, super_headers, db):
        marker = uuid.uuid4().hex[:6]
        # Limpia logs previos del feature
        before = db.audit_log.count_documents({"action": "feature_flag_updated"})
        requests.put(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=super_headers,
            json={"feature": "advanced_analytics_export", "enabled": True},
        )
        after = db.audit_log.count_documents({"action": "feature_flag_updated"})
        assert after > before


# ---------------- /auth/tenant/branding includes features ----------------
class TestBrandingIncludesFeatures:
    def test_branding_returns_features(self, tenant_headers):
        r = requests.get(f"{BASE}/api/auth/tenant/branding", headers=tenant_headers)
        assert r.status_code == 200
        d = r.json()
        assert "features" in d
        assert isinstance(d["features"], dict)
        # Todas las keys del registry presentes
        from feature_flags import FEATURE_FLAGS
        for k in FEATURE_FLAGS.keys():
            assert k in d["features"], f"missing feature {k} in branding"

    def test_enabling_flag_reflects_in_branding(self, super_headers, tenant_headers):
        # Habilitar
        requests.put(
            f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
            headers=super_headers,
            json={"feature": "ai_lead_summary", "enabled": True},
        )
        # Tenant ve la feature como activa
        r = requests.get(f"{BASE}/api/auth/tenant/branding", headers=tenant_headers)
        assert r.status_code == 200
        assert r.json()["features"]["ai_lead_summary"] is True
