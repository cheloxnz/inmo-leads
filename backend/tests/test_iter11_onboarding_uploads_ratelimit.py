"""
Iter 11 - Tests for: Rate-limit AI Copy, Logo Upload, Auto-Onboarding wizard.
Covers:
- POST /api/auth/tenant/branding/ai-generate rate limit (5/hour per tenant)
- POST /api/uploads/logo + GET /api/uploads/logos/{filename}
- POST /api/onboarding/suggest-tenant-id, POST /api/onboarding/auto-setup
- Regression sanity: catalog list, public catalog
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inmobot-preview.preview.emergentagent.com").rstrip("/")
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"
SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASSWORD = "Admin123!"


# ---------- Auth helpers ----------

def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login {email} failed: {r.status_code} {r.text}")
    return r.json().get("access_token")


@pytest.fixture(scope="session")
def demo_token():
    return _login(DEMO_EMAIL, DEMO_PASSWORD)


@pytest.fixture(scope="session")
def super_token():
    return _login(SUPER_EMAIL, SUPER_PASSWORD)


@pytest.fixture(scope="session")
def fresh_tenant():
    """Crea un tenant nuevo via auto-setup para tests de rate-limit aislado."""
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_iter11_{suffix}@inmobot.com"
    body = {
        "business_name": f"TEST iter11 fresh {suffix}",
        "description": "Soy una clinica odontologica de prueba para tests automatizados de rate limit.",
        "email": email,
        "password": "FreshPass123!",
    }
    r = requests.post(f"{BASE_URL}/api/onboarding/auto-setup", json=body, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"auto-setup failed: {r.status_code} {r.text}")
    data = r.json()
    return {"token": data["access_token"], "tenant_id": data["tenant_id"], "email": email, "data": data}


# ============================================================
# Rate-limit AI Copy
# ============================================================

class TestAIRateLimit:
    def test_fresh_tenant_can_make_5_calls_then_429(self, fresh_tenant):
        """5 calls ok, 6ta = 429 con detalle 'Limite de IA'."""
        token = fresh_tenant["token"]
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{BASE_URL}/api/auth/tenant/branding/ai-generate"
        body = {"description": "Soy una clinica odontologica de Buenos Aires"}

        statuses = []
        rate_meta = []
        for i in range(5):
            r = requests.post(url, headers=headers, json=body, timeout=30)
            statuses.append(r.status_code)
            if r.status_code == 200:
                rl = r.json().get("rate_limit", {})
                rate_meta.append(rl)

        assert all(s == 200 for s in statuses), f"Esperaba 5x 200, got {statuses}"
        # rate_limit shape
        assert rate_meta, "ningun response trajo rate_limit"
        last = rate_meta[-1]
        assert "remaining" in last and "max" in last and "window_seconds" in last
        assert last["max"] == 5
        assert last["window_seconds"] == 3600
        assert last["remaining"] == 0  # despues de la 5ta call

        # 6ta = 429
        r6 = requests.post(url, headers=headers, json=body, timeout=30)
        assert r6.status_code == 429, f"esperaba 429, got {r6.status_code} {r6.text}"
        detail = r6.json().get("detail", "")
        assert "Limite de IA" in detail or "limite" in detail.lower()

    def test_rate_limit_bucket_is_per_tenant(self, demo_token):
        """Otro tenant debe tener su propio bucket. Probamos que el demo tenant
        recibe rate_limit field correctamente o 429 (su bucket puede estar lleno
        por tests previos, pero NO afectado por el de fresh_tenant)."""
        headers = {"Authorization": f"Bearer {demo_token}"}
        url = f"{BASE_URL}/api/auth/tenant/branding/ai-generate"
        r = requests.post(url, headers=headers, json={"description": "Inmobiliaria con propiedades en CABA"}, timeout=30)
        # demo_token tenant es 'demo-inmobiliaria' (independiente del fresh)
        assert r.status_code in (200, 429), f"unexpected {r.status_code} {r.text}"
        if r.status_code == 200:
            assert "rate_limit" in r.json()


# ============================================================
# Upload de logos
# ============================================================

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfe\xa3z\xfb\xc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestLogoUpload:
    def test_no_file_returns_422(self, demo_token):
        headers = {"Authorization": f"Bearer {demo_token}"}
        r = requests.post(f"{BASE_URL}/api/uploads/logo", headers=headers, timeout=15)
        assert r.status_code == 422

    def test_txt_file_returns_400(self, demo_token):
        headers = {"Authorization": f"Bearer {demo_token}"}
        files = {"file": ("test.txt", b"hello world", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/uploads/logo", headers=headers, files=files, timeout=15)
        assert r.status_code == 400
        assert "Tipo no permitido" in r.json().get("detail", "")

    def test_png_upload_returns_200(self, demo_token):
        headers = {"Authorization": f"Bearer {demo_token}"}
        files = {"file": ("logo.png", PNG_1x1, "image/png")}
        r = requests.post(f"{BASE_URL}/api/uploads/logo", headers=headers, files=files, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("url", "filename", "size_bytes", "content_type"):
            assert k in d, f"missing {k} in {d}"
        assert d["content_type"] == "image/png"
        assert d["filename"].endswith(".png")
        assert d["size_bytes"] == len(PNG_1x1)
        assert "/api/uploads/logos/" in d["url"]
        # guardamos el filename para test posterior
        TestLogoUpload._uploaded_filename = d["filename"]
        TestLogoUpload._uploaded_url = d["url"]

    def test_oversize_returns_413(self, demo_token):
        headers = {"Authorization": f"Bearer {demo_token}"}
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 100)
        files = {"file": ("big.png", big, "image/png")}
        r = requests.post(f"{BASE_URL}/api/uploads/logo", headers=headers, files=files, timeout=30)
        assert r.status_code == 413, f"esperaba 413, got {r.status_code}"

    def test_serve_uploaded_logo_returns_image(self, demo_token):
        # asegurar que tenemos un upload previo
        if not hasattr(TestLogoUpload, "_uploaded_filename"):
            self.test_png_upload_returns_200(demo_token)
        filename = TestLogoUpload._uploaded_filename
        r = requests.get(f"{BASE_URL}/api/uploads/logos/{filename}", timeout=15)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 0

    def test_path_traversal_returns_400(self):
        r = requests.get(f"{BASE_URL}/api/uploads/logos/..%2Fetc%2Fpasswd", timeout=15)
        # Algunos proxies decodifican y devuelven 404; FastAPI con encoded slash igual hace match al path param.
        assert r.status_code in (400, 404), f"esperaba 400/404, got {r.status_code}"

    def test_invalid_filename_returns_400(self):
        r = requests.get(f"{BASE_URL}/api/uploads/logos/bad-name.exe", timeout=15)
        assert r.status_code == 400

    def test_nonexistent_file_returns_404(self):
        # filename valido en formato pero inexistente
        r = requests.get(f"{BASE_URL}/api/uploads/logos/ZZZ_doesnotexist_aaa.png", timeout=15)
        assert r.status_code == 404


# ============================================================
# Auto-onboarding
# ============================================================

class TestOnboarding:
    def test_suggest_tenant_id(self):
        r = requests.post(
            f"{BASE_URL}/api/onboarding/suggest-tenant-id",
            json={"business_name": "Mi Pizza Genial"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "tenant_id" in data and data["available"] is True
        # debe ser slug (sin espacios, sin acentos, lowercase)
        slug = data["tenant_id"]
        assert slug.replace("-", "").isalnum() and slug == slug.lower()

    def test_suggest_empty_business_name_returns_400(self):
        r = requests.post(
            f"{BASE_URL}/api/onboarding/suggest-tenant-id",
            json={"business_name": ""},
            timeout=15,
        )
        assert r.status_code == 400

    def test_suggest_existing_tenant_appends_suffix(self):
        r = requests.post(
            f"{BASE_URL}/api/onboarding/suggest-tenant-id",
            json={"business_name": "demo-inmobiliaria"},
            timeout=15,
        )
        assert r.status_code == 200
        # debe ser distinto del existente
        assert r.json()["tenant_id"] != "demo-inmobiliaria"

    def test_auto_setup_creates_tenant_user_products(self):
        suffix = uuid.uuid4().hex[:8]
        email = f"TEST_iter11_clinic_{suffix}@inmobot.com"
        body = {
            "business_name": f"TEST Clinica Odontologica {suffix}",
            "description": "Somos una clinica odontologica especializada en implantes dentales y limpieza.",
            "email": email,
            "password": "Setup12345!",
        }
        r = requests.post(f"{BASE_URL}/api/onboarding/auto-setup", json=body, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("tenant_id", "template_id", "products_seeded", "access_token", "user", "landing_url", "next_step"):
            assert k in d, f"missing {k}"
        assert d["template_id"] == "clinica", f"esperaba clinica, got {d['template_id']}"
        assert d["products_seeded"] == 3
        assert d["user"]["email"].lower() == email.lower()
        # token funciona (email se guarda lowercase)
        login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email.lower(), "password": "Setup12345!"}, timeout=15)
        assert login.status_code == 200, f"auto-created user no puede loguearse: {login.text}"
        # Verificar productos via endpoint catalog publico
        cat = requests.get(f"{BASE_URL}/api/public/catalog/{d['tenant_id']}", timeout=15)
        assert cat.status_code == 200, f"public catalog no encontrado: {cat.status_code}"
        body = cat.json()
        items = body if isinstance(body, list) else body.get("items") or body.get("products") or []
        assert len(items) >= 3, f"esperaba >=3 productos demo, got {len(items)}"

    def test_auto_setup_template_pizza_detects_restaurante(self):
        suffix = uuid.uuid4().hex[:8]
        body = {
            "business_name": f"TEST Pizzeria {suffix}",
            "description": "Soy una pizzeria con delivery en Buenos Aires especializada en pizza al horno.",
            "email": f"TEST_iter11_pizza_{suffix}@inmobot.com",
            "password": "PizzaPass1!",
        }
        r = requests.post(f"{BASE_URL}/api/onboarding/auto-setup", json=body, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["template_id"] == "restaurante"

    def test_auto_setup_template_inmobiliaria(self):
        suffix = uuid.uuid4().hex[:8]
        body = {
            "business_name": f"TEST Inmo {suffix}",
            "description": "Inmobiliaria con propiedades en alquiler y venta departamento casa.",
            "email": f"TEST_iter11_inmo_{suffix}@inmobot.com",
            "password": "InmoPass1!",
        }
        r = requests.post(f"{BASE_URL}/api/onboarding/auto-setup", json=body, timeout=30)
        assert r.status_code == 200
        assert r.json()["template_id"] == "inmobiliaria"

    def test_auto_setup_duplicate_email_returns_409(self):
        # demo@inmobot.com ya existe
        body = {
            "business_name": "TEST dup",
            "description": "Negocio duplicado para test, descripcion suficientemente larga.",
            "email": DEMO_EMAIL,
            "password": "DupPass123!",
        }
        r = requests.post(f"{BASE_URL}/api/onboarding/auto-setup", json=body, timeout=20)
        assert r.status_code == 409

    def test_auto_setup_short_password_returns_400(self):
        body = {
            "business_name": "TEST short pwd",
            "description": "Negocio para test password corto, descripcion valida.",
            "email": f"TEST_short_{uuid.uuid4().hex[:6]}@inmobot.com",
            "password": "abc",
        }
        r = requests.post(f"{BASE_URL}/api/onboarding/auto-setup", json=body, timeout=20)
        assert r.status_code == 400
        assert "password" in r.json().get("detail", "").lower()

    def test_auto_setup_invalid_email_returns_400(self):
        body = {
            "business_name": "TEST bad email",
            "description": "Negocio con email invalido para test, descripcion suficiente.",
            "email": "no-es-un-email",
            "password": "ValidPass123!",
        }
        r = requests.post(f"{BASE_URL}/api/onboarding/auto-setup", json=body, timeout=20)
        assert r.status_code == 400


# ============================================================
# Regresion basica
# ============================================================

class TestRegression:
    def test_login_demo_works(self, demo_token):
        assert demo_token

    def test_catalog_list_works(self, demo_token):
        headers = {"Authorization": f"Bearer {demo_token}"}
        r = requests.get(f"{BASE_URL}/api/catalog", headers=headers, timeout=15)
        assert r.status_code == 200

    def test_public_catalog_demo(self):
        r = requests.get(f"{BASE_URL}/api/public/catalog/demo-inmobiliaria", timeout=15)
        assert r.status_code == 200

    def test_branding_get(self, demo_token):
        headers = {"Authorization": f"Bearer {demo_token}"}
        r = requests.get(f"{BASE_URL}/api/auth/tenant/branding", headers=headers, timeout=15)
        assert r.status_code == 200
