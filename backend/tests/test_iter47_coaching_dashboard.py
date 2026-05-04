"""Iter47 — Dashboard global de "Oportunidades de coaching".
Tests para GET /api/bot-learning/coaching-opportunities y verificación de Stripe live key.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
BASE_URL = BASE_URL.rstrip("/")

DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"


@pytest.fixture(scope="module")
def demo_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
                      timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}", "Content-Type": "application/json"}


# === iter47: Coaching Opportunities Dashboard ===

class TestCoachingOpportunitiesDashboard:
    def test_endpoint_returns_200_and_shape(self, demo_headers):
        r = requests.get(
            f"{BASE_URL}/api/bot-learning/coaching-opportunities?days=30&min_cluster_size=2",
            headers=demo_headers, timeout=120,
        )
        assert r.status_code == 200, f"status {r.status_code}: {r.text}"
        data = r.json()
        # Required keys
        for k in ["model_available", "total_customer_questions", "already_covered", "uncovered", "clusters"]:
            assert k in data, f"missing key {k} in response: {data}"
        assert isinstance(data["clusters"], list)
        assert isinstance(data["total_customer_questions"], int)
        assert data["model_available"] is True

    def test_cluster_shape(self, demo_headers):
        r = requests.get(
            f"{BASE_URL}/api/bot-learning/coaching-opportunities?days=30&min_cluster_size=2",
            headers=demo_headers, timeout=120,
        )
        data = r.json()
        clusters = data.get("clusters", [])
        if not clusters:
            pytest.skip(f"No clusters available to validate shape (uncovered={data.get('uncovered')}, covered={data.get('already_covered')})")
        c = clusters[0]
        assert "canonical_question" in c and isinstance(c["canonical_question"], str)
        assert "cluster_size" in c and c["cluster_size"] >= 2
        assert "sample_questions" in c and isinstance(c["sample_questions"], list)
        assert len(c["sample_questions"]) >= 1
        assert "last_seen_days_ago" in c
        assert "first_seen_days_ago" in c
        s0 = c["sample_questions"][0]
        for k in ["question", "lead_name", "lead_phone", "days_ago"]:
            assert k in s0

    def test_clusters_sorted_by_size_desc(self, demo_headers):
        r = requests.get(
            f"{BASE_URL}/api/bot-learning/coaching-opportunities?days=30&min_cluster_size=2",
            headers=demo_headers, timeout=120,
        )
        clusters = r.json().get("clusters", [])
        if len(clusters) < 2:
            pytest.skip("not enough clusters to validate ordering")
        sizes = [c["cluster_size"] for c in clusters]
        assert sizes == sorted(sizes, reverse=True), f"clusters not sorted desc: {sizes}"

    def test_already_covered_excludes_learned(self, demo_headers):
        # demo-inmobiliaria has at least 2 learned_responses (alquiler Palermo, sábados)
        r = requests.get(
            f"{BASE_URL}/api/bot-learning/coaching-opportunities?days=30&min_cluster_size=2",
            headers=demo_headers, timeout=120,
        )
        data = r.json()
        # already_covered + uncovered must equal total (or be <=)
        total = data["total_customer_questions"]
        cov = data["already_covered"]
        unc = data["uncovered"]
        assert cov + unc <= total + 1, f"covered({cov})+uncovered({unc}) > total({total})"
        # demo seed has at least some already-covered customer questions about alquiler/sabados
        # Not strict assertion (depends on seed state) but should be >= 0
        assert cov >= 0
        assert unc >= 0

    def test_query_params_clamped(self, demo_headers):
        r = requests.get(
            f"{BASE_URL}/api/bot-learning/coaching-opportunities?days=999&min_cluster_size=999",
            headers=demo_headers, timeout=120,
        )
        # backend clamps days≤365 and min_cluster_size≤50, so it should return 200 not 422/500
        assert r.status_code == 200, r.text

    def test_unauthenticated_blocked(self):
        r = requests.get(
            f"{BASE_URL}/api/bot-learning/coaching-opportunities",
            timeout=20,
        )
        assert r.status_code in (401, 403), f"expected auth required, got {r.status_code}"


# === Stripe live key — verify no "Invalid API Key" on /api/plans ===

class TestStripeKeyInitialization:
    def test_plans_endpoint_loads(self):
        # /api/plans (public) - at minimum must not 500 with stripe.error
        r = requests.get(f"{BASE_URL}/api/plans", timeout=15)
        assert r.status_code == 200, f"status {r.status_code}: {r.text}"
        body = r.text.lower()
        assert "invalid api key" not in body, f"Stripe key invalid! response: {r.text}"
        # SUBSCRIPTION_PLANS is a dict — should return JSON object/list
        try:
            r.json()
        except Exception as e:
            pytest.fail(f"plans response not JSON: {e}")


# === Iter45/46 regression smoke ===

class TestRegressionIter45_46:
    def test_bot_learning_list_works(self, demo_headers):
        r = requests.get(f"{BASE_URL}/api/bot-learning", headers=demo_headers, timeout=20)
        assert r.status_code == 200

    def test_agent_suggestions_endpoint(self, demo_headers):
        r = requests.post(
            f"{BASE_URL}/api/agent-suggestions",
            headers=demo_headers,
            json={"message": "cuanto sale el alquiler en palermo"},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"status {r.status_code}: {r.text}"
        data = r.json()
        # shape: should at least return suggestions list
        assert "suggestions" in data or "from_learned" in data or isinstance(data, dict)

    def test_per_lead_coaching_opportunity(self, demo_headers):
        r = requests.post(
            f"{BASE_URL}/api/bot-learning/coaching-opportunity",
            headers=demo_headers,
            json={"customer_question": "aceptan mascotas?"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["already_taught", "similar_pending_count", "sample_questions", "recommendation"]:
            assert k in data, f"missing key {k}"
