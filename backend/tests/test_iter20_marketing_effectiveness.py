"""Iter20 — Coach Effectiveness dashboard
GET /api/coach/effectiveness?days=N — funnel + timeseries + top celebrations.
"""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestEffectivenessAuth:
    def test_no_auth_returns_401_or_403(self):
        r = requests.get(f"{BASE}/api/coach/effectiveness")
        assert r.status_code in (401, 403)


class TestEffectivenessStructure:
    def test_default_structure(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness", headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("window_days", "funnel", "funnel_rates", "by_platform",
                  "in_window", "timeseries", "top_celebrations"):
            assert k in d, f"missing {k}"
        assert d["window_days"] == 30
        # funnel keys
        for k in ("shares_explicit", "preview_views", "html_views",
                  "leads_captured", "signups_converted"):
            assert k in d["funnel"]
            assert isinstance(d["funnel"][k], int)
        # rates
        for k in ("view_to_lead", "lead_to_signup", "share_to_view", "overall_share_to_signup"):
            assert k in d["funnel_rates"]
            assert isinstance(d["funnel_rates"][k], (int, float))
            assert 0 <= d["funnel_rates"][k] <= 100  # clamped
        # by_platform
        for k in ("twitter", "linkedin", "download"):
            assert k in d["by_platform"]
            assert isinstance(d["by_platform"][k], int)
        # in_window
        for k in ("leads", "converted"):
            assert k in d["in_window"]
        # lists
        assert isinstance(d["timeseries"], list)
        assert isinstance(d["top_celebrations"], list)

    def test_funnel_rates_no_division_by_zero(self, admin_headers):
        # Demo tenant may have zero shares; ensure rate is 0 not 500
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=1", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        for k, v in d["funnel_rates"].items():
            assert 0 <= v <= 100, f"{k}={v} not clamped"

    def test_top_celebrations_fields(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness", headers=admin_headers)
        d = r.json()
        # Top is sorted desc by shares_total and limited to 10
        assert len(d["top_celebrations"]) <= 10
        prev = None
        for tc in d["top_celebrations"]:
            for k in ("celebration_id", "celebration_type", "title",
                      "shares_total", "preview_views", "html_views",
                      "leads", "converted"):
                assert k in tc, f"missing {k} in top_celebration"
            # created_at should be string (ISO) if present
            if "created_at" in tc and tc["created_at"]:
                assert isinstance(tc["created_at"], str)
            if prev is not None:
                assert tc["shares_total"] <= prev
            prev = tc["shares_total"]

    def test_timeseries_sorted_and_keys(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=90", headers=admin_headers)
        d = r.json()
        prev_date = None
        for entry in d["timeseries"]:
            assert "date" in entry and "leads" in entry and "converted" in entry
            # YYYY-MM-DD format
            assert len(entry["date"]) == 10 and entry["date"][4] == "-"
            if prev_date is not None:
                assert entry["date"] >= prev_date
            prev_date = entry["date"]


class TestEffectivenessClamp:
    def test_days_clamped_to_max_90(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=200", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["window_days"] == 90

    def test_days_clamped_to_min_1(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=0", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["window_days"] == 1

    def test_days_negative_clamped_to_min_1(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=-5", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["window_days"] == 1

    def test_days_invalid_returns_422(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=foo", headers=admin_headers)
        # FastAPI int conversion -> 422
        assert r.status_code in (422, 400)

    def test_days_7_window(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=7", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["window_days"] == 7


class TestEffectivenessConsistency:
    def test_in_window_le_total(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=30", headers=admin_headers)
        d = r.json()
        # in_window cannot exceed total funnel counts
        assert d["in_window"]["leads"] <= d["funnel"]["leads_captured"]
        assert d["in_window"]["converted"] <= d["funnel"]["signups_converted"]

    def test_by_platform_sum_le_shares_total(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness", headers=admin_headers)
        d = r.json()
        bp = d["by_platform"]
        # Note: shares.total includes also "facebook", "copy" platforms not in by_platform.
        # So sum can be <= shares_explicit
        plat_sum = bp["twitter"] + bp["linkedin"] + bp["download"]
        assert plat_sum <= d["funnel"]["shares_explicit"]
