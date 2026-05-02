"""
Iter 35 - Seed Demo Data + 3 code-review quick wins
Tests:
  - POST /api/superadmin/tenants/{id}/seed-demo-data (all scenarios)
  - Reset demo data response shape (partial:bool, errors)
  - waitlist_admin_alerts cooldown idempotency (datetime native)
  - APP_URL env warning in email_service
  - Regression: auth login, onboarding status, upsell run, admin-report run
"""
import os
import logging
import pytest
import requests
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL is not set"
API = f"{BASE_URL}/api"

SUPER = {"email": "admin@inmobot.com", "password": "Admin123!"}
DEMO = {"email": "demo@inmobot.com", "password": "Demo123!"}

# Use a template-restaurante tenant so we don't pollute demo-inmobiliaria
SEED_TENANT = "test-pizzeria-e2e"
FAKE_TENANT = "tenant-does-not-exist-xyz"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{API}/auth/login", json=SUPER, timeout=30)
    assert r.status_code == 200, f"superadmin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def demo_token():
    r = requests.post(f"{API}/auth/login", json=DEMO, timeout=30)
    assert r.status_code == 200, f"demo login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- 1. Seed Demo Data ----------
class TestSeedDemoData:
    def test_seed_requires_superadmin(self, demo_token):
        r = requests.post(
            f"{API}/superadmin/tenants/{SEED_TENANT}/seed-demo-data",
            json={"products_count": 2, "waitlist_per_product": 1, "include_leads": False, "force": False},
            headers=_h(demo_token), timeout=30,
        )
        assert r.status_code == 403, f"expected 403 non-superadmin, got {r.status_code}"

    def test_seed_unknown_tenant_404(self, super_token):
        r = requests.post(
            f"{API}/superadmin/tenants/{FAKE_TENANT}/seed-demo-data",
            json={"products_count": 2, "waitlist_per_product": 1, "include_leads": False, "force": False},
            headers=_h(super_token), timeout=30,
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"

    def test_seed_reset_then_seed_fresh(self, super_token):
        # Clean slate first
        r_reset = requests.post(
            f"{API}/superadmin/tenants/{SEED_TENANT}/reset-demo-data",
            json={"confirm": True, "include_leads": True},
            headers=_h(super_token), timeout=60,
        )
        assert r_reset.status_code == 200
        rd = r_reset.json()
        # response shape check (Mejora 2)
        assert "partial" in rd and rd["partial"] is False
        assert "errors" not in rd or rd.get("errors") in (None, [])
        assert "products_deleted" in rd
        assert "leads_deleted" in rd  # include_leads=True

        # Now seed
        r = requests.post(
            f"{API}/superadmin/tenants/{SEED_TENANT}/seed-demo-data",
            json={"products_count": 6, "waitlist_per_product": 3, "include_leads": True, "force": False},
            headers=_h(super_token), timeout=90,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tenant_id"] == SEED_TENANT
        assert d.get("skipped") is False
        assert d["template_used"] == "restaurante"
        assert d["products_inserted"] >= 1
        assert d["waitlist_inserted"] >= 1
        assert d["leads_inserted"] >= 1
        assert d["conversations_inserted"] >= 1
        assert d["messages_inserted"] >= 1

    def test_seed_idempotent_without_force(self, super_token):
        # SEED_TENANT should have products after previous test — expect skipped
        r = requests.post(
            f"{API}/superadmin/tenants/{SEED_TENANT}/seed-demo-data",
            json={"products_count": 3, "waitlist_per_product": 1, "include_leads": False, "force": False},
            headers=_h(super_token), timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("skipped") is True, f"expected skipped=True, got {d}"
        assert d.get("existing_products", 0) >= 1
        assert "reason" in d

    def test_seed_with_force_adds_more(self, super_token):
        # Count before
        # Use force=True: should add more products
        r = requests.post(
            f"{API}/superadmin/tenants/{SEED_TENANT}/seed-demo-data",
            json={"products_count": 3, "waitlist_per_product": 1, "include_leads": False, "force": True},
            headers=_h(super_token), timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("skipped") is False
        assert d["products_inserted"] >= 1


# ---------- 2. Reset Demo Data response shape (Mejora 2) ----------
class TestResetDemoShape:
    def test_reset_happy_path_partial_false(self, super_token):
        r = requests.post(
            f"{API}/superadmin/tenants/{SEED_TENANT}/reset-demo-data",
            json={"confirm": True, "include_leads": False},
            headers=_h(super_token), timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tenant_id"] == SEED_TENANT
        assert "products_deleted" in d
        assert "waitlist_deleted" in d
        assert "waitlist_alerts_deleted" in d
        assert d["partial"] is False
        assert "errors" not in d  # omitted when empty

    def test_reset_missing_confirm_400(self, super_token):
        r = requests.post(
            f"{API}/superadmin/tenants/{SEED_TENANT}/reset-demo-data",
            json={"confirm": False, "include_leads": False},
            headers=_h(super_token), timeout=30,
        )
        assert r.status_code == 400

    def test_reset_unknown_tenant_404(self, super_token):
        r = requests.post(
            f"{API}/superadmin/tenants/{FAKE_TENANT}/reset-demo-data",
            json={"confirm": True, "include_leads": False},
            headers=_h(super_token), timeout=30,
        )
        assert r.status_code == 404


# ---------- 3. Waitlist alert cooldown (Mejora 1 - BSON datetime) ----------
class TestWaitlistAlertCooldown:
    @pytest.mark.asyncio
    async def test_cooldown_idempotent_within_day(self):
        """Two calls within cooldown → only 1 insert in waitlist_admin_alerts."""
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        import waitlist_alert_service as was

        # Ensure SUPERADMIN_EMAIL is set for this test
        os.environ.setdefault("SUPERADMIN_EMAIL", "test-superadmin@example.com")
        # Lower threshold for the test
        os.environ["WAITLIST_ADMIN_ALERT_THRESHOLD"] = "5"

        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        test_tenant = "TEST_cooldown_iter35"

        # cleanup
        await db.waitlist_admin_alerts.delete_many({"tenant_id": test_tenant})
        await db.product_waitlist.delete_many({"tenant_id": test_tenant})
        await db.tenants.delete_many({"tenant_id": test_tenant})
        await db.tenants.insert_one({
            "tenant_id": test_tenant,
            "name": "TEST cooldown",
            "business_name": "TEST cooldown",
            "template_id": "servicios",
        })

        # 6 unnotified waitlist entries → crosses threshold=5
        for i in range(6):
            await db.product_waitlist.insert_one({
                "tenant_id": test_tenant,
                "lead_phone": f"999000{i:04d}",
                "product_id": "prodX",
                "product_name": "ProdX",
                "notified_at": None,
            })

        # Patch EmailService.send_waitlist_threshold_alert to no-op (avoid SMTP)
        from email_service import EmailService
        async def _fake_send(*a, **kw):
            return True
        with patch.object(EmailService, "send_waitlist_threshold_alert", _fake_send):
            r1 = await was.maybe_alert_superadmin(db, test_tenant, "prodX", "ProdX")
            r2 = await was.maybe_alert_superadmin(db, test_tenant, "prodX", "ProdX")

        count = await db.waitlist_admin_alerts.count_documents({"tenant_id": test_tenant})
        assert count == 1, f"expected 1 alert, got {count} (r1={r1}, r2={r2})"
        assert r1 is True
        assert r2 is False

        # Verify sent_at is a native datetime (BSON), not string
        doc = await db.waitlist_admin_alerts.find_one({"tenant_id": test_tenant})
        import datetime as _dt
        assert isinstance(doc["sent_at"], _dt.datetime), f"sent_at type={type(doc['sent_at'])}"

        # cleanup
        await db.product_waitlist.delete_many({"tenant_id": test_tenant})
        await db.waitlist_admin_alerts.delete_many({"tenant_id": test_tenant})
        await db.tenants.delete_many({"tenant_id": test_tenant})


# ---------- 4. APP_URL warning in email_service (Mejora 3) ----------
class TestAppUrlWarning:
    @pytest.mark.asyncio
    async def test_upsell_logs_warning_when_app_url_missing(self, caplog):
        import sys
        sys.path.insert(0, "/app/backend")
        from email_service import EmailService

        caplog.set_level(logging.WARNING)

        saved = os.environ.pop("APP_URL", None)
        try:
            svc = EmailService(db=None)
            # Patch low-level send_email to no-op
            async def _noop(*a, **kw):
                return True
            with patch.object(EmailService, "send_email", _noop):
                await svc.send_upsell_unmet_demand(
                    to_email="noreply-test@example.com",
                    business_name="TestTenant",
                    demand={"leads_count": 3, "value_usd": 100, "top_products": []},
                    tenant_id="test-t",
                )
        finally:
            if saved is not None:
                os.environ["APP_URL"] = saved

        msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("APP_URL" in m for m in msgs), f"warning not logged. records={msgs}"

    @pytest.mark.asyncio
    async def test_waitlist_alert_logs_warning_when_app_url_missing(self, caplog):
        import sys
        sys.path.insert(0, "/app/backend")
        from email_service import EmailService

        caplog.set_level(logging.WARNING)

        saved = os.environ.pop("APP_URL", None)
        try:
            svc = EmailService(db=None)
            async def _noop(*a, **kw):
                return True
            with patch.object(EmailService, "send_email", _noop):
                await svc.send_waitlist_threshold_alert(
                    to_email="noreply-test@example.com",
                    tenant_id="t",
                    business_name="TestTenant",
                    plan="pro",
                    product_name="X",
                    product_id="px",
                    leads_count=6,
                    threshold=5,
                )
        finally:
            if saved is not None:
                os.environ["APP_URL"] = saved

        msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("APP_URL" in m for m in msgs), f"warning not logged. records={msgs}"


# ---------- 5. Regression ----------
class TestRegression:
    def test_login_demo_200(self):
        r = requests.post(f"{API}/auth/login", json=DEMO, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 20

    def test_login_super_200(self, super_token):
        assert super_token and len(super_token) > 20

    def test_onboarding_status(self, demo_token):
        r = requests.get(f"{API}/auth/onboarding/status", headers=_h(demo_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        # Response shape uses "completed" (not "onboarding_completed")
        assert "completed" in d

    def test_upsell_run(self, super_token):
        r = requests.post(f"{API}/superadmin/upsell/run", headers=_h(super_token), timeout=60)
        assert r.status_code == 200, r.text

    def test_admin_report_run(self, super_token):
        r = requests.post(f"{API}/superadmin/admin-report/run", headers=_h(super_token), timeout=60)
        assert r.status_code == 200, r.text
