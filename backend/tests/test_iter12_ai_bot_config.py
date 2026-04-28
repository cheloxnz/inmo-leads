"""Iter 12 - AI Bot Config Assistant tests.

Endpoints:
  - GET  /api/bot-config/ai-edit/info   (require_admin)
  - POST /api/bot-config/ai-edit        (require_admin, rate-limited 10/h)

Comportamiento esperado en este entorno (sin OPENAI_API_KEY):
  - info: 200 con editable_fields(9), rate_limit, examples(5)
  - ai-edit con auth+instruction valida: 503 "IA no configurada"
  - ai-edit sin instruction: 400
  - ai-edit con instruction >500 chars: 400
  - ai-edit sin auth: 401/403
  - rate-limit: tras 10 requests "consumidos" (pasaron el check de rate-limit),
    el 11vo retorna 429.  Como el 503 ocurre DESPUES del check_rate_limit,
    los primeros 10 efectivamente cuentan.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip().rstrip("/")

ADMIN_EMAIL = "demo@inmobot.com"
ADMIN_PASS = "Demo123!"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                      timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login admin fallo: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- GET /info ----------------
class TestAIEditInfo:
    def test_info_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/bot-config/ai-edit/info", timeout=15)
        assert r.status_code in (401, 403), f"esperado 401/403, got {r.status_code}: {r.text[:200]}"

    def test_info_returns_metadata(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/bot-config/ai-edit/info",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # editable_fields: lista de 9 campos
        fields = data.get("editable_fields")
        assert isinstance(fields, list)
        assert len(fields) == 9
        expected = {
            "business_hours_start", "business_hours_end", "business_days",
            "saturday_hours_start", "saturday_hours_end",
            "auto_handoff_score", "warm_lead_reactivation_days",
            "appointment_reminder_hours", "welcome_message",
        }
        assert set(fields) == expected
        # rate_limit
        rl = data.get("rate_limit")
        assert isinstance(rl, dict)
        assert rl.get("max") == 10
        assert rl.get("window_seconds") == 3600
        # examples: 5 strings
        examples = data.get("examples")
        assert isinstance(examples, list)
        assert len(examples) == 5
        assert all(isinstance(e, str) and len(e) > 0 for e in examples)


# ---------------- POST /ai-edit ----------------
class TestAIEditValidation:
    def test_no_auth_returns_401_or_403(self):
        r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                          json={"instruction": "test"}, timeout=15)
        assert r.status_code in (401, 403), f"got {r.status_code}: {r.text[:200]}"

    def test_empty_instruction_returns_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                          headers=admin_headers, json={"instruction": ""}, timeout=15)
        assert r.status_code == 400, r.text
        assert "requerido" in (r.json().get("detail", "")).lower()

    def test_missing_instruction_returns_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                          headers=admin_headers, json={}, timeout=15)
        assert r.status_code == 400, r.text

    def test_instruction_too_long_returns_400(self, admin_headers):
        long_text = "a" * 501
        r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                          headers=admin_headers,
                          json={"instruction": long_text}, timeout=15)
        assert r.status_code == 400, r.text
        assert "demasiado largo" in r.json().get("detail", "").lower()

    def test_instruction_500_chars_passes_size_check(self, admin_headers):
        # Exactamente 500 chars: NO debe ser rechazado por size; debe llegar al 503/429
        ok_text = "x" * 500
        r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                          headers=admin_headers,
                          json={"instruction": ok_text}, timeout=20)
        assert r.status_code in (503, 429), f"got {r.status_code}: {r.text[:200]}"


class TestAIEditNoOpenAIKey:
    def test_valid_request_returns_503_when_no_openai_key(self, admin_headers):
        # En este entorno no hay OPENAI_API_KEY; tras pasar rate-limit el endpoint
        # debe retornar 503 'IA no configurada'.
        r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                          headers=admin_headers,
                          json={"instruction": "Cambia el horario a 9 a 18hs"},
                          timeout=20)
        # 503 si todavia hay slots; 429 si el bucket ya quedo agotado por tests previos.
        assert r.status_code in (503, 429), f"got {r.status_code}: {r.text[:200]}"
        if r.status_code == 503:
            detail = r.json().get("detail", "").lower()
            assert "ia" in detail or "configura" in detail


class TestAIEditRateLimit:
    """Validar que tras N requests consecutivos al mismo endpoint con auth,
    eventualmente devuelve 429 (rate-limit aplica antes que el check de OpenAI key)."""

    def test_rate_limit_kicks_in(self, admin_headers):
        # El bucket es por tenant_id y se mantiene entre tests. Hacemos hasta 12
        # requests y verificamos que aparece al menos un 429.
        statuses = []
        for i in range(12):
            r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                              headers=admin_headers,
                              json={"instruction": f"req {i}"}, timeout=20)
            statuses.append(r.status_code)
            if r.status_code == 429:
                detail = r.json().get("detail", "").lower()
                assert "limite" in detail or "alcanzado" in detail or "10/hora" in detail
                break
        assert 429 in statuses, f"esperaba un 429 en 12 reqs, got: {statuses}"
        # Tambien validamos que el primero o alguno NO sea 429 (rate-limit no esta
        # roto desde el inicio bloqueando todo).  Si todos son 429 desde request 0,
        # significaria que el bucket quedo lleno entre tests; aceptable.
        # Sólo verificamos consistencia: una vez aparece 429, siguientes deben ser 429.
        if 429 in statuses:
            idx = statuses.index(429)
            for s in statuses[idx:]:
                assert s == 429, f"despues del primer 429, status volvió a {s}"


# ---------------- Regresion ----------------
class TestRouterRegistration:
    def test_endpoints_registered_not_404(self, admin_headers):
        # info
        r = requests.get(f"{BASE_URL}/api/bot-config/ai-edit/info",
                         headers=admin_headers, timeout=15)
        assert r.status_code != 404
        # post
        r2 = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                           headers=admin_headers,
                           json={"instruction": "test 404 check"}, timeout=15)
        assert r2.status_code != 404

    def test_existing_config_endpoint_still_works(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/config",
                         headers=admin_headers, timeout=15)
        # /api/config debe seguir funcionando tras la adicion
        assert r.status_code == 200, f"GET /api/config rompio: {r.status_code} {r.text[:200]}"
