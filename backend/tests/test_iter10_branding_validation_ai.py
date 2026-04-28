"""
Iter 10 - Tests:
1. Validacion backend hex/URL/template/list en PUT /api/auth/tenant/branding
2. Audit log en MongoDB cuando rechaza por whitelist
3. Whatsapp display phone separado de contact_phone
4. AI Copy Generator POST /api/auth/tenant/branding/ai-generate
5. Regresion (happy path)
"""
import os
import pytest
import requests
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Cargar backend/.env para MONGO_URL/DB_NAME
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "demo@inmobot.com"
ADMIN_PASSWORD = "Demo123!"
SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASSWORD = "Admin123!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_EMAIL, SUPER_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def asesor_token(admin_token):
    """Crea (o reusa) un asesor en demo-inmobiliaria y retorna su token.
    Usa el admin del tenant demo (require_admin)."""
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    email = "TEST_asesor_iter10@inmobot.com"
    password = "AsesorIter10!"
    # intento crear (idempotente)
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      headers=admin_headers,
                      json={
                          "email": email,
                          "password": password,
                          "name": "Asesor Iter10",
                          "phone": "+5491100001111",
                      }, timeout=20)
    # 200/201 ok, 400 si ya existe
    if r.status_code not in (200, 201, 400):
        pytest.skip(f"Could not create asesor: {r.status_code} {r.text}")
    # login
    r2 = requests.post(f"{BASE_URL}/api/auth/login",
                       json={"email": email, "password": password}, timeout=20)
    if r2.status_code != 200:
        pytest.skip(f"Asesor login failed: {r2.status_code} {r2.text}")
    return r2.json()["access_token"]


# ---------- 1. VALIDACION ----------

class TestBrandingValidation:

    def test_invalid_primary_color_no_hex(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={"primary_color": "red"}, timeout=20)
        assert r.status_code == 400
        body = r.json()
        # FastAPI envuelve en {"detail":{...}}
        detail = body.get("detail", body)
        errors = detail.get("validation_errors") if isinstance(detail, dict) else None
        assert errors and any("primary_color" in e for e in errors), f"Got: {body}"

    def test_invalid_primary_color_no_hash(self, admin_headers):
        # edge case: 'ff0000' sin #
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={"primary_color": "ff0000"}, timeout=20)
        assert r.status_code == 400

    def test_invalid_logo_url_xss(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={"logo_url": "javascript:alert(1)"}, timeout=20)
        assert r.status_code == 400
        body = r.json()
        detail = body.get("detail", body)
        errors = detail.get("validation_errors") if isinstance(detail, dict) else None
        assert errors and any("logo_url" in e for e in errors)

    def test_invalid_template_id(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={"template_id": "hack"}, timeout=20)
        assert r.status_code == 400

    def test_custom_features_not_list(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={"custom_features": "not_array"}, timeout=20)
        assert r.status_code == 400

    def test_custom_features_max_5(self, admin_headers):
        items = [{"icon": "bot", "title": f"t{i}", "desc": f"d{i}"} for i in range(6)]
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={"custom_features": items}, timeout=20)
        assert r.status_code == 400

    def test_valid_hex_and_json_ok(self, admin_headers):
        payload = {
            "primary_color": "#1a2b3c",
            "accent_color": "#ffffff",
            "logo_url": "https://example.com/logo.png",
            "template_id": "inmobiliaria",
            "custom_features": [{"icon": "bot", "title": "T1", "desc": "D1"}],
        }
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "updated_fields" in body
        assert "primary_color" in body["updated_fields"]


# ---------- 2. AUDIT LOG ----------

