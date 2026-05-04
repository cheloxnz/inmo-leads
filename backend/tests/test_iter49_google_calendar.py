"""
iter49 - Google Calendar OAuth per-tenant.
Tests endpoints that don't require a real OAuth completion (requires manual
human consent in Google). We test:
- /calendar/status while disconnected
- /oauth/calendar/start (admin) returns correct authorization_url
- /oauth/calendar/start (non-admin) -> 403
- /oauth/calendar/callback error handling (no params, invalid state)
- /calendar/events (GET/POST) when not connected -> 400
- /calendar/disconnect idempotent
"""
import os
import requests
import pytest
from urllib.parse import urlparse, parse_qs

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inmobot-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "demo@inmobot.com"
ADMIN_PASS = "Demo123!"

EXPECTED_REDIRECT_URI = "https://inmobot-preview.preview.emergentagent.com/api/oauth/calendar/callback"
EXPECTED_CLIENT_ID_PREFIX = "774383207527-"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def asesor_token(admin_headers):
    """Create a non-admin user (role=asesor) so we can test 403 on /oauth/calendar/start."""
    import uuid
    email = f"TEST_iter49_asesor_{uuid.uuid4().hex[:8]}@inmobot.com"
    pw = "Asesor123!"
    # /auth/register is admin-only and creates an agent (role=asesor)
    r = requests.post(
        f"{API}/auth/register",
        headers=admin_headers,
        json={"email": email, "password": pw, "name": "Asesor Test", "phone": "+5491100000000"},
        timeout=15,
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"Could not create asesor user: {r.status_code} {r.text}")
    rl = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    if rl.status_code != 200:
        pytest.skip("Could not log in as asesor")
    return rl.json()["access_token"]


# --- /calendar/status ---
class TestCalendarStatus:
    def test_status_disconnected(self, admin_headers):
        r = requests.get(f"{API}/calendar/status", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["configured"] is True
        # If a previous human test connected, this could be True. Accept either but log.
        assert "connected" in d
        assert "connected_email" in d
        assert "connected_at" in d


# --- /oauth/calendar/start ---
class TestOauthStart:
    def test_admin_returns_authorization_url(self, admin_headers):
        r = requests.get(f"{API}/oauth/calendar/start", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        url = r.json().get("authorization_url", "")
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?"), url
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        assert qs.get("client_id", [""])[0].startswith(EXPECTED_CLIENT_ID_PREFIX)
        assert qs.get("redirect_uri", [""])[0] == EXPECTED_REDIRECT_URI
        assert qs.get("response_type", [""])[0] == "code"
        assert qs.get("access_type", [""])[0] == "offline"
        assert qs.get("prompt", [""])[0] == "consent"
        assert "state" in qs and len(qs["state"][0]) > 10
        scope = qs.get("scope", [""])[0]
        assert "calendar.events" in scope
        assert "userinfo.email" in scope

    def test_no_auth_unauthorized(self):
        r = requests.get(f"{API}/oauth/calendar/start", timeout=15)
        assert r.status_code in (401, 403)

    def test_asesor_forbidden(self, asesor_token):
        r = requests.get(
            f"{API}/oauth/calendar/start",
            headers={"Authorization": f"Bearer {asesor_token}"},
            timeout=15,
        )
        assert r.status_code == 403, r.text


# --- /oauth/calendar/callback ---
class TestOauthCallback:
    def test_callback_no_params_redirects_error(self):
        r = requests.get(f"{API}/oauth/calendar/callback", timeout=15, allow_redirects=False)
        assert r.status_code in (302, 307)
        loc = r.headers.get("location", "")
        assert "calendar=error" in loc and "missing_params" in loc

    def test_callback_invalid_state_redirects_error(self):
        r = requests.get(
            f"{API}/oauth/calendar/callback",
            params={"code": "fake_code", "state": "this_state_does_not_exist_xxx"},
            timeout=15,
            allow_redirects=False,
        )
        assert r.status_code in (302, 307)
        loc = r.headers.get("location", "")
        assert "calendar=error" in loc and "invalid_state" in loc

    def test_callback_explicit_error_param(self):
        r = requests.get(
            f"{API}/oauth/calendar/callback",
            params={"error": "access_denied"},
            timeout=15, allow_redirects=False,
        )
        assert r.status_code in (302, 307)
        loc = r.headers.get("location", "")
        assert "calendar=error" in loc and "access_denied" in loc


# --- /calendar/events when not connected ---
class TestEventsWithoutConnection:
    def _is_connected(self, headers):
        r = requests.get(f"{API}/calendar/status", headers=headers, timeout=15)
        return r.json().get("connected") if r.status_code == 200 else False

    def test_get_events_without_connection_400(self, admin_headers):
        if self._is_connected(admin_headers):
            pytest.skip("tenant already connected; skipping disconnected-state test")
        r = requests.get(f"{API}/calendar/events", headers=admin_headers, timeout=15)
        assert r.status_code == 400
        assert "no conectado" in r.json().get("detail", "").lower()

    def test_post_event_without_connection_400(self, admin_headers):
        if self._is_connected(admin_headers):
            pytest.skip("tenant already connected; skipping disconnected-state test")
        body = {
            "summary": "Test", "start_iso": "2026-05-10T14:00:00-03:00",
            "end_iso": "2026-05-10T15:00:00-03:00",
        }
        r = requests.post(f"{API}/calendar/events", headers=admin_headers, json=body, timeout=15)
        assert r.status_code == 400


# --- /calendar/disconnect idempotent ---
class TestDisconnect:
    def test_disconnect_idempotent(self, admin_headers):
        r = requests.post(f"{API}/calendar/disconnect", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert "disconnected" in r.json()
        # second time should still be 200
        r2 = requests.post(f"{API}/calendar/disconnect", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert r2.json().get("disconnected") in (True, False)
