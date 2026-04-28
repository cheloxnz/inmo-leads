"""
Tests iter9: Branding editor endpoints + public catalog campos nuevos.

Endpoints probados:
  - POST /api/auth/login (admin tenant + superadmin)
  - GET  /api/auth/tenant/branding
  - PUT  /api/auth/tenant/branding (whitelist, campos invalidos, body vacio, no-admin)
  - GET  /api/public/catalog/{tenant_id} (nuevos campos primary_color, accent_color, hero_bg_url, custom_features, custom_steps)
  - Aislamiento de tenant (PUT solo afecta al tenant del JWT)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://inmobot-preview.preview.emergentagent.com"

ADMIN_TENANT = {"email": "demo@inmobot.com", "password": "Demo123!"}
SUPERADMIN = {"email": "admin@inmobot.com", "password": "Admin123!"}


# ---------- helpers ----------

def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return r.json()["access_token"], r.json()["user"]


@pytest.fixture(scope="module")
def admin_token():
    token, _ = _login(ADMIN_TENANT)
    return token


@pytest.fixture(scope="module")
def admin_user():
    _, user = _login(ADMIN_TENANT)
    return user


@pytest.fixture(scope="module")
def superadmin_token():
    token, _ = _login(SUPERADMIN)
    return token


def _auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- GET /auth/tenant/branding ----------

class TestGetBranding:
    def test_returns_branding_shape(self, admin_token, admin_user):
        r = requests.get(
            f"{BASE_URL}/api/auth/tenant/branding",
            headers=_auth(admin_token), timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Debe incluir tenant_id y name + todos los campos whitelist
        expected_keys = {
            "business_name", "business_tagline", "logo_url",
            "primary_color", "accent_color", "hero_bg_url",
            "template_id", "contact_phone", "country",
            "custom_features", "custom_steps", "tenant_id", "name",
        }
        assert expected_keys.issubset(set(data.keys())), f"missing keys: {expected_keys - set(data.keys())}"
        assert data["tenant_id"] == admin_user["tenant_id"]

    def test_custom_features_and_steps_are_lists(self, admin_token):
        """Smoke-test del bug mencionado: custom_features/custom_steps deben ser list, no ''"""
        r = requests.get(
            f"{BASE_URL}/api/auth/tenant/branding",
            headers=_auth(admin_token), timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["custom_features"], list), f"custom_features should be list, got {type(data['custom_features']).__name__}={data['custom_features']!r}"
        assert isinstance(data["custom_steps"], list), f"custom_steps should be list, got {type(data['custom_steps']).__name__}={data['custom_steps']!r}"

    def test_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/auth/tenant/branding", timeout=15)
        assert r.status_code == 401


# ---------- PUT /auth/tenant/branding ----------

class TestPutBranding:
    def test_whitelist_accepted_and_persisted(self, admin_token):
        payload = {
            "business_name": "TEST Branding Demo",
            "business_tagline": "Agente IA 24/7 - TEST",
            "primary_color": "#16a34a",
            "accent_color": "#059669",
            "contact_phone": "+5491100000000",
            "template_id": "inmobiliaria",
            "custom_features": [
                {"title": "Feature 1", "desc": "Desc 1"},
                {"title": "Feature 2", "desc": "Desc 2"},
            ],
            "custom_steps": [
                {"title": "Paso 1", "desc": "Desc paso 1"},
            ],
        }
        r = requests.put(
            f"{BASE_URL}/api/auth/tenant/branding",
            json=payload, headers=_auth(admin_token), timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "updated_fields" in body
        assert set(payload.keys()).issubset(set(body["updated_fields"]))

        # Re-leer y verificar persistencia
        r2 = requests.get(
            f"{BASE_URL}/api/auth/tenant/branding",
            headers=_auth(admin_token), timeout=15,
        )
        d = r2.json()
        assert d["business_name"] == "TEST Branding Demo"
        assert d["primary_color"] == "#16a34a"
        assert d["accent_color"] == "#059669"
        assert d["template_id"] == "inmobiliaria"
        assert isinstance(d["custom_features"], list) and len(d["custom_features"]) == 2
        assert d["custom_features"][0]["title"] == "Feature 1"

    def test_whitelist_rejects_unsafe_fields(self, admin_token):
        """Campos no whitelist no deben persistir."""
        # Capturar valores actuales
        pre = requests.get(
            f"{BASE_URL}/api/auth/tenant/branding",
            headers=_auth(admin_token), timeout=15,
        ).json()

        payload = {
            "business_name": "TEST Whitelist",
            "max_ai_messages": 9999999,       # no whitelist
            "stripe_customer_id": "cus_FAKE", # no whitelist
            "tenant_id": "hacker-tenant",     # no whitelist
            "subscription_status": "free",    # no whitelist
            "active": False,                  # no whitelist
        }
        r = requests.put(
            f"{BASE_URL}/api/auth/tenant/branding",
            json=payload, headers=_auth(admin_token), timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Solo business_name debe aplicarse
        assert body["updated_fields"] == ["business_name"] or body["updated_fields"] == ["business_name", "updated_at"]

        # Verificar que max_ai_messages/stripe/active/tenant_id NO cambiaron
        post = requests.get(
            f"{BASE_URL}/api/auth/tenant/branding",
            headers=_auth(admin_token), timeout=15,
        ).json()
        assert post["tenant_id"] == pre["tenant_id"]  # tenant_id intocable

    def test_empty_body_returns_400(self, admin_token):
        r = requests.put(
            f"{BASE_URL}/api/auth/tenant/branding",
            json={}, headers=_auth(admin_token), timeout=15,
        )
        assert r.status_code == 400
        assert "Sin campos validos" in r.text or "Sin campos" in r.text

    def test_only_invalid_fields_returns_400(self, admin_token):
        r = requests.put(
            f"{BASE_URL}/api/auth/tenant/branding",
            json={"max_ai_messages": 10, "stripe_customer_id": "x"},
            headers=_auth(admin_token), timeout=15,
        )
        assert r.status_code == 400

    def test_unauth_put_returns_401(self):
        r = requests.put(
            f"{BASE_URL}/api/auth/tenant/branding",
            json={"business_name": "x"}, timeout=15,
        )
        assert r.status_code == 401

    def test_asesor_forbidden(self, admin_token):
        """Crear un asesor (no admin) y verificar que NO pueda editar branding."""
        import uuid
        asesor_email = f"TEST_asesor_{uuid.uuid4().hex[:8]}@inmobot.com"
        asesor_pwd = "Asesor123!"
        # Create asesor via /auth/register (requires admin)
        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "TEST Asesor",
                "email": asesor_email,
                "password": asesor_pwd,
                "phone": "",
                "specialties": [],
                "zones": [],
            },
            headers=_auth(admin_token), timeout=15,
        )
        if r.status_code not in (200, 201):
            pytest.skip(f"cannot create asesor: {r.status_code} {r.text}")

        try:
            # login as asesor
            login_r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": asesor_email, "password": asesor_pwd}, timeout=15,
            )
            assert login_r.status_code == 200
            asesor_token = login_r.json()["access_token"]

            # PUT /tenant/branding debe dar 403
            put_r = requests.put(
                f"{BASE_URL}/api/auth/tenant/branding",
                json={"business_name": "HACKED"},
                headers=_auth(asesor_token), timeout=15,
            )
            assert put_r.status_code == 403, f"asesor should not update branding, got {put_r.status_code}"
        finally:
            requests.delete(
                f"{BASE_URL}/api/auth/agents/{asesor_email}",
                headers=_auth(admin_token), timeout=15,
            )


# ---------- Public catalog new fields ----------

class TestPublicCatalogBrandingFields:
    def test_public_catalog_exposes_new_fields(self, admin_token):
        # set a known branding first
        requests.put(
            f"{BASE_URL}/api/auth/tenant/branding",
            json={
                "primary_color": "#111111",
                "accent_color": "#222222",
                "hero_bg_url": "https://img.example/hero.jpg",
                "custom_features": [{"title": "F1", "desc": "D1"}],
                "custom_steps": [{"title": "S1", "desc": "DS1"}],
            },
            headers=_auth(admin_token), timeout=15,
        )

        r = requests.get(f"{BASE_URL}/api/public/catalog/demo-inmobiliaria", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        tenant = data.get("tenant", {})
        for k in ("primary_color", "accent_color", "hero_bg_url", "custom_features", "custom_steps"):
            assert k in tenant, f"missing {k} in public catalog tenant block"
        assert tenant["primary_color"] == "#111111"
        assert tenant["accent_color"] == "#222222"
        assert isinstance(tenant["custom_features"], list)
        assert isinstance(tenant["custom_steps"], list)
        assert len(tenant["custom_features"]) == 1
        assert tenant["custom_features"][0]["title"] == "F1"


# ---------- Tenant isolation ----------

class TestTenantIsolation:
    def test_put_only_affects_own_tenant(self, admin_token, superadmin_token, admin_user):
        """Al hacer PUT como admin del tenant demo, solo debe cambiar demo, no otros tenants."""
        # list tenants (superadmin)
        r = requests.get(f"{BASE_URL}/api/auth/tenants", headers=_auth(superadmin_token), timeout=15)
        assert r.status_code == 200
        tenants = r.json()
        my_tid = admin_user["tenant_id"]
        others = [t for t in tenants if t["tenant_id"] != my_tid]
        if not others:
            pytest.skip("no other tenant to compare isolation")
        other = others[0]
        other_tid = other["tenant_id"]
        # snapshot other tenant
        pre_other = requests.get(
            f"{BASE_URL}/api/auth/tenants/{other_tid}",
            headers=_auth(superadmin_token), timeout=15,
        ).json()
        pre_name = pre_other.get("business_name", "")

        # admin del tenant my_tid hace PUT con business_name distinto
        uniq = "TEST_ISO_DEMO_ONLY"
        r2 = requests.put(
            f"{BASE_URL}/api/auth/tenant/branding",
            json={"business_name": uniq}, headers=_auth(admin_token), timeout=15,
        )
        assert r2.status_code == 200

        # verificar que OTRO tenant no cambio
        post_other = requests.get(
            f"{BASE_URL}/api/auth/tenants/{other_tid}",
            headers=_auth(superadmin_token), timeout=15,
        ).json()
        assert post_other.get("business_name", "") == pre_name
        assert post_other.get("business_name", "") != uniq