class TestAuditLog:

    def test_rejected_fields_returned_and_logged(self, admin_headers):
        # campos no permitidos
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={
                             "business_name": "AuditTestCo",
                             "max_ai_messages": 999,
                             "stripe_customer_id": "cus_evil",
                         }, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "rejected_fields" in body
        rejected = set(body["rejected_fields"])
        assert "max_ai_messages" in rejected
        assert "stripe_customer_id" in rejected

    @pytest.mark.asyncio
    async def test_audit_log_persisted_in_mongo(self, admin_headers):
        # disparar otro intento con marker unico
        marker_field = "evil_marker_xyz"
        # max_ai_messages para garantizar insert
        requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                     headers=admin_headers,
                     json={"max_ai_messages": 1}, timeout=20)

        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "inmobot_db")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        # buscar el ultimo audit log para demo
        doc = await db.audit_log.find_one(
            {"tenant_id": "demo-inmobiliaria",
             "action": "branding_rejected_fields"},
            sort=[("timestamp", -1)]
        )
        client.close()
        assert doc is not None
        assert doc.get("user_email") == ADMIN_EMAIL
        assert "rejected_fields" in doc
        assert isinstance(doc["rejected_fields"], list)
        assert "max_ai_messages" in doc["rejected_fields"]


# ---------- 3. WHATSAPP DISPLAY PHONE ----------

class TestWhatsappDisplayPhone:

    def test_set_whatsapp_display_phone(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers,
                         json={
                             "whatsapp_display_phone": "5491199998888",
                             "contact_phone": "5491100000000",
                         }, timeout=20)
        assert r.status_code == 200, r.text

    def test_public_catalog_returns_separate_fields(self):
        r = requests.get(f"{BASE_URL}/api/public/catalog/demo-inmobiliaria", timeout=20)
        assert r.status_code == 200
        data = r.json()
        # tenant nested
        tenant = data.get("tenant", data)
        assert "whatsapp_display_phone" in tenant, f"keys: {list(tenant.keys())}"
        assert tenant.get("whatsapp_display_phone") == "5491199998888"
        if "whatsapp_phone" in tenant:
            assert tenant["whatsapp_phone"] == "5491100000000"


# ---------- 4. AI COPY GENERATOR ----------

class TestAICopyGenerator:

    def test_ai_generate_no_description(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/auth/tenant/branding/ai-generate",
                          headers=admin_headers, json={}, timeout=30)
        assert r.status_code == 400

    def test_ai_generate_description_too_long(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/auth/tenant/branding/ai-generate",
                          headers=admin_headers,
                          json={"description": "x" * 501}, timeout=30)
        assert r.status_code == 400

    def test_ai_generate_fallback_no_llm(self, admin_headers):
        # OPENAI_API_KEY no configurada -> fallback ai_enabled=false sin error 500
        r = requests.post(f"{BASE_URL}/api/auth/tenant/branding/ai-generate",
                          headers=admin_headers,
                          json={"description": "soy una clinica odontologica"},
                          timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "business_tagline" in body
        assert "features" in body
        assert "steps" in body
        assert "ai_enabled" in body
        # En entorno actual sin OPENAI_API_KEY -> fallback
        if not body["ai_enabled"]:
            assert isinstance(body["features"], list)
            assert isinstance(body["steps"], list)
            assert body["business_tagline"]  # fallback string

    def test_ai_generate_asesor_403(self, asesor_token):
        headers = {"Authorization": f"Bearer {asesor_token}"}
        r = requests.post(f"{BASE_URL}/api/auth/tenant/branding/ai-generate",
                          headers=headers,
                          json={"description": "test"}, timeout=20)
        assert r.status_code == 403, f"Asesor should be denied. Got: {r.status_code} {r.text}"

    def test_ai_generate_unauth(self):
        r = requests.post(f"{BASE_URL}/api/auth/tenant/branding/ai-generate",
                          json={"description": "test"}, timeout=20)
        assert r.status_code in (401, 403)


# ---------- 5. REGRESION ----------

class TestRegression:

    def test_login_admin(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                          timeout=20)
        assert r.status_code == 200

    def test_get_branding(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        # custom_features debe ser lista (fix iter9)
        assert isinstance(data.get("custom_features", []), list)
        assert isinstance(data.get("custom_steps", []), list)

    def test_public_catalog_basic(self):
        r = requests.get(f"{BASE_URL}/api/public/catalog/demo-inmobiliaria", timeout=20)
        assert r.status_code == 200
        d = r.json()
        tenant = d.get("tenant", d)
        assert "tenant_id" in tenant or "name" in tenant or "business_name" in tenant

    def test_leads_endpoint(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers, timeout=20)
        assert r.status_code == 200
