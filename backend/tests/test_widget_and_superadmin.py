"""Tests for widget tracking, widget analytics, widget.js drop-in, and SuperAdmin metrics."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inmobot-preview.preview.emergentagent.com").rstrip("/")
TENANT_ID = "demo-inmobiliaria"
ADMIN_EMAIL = "demo@inmobot.com"
ADMIN_PASS = "Demo123!"
SUPERADMIN_EMAIL = "admin@inmobot.com"
SUPERADMIN_PASS = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def superadmin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


# ===== Widget tracking (público, sin auth) =====
class TestWidgetTracking:
    def test_track_view(self):
        r = requests.post(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/track",
                          json={"event_type": "view", "session_id": "TEST_sess_1"}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "ok"

    def test_track_click_product(self):
        r = requests.post(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/track",
                          json={"event_type": "click_product", "product_id": "PROD_TEST_1",
                                "session_id": "TEST_sess_1"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_track_click_whatsapp(self):
        r = requests.post(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/track",
                          json={"event_type": "click_whatsapp", "product_id": "PROD_TEST_1"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_track_ai_search(self):
        r = requests.post(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/track",
                          json={"event_type": "ai_search", "query": "TEST_casa con pileta"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_track_lead_generated(self):
        r = requests.post(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/track",
                          json={"event_type": "lead_generated"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_track_invalid_event(self):
        r = requests.post(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/track",
                          json={"event_type": "INVALID"}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "error"

    def test_track_tenant_not_found(self):
        r = requests.post(f"{BASE_URL}/api/public/catalog/does-not-exist-xyz/track",
                          json={"event_type": "view"}, timeout=10)
        assert r.status_code == 404


# ===== Widget Analytics (admin) =====
class TestWidgetAnalytics:
    def test_analytics_default_days(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/widget/analytics?days=30", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data
        s = data["summary"]
        for k in ("views", "unique_visitors", "clicks_product", "clicks_whatsapp",
                  "ai_searches", "leads_generated", "click_through_rate", "conversion_rate"):
            assert k in s
        assert isinstance(data.get("by_day"), list)
        assert isinstance(data.get("top_products"), list)
        assert isinstance(data.get("top_queries"), list)
        # Tras inserts del bloque anterior, views >= 1
        assert s["views"] >= 1

    def test_analytics_7_days(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/widget/analytics?days=7", headers=h, timeout=15)
        assert r.status_code == 200
        assert r.json().get("period_days") == 7

    def test_analytics_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/widget/analytics", timeout=10)
        assert r.status_code in (401, 403)


# ===== Widget.js drop-in =====
class TestWidgetJs:
    def test_widget_js_content(self):
        r = requests.get(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/widget.js", timeout=10)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "javascript" in ct.lower(), ct
        assert r.headers.get("Cache-Control")
        assert r.headers.get("Access-Control-Allow-Origin") == "*"
        body = r.text
        assert "iframe" in body
        assert TENANT_ID in body
        # https (respetando x-forwarded-proto ingress)
        assert "https://" in body, f"widget.js should use https:// in URL; got: {body[:300]}"

    def test_widget_js_tenant_independent(self):
        # Aunque el tenant no exista, sigue devolviendo un script (stateless)
        r = requests.get(f"{BASE_URL}/api/public/catalog/any-tenant-x/widget.js", timeout=10)
        assert r.status_code == 200


# ===== SuperAdmin metrics =====
class TestSuperAdminMetrics:
    def test_metrics_requires_superadmin(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/superadmin/metrics", headers=h, timeout=15)
        assert r.status_code == 403

    def test_metrics_superadmin(self, superadmin_token):
        h = {"Authorization": f"Bearer {superadmin_token}"}
        r = requests.get(f"{BASE_URL}/api/superadmin/metrics", headers=h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("mrr", "arr_estimated", "tenants", "plans_distribution", "usage", "leads", "revenue_last_30d"):
            assert k in d, f"missing {k}"
        for k in ("total", "active", "past_due", "cancelled", "churned_last_30d", "churn_rate_pct"):
            assert k in d["tenants"]
        for k in ("period", "total_ai_messages", "total_overage_messages", "total_extra_messages"):
            assert k in d["usage"]

    def test_tenants_usage(self, superadmin_token):
        h = {"Authorization": f"Bearer {superadmin_token}"}
        r = requests.get(f"{BASE_URL}/api/superadmin/tenants/usage", headers=h, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_tenants_usage_forbidden_for_admin(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/superadmin/tenants/usage", headers=h, timeout=15)
        assert r.status_code == 403

    def test_global_widget_analytics(self, superadmin_token):
        h = {"Authorization": f"Bearer {superadmin_token}"}
        r = requests.get(f"{BASE_URL}/api/superadmin/widget/analytics", headers=h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "per_tenant" in d

    def test_global_widget_analytics_forbidden(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/superadmin/widget/analytics", headers=h, timeout=15)
        assert r.status_code == 403


# ===== Regresión: endpoints anteriores siguen funcionando =====
class TestRegression:
    def test_public_catalog(self):
        r = requests.get(f"{BASE_URL}/api/public/catalog/{TENANT_ID}", timeout=15)
        assert r.status_code == 200

    def test_billing_plans(self):
        r = requests.get(f"{BASE_URL}/api/plans", timeout=15)
        assert r.status_code == 200

    def test_stats_summary(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/leads/stats/summary", headers=h, timeout=15)
        assert r.status_code == 200

    def test_flood_tracking_does_not_break(self):
        # 10 requests seguidos -- no debe romper
        ok = 0
        for i in range(10):
            r = requests.post(f"{BASE_URL}/api/public/catalog/{TENANT_ID}/track",
                              json={"event_type": "view", "session_id": f"flood_{i}"}, timeout=10)
            if r.status_code == 200:
                ok += 1
        assert ok >= 9  # permitir 1 flaky
