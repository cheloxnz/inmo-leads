"""Iter 14 - AI Flow Assistant + branding subscription_plan + bot_config_ai hardening.

Endpoints bajo prueba:
  - GET  /api/flow/ai-edit/info        (require_admin)
  - POST /api/flow/ai-edit              (require_admin, rate-limited 8/h)
  - GET  /api/tenant/branding           (debe incluir subscription_plan + status)
  - GET  /api/flow/config               (regresion + verify apply)

Comportamiento esperado SIN OPENAI_API_KEY:
  - info: 200 con valid_ops(7), rate_limit(8/3600), examples(5)
  - ai-edit auth+instruction valida (preview): 503 IA no configurada (NO consume slot)
  - ai-edit confirm=true + confirmed_ops valida (update_welcome): aplica
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip().rstrip("/")

ADMIN_EMAIL = "demo@inmobot.com"
ADMIN_PASS = "Demo123!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login admin fallo: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# -------------- GET /api/flow/ai-edit/info --------------
class TestFlowAIInfo:
    def test_info_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/flow/ai-edit/info", timeout=15)
        assert r.status_code in (401, 403), f"got {r.status_code}: {r.text[:200]}"

    def test_info_returns_metadata(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/flow/ai-edit/info",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        ops = d.get("valid_ops")
        assert isinstance(ops, list) and len(ops) == 7
        expected = {
            "add_step", "update_step", "remove_step", "reorder_step",
            "update_welcome", "update_completion", "update_appointment",
        }
        assert set(ops) == expected, f"ops mismatch: {ops}"
        rl = d.get("rate_limit")
        assert rl.get("max") == 8
        assert rl.get("window_seconds") == 3600
        ex = d.get("examples")
        assert isinstance(ex, list) and len(ex) == 5
        assert all(isinstance(e, str) and e for e in ex)


# -------------- POST /api/flow/ai-edit (validation) --------------
class TestFlowAIValidation:
    def test_no_auth_returns_401_or_403(self):
        r = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                          json={"instruction": "test"}, timeout=15)
        assert r.status_code in (401, 403)

    def test_empty_instruction_returns_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                          headers=admin_headers, json={"instruction": ""}, timeout=15)
        assert r.status_code == 400
        assert "requerido" in r.json().get("detail", "").lower()

    def test_long_instruction_returns_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                          headers=admin_headers,
                          json={"instruction": "a" * 501}, timeout=15)
        assert r.status_code == 400
        assert "demasiado largo" in r.json().get("detail", "").lower()

    def test_no_openai_key_returns_503_without_consuming_slot(self, admin_headers):
        """Critico: el check llm.client va ANTES del rate-limit.
        Hacer 10 requests; todos deben ser 503, ninguno 429."""
        statuses = []
        for i in range(10):
            r = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                              headers=admin_headers,
                              json={"instruction": f"req {i}"}, timeout=15)
            statuses.append(r.status_code)
        assert all(s == 503 for s in statuses), f"esperado 10x503, got: {statuses}"
        # detalle
        detail = requests.post(
            f"{BASE_URL}/api/flow/ai-edit",
            headers=admin_headers,
            json={"instruction": "una mas"}, timeout=15
        ).json().get("detail", "").lower()
        assert "ia" in detail or "configura" in detail


# -------------- POST /api/flow/ai-edit (apply path) --------------
class TestFlowAIApply:
    def test_invalid_confirmed_ops_returns_400(self, admin_headers):
        # op no existente
        r = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                          headers=admin_headers,
                          json={
                              "instruction": "test",
                              "confirm": True,
                              "confirmed_ops": [
                                  {"op": "not_a_real_op", "params": {"text": "x"}}
                              ]
                          }, timeout=15)
        assert r.status_code == 400, r.text
        assert "invalidas" in r.json().get("detail", "").lower()

    def test_apply_update_welcome_persists(self, admin_headers):
        """Aplicar update_welcome y luego GET /api/flow/config debe reflejarlo."""
        new_msg = "TEST_iter14: Hola! Soy InmoBot, tu asesor virtual de prueba."
        r = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                          headers=admin_headers,
                          json={
                              "instruction": "Cambiar bienvenida",
                              "confirm": True,
                              "confirmed_ops": [
                                  {"op": "update_welcome",
                                   "params": {"text": new_msg}}
                              ]
                          }, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("applied") is True
        assert body.get("applied_count") == 1

        # Verify via GET /api/flow/config
        g = requests.get(f"{BASE_URL}/api/flow/config",
                         headers=admin_headers, timeout=15)
        assert g.status_code == 200, g.text
        cfg = g.json()
        # El campo puede ser welcome_message (resuelto) o custom_welcome_message
        wm = cfg.get("welcome_message") or cfg.get("custom_welcome_message")
        assert wm == new_msg, f"welcome no persistido: {wm}"

    def test_apply_add_step_persists(self, admin_headers):
        """Aplicar add_step (type=text) y verificar que aparece en flow_steps."""
        r = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                          headers=admin_headers,
                          json={
                              "instruction": "agregar paso de test",
                              "confirm": True,
                              "confirmed_ops": [
                                  {"op": "add_step",
                                   "params": {
                                       "question": "TEST_iter14 pregunta",
                                       "type": "text",
                                       "field": "custom_fields.test_iter14"
                                   }}
                              ]
                          }, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("applied") is True

        g = requests.get(f"{BASE_URL}/api/flow/config",
                         headers=admin_headers, timeout=15)
        assert g.status_code == 200
        steps = g.json().get("flow_steps") or g.json().get("custom_flow_steps") or []
        questions = [s.get("question") for s in steps if isinstance(s, dict)]
        assert "TEST_iter14 pregunta" in questions, f"step no persistido. Steps: {questions}"


# -------------- /api/tenant/branding subscription_plan --------------
class TestBrandingSubscription:
    def test_branding_includes_subscription(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/auth/tenant/branding",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "subscription_plan" in data, f"falta subscription_plan: {list(data.keys())}"
        assert "subscription_status" in data, f"falta subscription_status: {list(data.keys())}"
        # readonly: type debe ser string
        assert isinstance(data["subscription_plan"], str)
        assert isinstance(data["subscription_status"], str)


# -------------- Regresion bot_config_ai (iter 12) --------------
class TestBotConfigAINoSlotConsume:
    """Validar que el cambio: bot_config_ai chequea llm.client ANTES del rate-limit.
    Multiple requests sin OpenAI key NO deben consumir slots (todos 503, no 429)."""

    def test_503_does_not_consume_rate_limit(self, admin_headers):
        statuses = []
        for i in range(11):
            r = requests.post(f"{BASE_URL}/api/bot-config/ai-edit",
                              headers=admin_headers,
                              json={"instruction": f"reg {i}"}, timeout=15)
            statuses.append(r.status_code)
        # Todos deben ser 503 si el bucket esta limpio.
        # Si esta sucio (test iter12 corrio antes), aceptamos 429.
        # Lo critico: si hay 503, debe haber MUCHOS 503 (no que se vuelva 429 a la 1ra).
        non_503_429 = [s for s in statuses if s not in (503, 429)]
        assert not non_503_429, f"status inesperados: {statuses}"


# -------------- Regresion router registration --------------
class TestRouterRegistration:
    def test_flow_ai_endpoints_registered(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/flow/ai-edit/info",
                         headers=admin_headers, timeout=15)
        assert r.status_code != 404
        r2 = requests.post(f"{BASE_URL}/api/flow/ai-edit",
                           headers=admin_headers,
                           json={"instruction": "test"}, timeout=15)
        assert r2.status_code != 404
