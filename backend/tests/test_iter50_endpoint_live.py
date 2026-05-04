"""Live endpoint tests for iter50 POST /api/calendar/availability."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "demo@inmobot.com", "password": "Demo123!"},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token
    return token


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def test_availability_no_auth_returns_401():
    r = requests.post(
        f"{BASE_URL}/api/calendar/availability",
        json={"start_iso": "2026-05-10T15:00:00-03:00"},
        timeout=15,
    )
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text}"


def test_availability_missing_start_iso_returns_400(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/calendar/availability",
        json={},
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 400
    body = r.json()
    detail = body.get("detail", "")
    assert "start_iso" in detail and "requerido" in detail.lower()


def test_availability_invalid_start_iso_returns_400(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/calendar/availability",
        json={"start_iso": "foo"},
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 400
    body = r.json()
    detail = body.get("detail", "")
    assert "inválido" in detail.lower() or "invalido" in detail.lower() or "start_iso" in detail


def test_availability_disconnected_tenant_returns_connected_false(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/calendar/availability",
        json={"start_iso": "2026-05-10T15:00:00-03:00", "duration_minutes": 60},
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is False
    assert body["available"] is True
    assert body["alternatives"] == []
    assert "preferred_start" in body
    assert "preferred_end" in body


def test_availability_response_time_under_500ms_when_disconnected(auth_headers):
    """Cuando el tenant no está conectado, no debe llamar a Google."""
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/calendar/availability",
        json={"start_iso": "2026-05-15T10:00:00-03:00"},
        headers=auth_headers,
        timeout=15,
    )
    elapsed_ms = (time.time() - start) * 1000
    assert r.status_code == 200
    assert elapsed_ms < 500, f"response took {elapsed_ms:.0f}ms (expected <500ms)"


def test_availability_with_z_suffix_iso(auth_headers):
    """Acepta ISO con sufijo Z (UTC)."""
    r = requests.post(
        f"{BASE_URL}/api/calendar/availability",
        json={"start_iso": "2026-05-10T15:00:00Z"},
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is False
