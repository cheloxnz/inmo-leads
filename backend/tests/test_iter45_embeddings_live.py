"""Live integration tests for iter45 (embeddings) against the running backend.

Endpoints under test:
- GET  /api/bot-learning/embeddings-status
- POST /api/bot-learning/backfill-embeddings
- POST /api/bot-learning (creates learned response w/ embedding)
- POST /api/agent-suggestions (paraphrase match via embedding; negative test for unrelated)
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inmobot-preview.preview.emergentagent.com").rstrip("/")
EMAIL = "demo@inmobot.com"
PASSWORD = "Demo123!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_embeddings_status(headers):
    r = requests.get(f"{BASE_URL}/api/bot-learning/embeddings-status", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("available") is True
    assert body.get("dim") == 384
    assert "model" in body
    assert "tenant_coverage" in body


def test_backfill_idempotent(headers):
    # Run twice; second should be idempotent (total_pending = 0).
    r1 = requests.post(f"{BASE_URL}/api/bot-learning/backfill-embeddings", headers=headers, timeout=120)
    assert r1.status_code == 200, r1.text
    r2 = requests.post(f"{BASE_URL}/api/bot-learning/backfill-embeddings", headers=headers, timeout=120)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2.get("total_pending", 0) == 0, f"backfill not idempotent: {body2}"


def test_create_learned_response_with_embedding(headers):
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "question": f"TEST_{suffix} Cuanto sale el alquiler del depto en Palermo?",
        "answer": f"TEST_{suffix} 850 mil pesos por mes con expensas aparte.",
        "category": "pricing",
    }
    r = requests.post(f"{BASE_URL}/api/bot-learning", headers=headers, json=payload, timeout=60)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert data.get("id")
    # Endpoint must NOT leak embedding vector to clients.
    assert "embedding" not in data
    # Sanity: present in list
    rl = requests.get(f"{BASE_URL}/api/bot-learning", headers=headers, timeout=30)
    assert rl.status_code == 200
    items = rl.json() if isinstance(rl.json(), list) else rl.json().get("items", [])
    assert any(it.get("id") == data["id"] for it in items)


def test_agent_suggestions_paraphrase_match(headers):
    # Ensure there's a learned response to match (idempotent insert)
    requests.post(
        f"{BASE_URL}/api/bot-learning",
        headers=headers,
        json={
            "question": "Cuanto sale el alquiler del depto en Palermo?",
            "answer": "850 mil pesos por mes con expensas aparte.",
            "category": "pricing",
        },
        timeout=60,
    )
    # Allow async embedding generation (lazy load)
    time.sleep(2)

    payload = {"message": "cuanto vale rentar el inmueble en palermo"}
    r = requests.post(f"{BASE_URL}/api/agent-suggestions", headers=headers, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    suggestions = data.get("suggestions", [])
    assert isinstance(suggestions, list)
    assert len(suggestions) >= 1, f"expected paraphrase to match, got: {data}"
    top = suggestions[0]
    assert "match_method" in top
    # We expect at least one suggestion via embedding (semantic) for this paraphrase
    methods = [s.get("match_method") for s in suggestions]
    assert "embedding" in methods, f"expected at least one embedding match, got methods={methods}"


def test_agent_suggestions_unrelated_no_false_positives(headers):
    payload = {"message": "como va a estar el clima manana en marte"}
    r = requests.post(f"{BASE_URL}/api/agent-suggestions", headers=headers, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    suggestions = data.get("suggestions", [])
    # should not generate confident matches for completely unrelated query
    assert len(suggestions) == 0, f"expected no false positives, got: {suggestions}"
