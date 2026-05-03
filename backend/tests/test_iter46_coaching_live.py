"""
Live integration tests for coaching opportunity endpoint (Iter46).
Uses real preview backend with seeded demo tenant.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inmobot-preview.preview.emergentagent.com").rstrip("/")
EMAIL = "demo@inmobot.com"
PASSWORD = "Demo123!"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def test_coaching_empty_question(headers):
    """Empty question → not_enough."""
    r = requests.post(f"{BASE_URL}/api/bot-learning/coaching-opportunity",
                      headers=headers, json={}, timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert data["recommendation"] == "not_enough"
    assert "reason" in data


def test_coaching_pets_question_recommends_teach(headers):
    """Federico's case: pets question with 4+ similar pending leads → teach."""
    r = requests.post(f"{BASE_URL}/api/bot-learning/coaching-opportunity",
                      headers=headers,
                      json={"customer_question": "Aceptan mascotas en el departamento?",
                            "exclude_lead_phone": "5491199999999"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    print(f"Pets coaching response: {data}")
    assert data["already_taught"] is False, f"Should NOT be already_taught: {data}"
    assert data["similar_pending_count"] >= 3, f"Expected >=3 similar pending: {data}"
    assert data["recommendation"] == "teach"
    assert len(data["sample_questions"]) >= 1
    for s in data["sample_questions"]:
        assert "question" in s
        assert "lead_name" in s


def test_coaching_already_taught_palermo_price(headers):
    """Pregunta sobre precio de Palermo ya está enseñada en learned_responses."""
    r = requests.post(f"{BASE_URL}/api/bot-learning/coaching-opportunity",
                      headers=headers,
                      json={"customer_question": "Cuanto cuesta el alquiler en Palermo?"},
                      timeout=30)
    assert r.status_code == 200
    data = r.json()
    print(f"Palermo coaching response: {data}")
    assert data["already_taught"] is True, f"Should be already_taught: {data}"
    assert data["recommendation"] == "already_taught"


def test_coaching_unrelated_question_not_enough(headers):
    """Pregunta sin demanda similar → not_enough."""
    r = requests.post(f"{BASE_URL}/api/bot-learning/coaching-opportunity",
                      headers=headers,
                      json={"customer_question": "Cual es el clima en Marte hoy en grados kelvin?"},
                      timeout=30)
    assert r.status_code == 200
    data = r.json()
    print(f"Unrelated coaching response: {data}")
    assert data["recommendation"] in ("not_enough", "already_taught")
    if data["recommendation"] == "not_enough":
        assert data["similar_pending_count"] < 3


def test_agent_suggestions_regression(headers):
    """Regression: /api/agent-suggestions still works."""
    r = requests.post(f"{BASE_URL}/api/agent-suggestions",
                      headers=headers,
                      json={"message": "cuanto sale el alquiler", "lead_phone": "+5491100000001"},
                      timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "suggestions" in data


def test_bot_learning_save_regression(headers):
    """Regression: POST /api/bot-learning still works."""
    r = requests.post(f"{BASE_URL}/api/bot-learning",
                      headers=headers,
                      json={"question": "TEST_iter46 regression question?",
                            "answer": "TEST_iter46 regression answer"},
                      timeout=20)
    assert r.status_code in (200, 201)
    data = r.json()
    assert "id" in data
