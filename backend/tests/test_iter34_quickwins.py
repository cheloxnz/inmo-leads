"""Iter34 QuickWins backend tests.

Covers:
- Onboarding Tour (status/complete)
- Upsell run + UTM links in email (send_upsell_unmet_demand signature)
- Waitlist admin threshold alert (maybe_alert_superadmin idempotency/cooldown)
- Reset demo data endpoint (400/404/403/200 + include_leads)
- Regression of existing superadmin endpoints
"""
import os
import sys
import uuid
import asyncio
import inspect
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inmobot-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASS = "Admin123!"
ADMIN_EMAIL = "demo@inmobot.com"
ADMIN_PASS = "Demo123!"


# ---------------- fixtures ----------------

@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Superadmin login failed: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Demo admin login failed: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


def _hdr(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# ---------------- onboarding ----------------

class TestOnboarding:
    def test_status_returns_boolean(self, super_token):
        r = requests.get(f"{API}/auth/onboarding/status", headers=_hdr(super_token), timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "completed" in data
        assert isinstance(data["completed"], bool)

    def test_complete_sets_flag(self, admin_token):
        r = requests.post(
            f"{API}/auth/onboarding/complete",
            headers=_hdr(admin_token),
            json={"skipped": False},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # verify
        r2 = requests.get(f"{API}/auth/onboarding/status", headers=_hdr(admin_token), timeout=10)
        assert r2.status_code == 200
        assert r2.json()["completed"] is True

    def test_onboarding_requires_auth(self):
        r = requests.get(f"{API}/auth/onboarding/status", timeout=10)
        assert r.status_code in (401, 403)


# ---------------- upsell + UTM ----------------

class TestUpsellUTM:
    def test_upsell_run_ok(self, super_token):
        r = requests.post(f"{API}/superadmin/upsell/run", headers=_hdr(super_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # endpoint should report a dict with candidate/sent counts (loose check)
        assert isinstance(data, dict)

    def test_upsell_history_ok(self, super_token):
        r = requests.get(f"{API}/superadmin/upsell/history", headers=_hdr(super_token), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), (list, dict))

    def test_send_upsell_unmet_demand_accepts_tenant_id_kwarg(self):
        """Signature check: must accept tenant_id kwarg."""
        sys.path.insert(0, "/app/backend")
        from email_service import EmailService
        sig = inspect.signature(EmailService.send_upsell_unmet_demand)
        assert "tenant_id" in sig.parameters

    def test_upsell_email_contains_utm_links(self):
        """Direct source-code inspection of URL composition."""
        src = open("/app/backend/email_service.py", encoding="utf-8").read()
        assert "utm_source=upsell" in src
        assert "utm_medium=email" in src
        assert "utm_campaign=unmet_demand" in src
        assert "utm_content=" in src


# ---------------- waitlist admin alert ----------------

class TestWaitlistAdminAlert:
    def _run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)

    def test_maybe_alert_threshold_and_idempotency(self):
        """Populate product_waitlist >= threshold and call maybe_alert_superadmin twice."""
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from waitlist_alert_service import maybe_alert_superadmin

        # Force a low threshold to avoid sending 20 real emails and so we don't
        # depend on SMTP. SUPERADMIN_EMAIL must exist; if not, test still runs.
        os.environ["WAITLIST_ADMIN_ALERT_THRESHOLD"] = "3"
        os.environ["WAITLIST_ADMIN_ALERT_COOLDOWN_DAYS"] = "30"
        # Avoid actually sending SMTP: override SUPERADMIN_EMAIL to empty to short-circuit
        prev_super = os.environ.get("SUPERADMIN_EMAIL")

        async def run():
            mongo_url = os.environ["MONGO_URL"]
            db_name = os.environ["DB_NAME"]
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            tenant_id = f"TEST_tenant_{uuid.uuid4().hex[:6]}"
            product_id = f"TEST_prod_{uuid.uuid4().hex[:6]}"

            # Seed tenant so enrichment works
            await db.tenants.insert_one({
                "tenant_id": tenant_id,
                "business_name": "TEST_biz",
                "subscription_plan": "pro",
            })
            try:
                # Case A: below threshold -> no alert
                for i in range(2):
                    await db.product_waitlist.insert_one({
                        "tenant_id": tenant_id,
                        "product_id": product_id,
                        "lead_phone": f"+569{i:07d}",
                        "notified_at": None,
                        "asked_at": "2026-01-01T00:00:00+00:00",
                    })
                # Temporarily disable SMTP path by unsetting SUPERADMIN_EMAIL
                os.environ["SUPERADMIN_EMAIL"] = ""
                r1 = await maybe_alert_superadmin(db, tenant_id, product_id, "TEST_prod_name")
                assert r1 is False
                count_alerts = await db.waitlist_admin_alerts.count_documents({
                    "tenant_id": tenant_id, "product_id": product_id
                })
                assert count_alerts == 0, "No alert doc expected when below threshold / no email"

                # Case B: set SUPERADMIN_EMAIL fake and go above threshold.
                # We don't want a real send, so mock EmailService.send_waitlist_threshold_alert
                os.environ["SUPERADMIN_EMAIL"] = "test_waitlist@example.com"
                import email_service as es_mod

                orig = es_mod.EmailService.send_waitlist_threshold_alert

                async def fake_send(self, **kw):
                    return True

                es_mod.EmailService.send_waitlist_threshold_alert = fake_send

                # add more to cross threshold (now total 3)
                await db.product_waitlist.insert_one({
                    "tenant_id": tenant_id,
                    "product_id": product_id,
                    "lead_phone": "+56998765432",
                    "notified_at": None,
                    "asked_at": "2026-01-02T00:00:00+00:00",
                })

                try:
                    r2 = await maybe_alert_superadmin(db, tenant_id, product_id, "TEST_prod_name")
                    assert r2 is True, "Alert should fire when >= threshold"
                    alerts = await db.waitlist_admin_alerts.find(
                        {"tenant_id": tenant_id, "product_id": product_id}, {"_id": 0}
                    ).to_list(10)
                    assert len(alerts) == 1
                    a = alerts[0]
                    assert a["leads_count"] >= 3
                    assert a["delivered"] is True
                    assert a["tenant_id"] == tenant_id

                    # Idempotency: second call within cooldown => no new doc
                    r3 = await maybe_alert_superadmin(db, tenant_id, product_id, "TEST_prod_name")
                    assert r3 is False
                    alerts2 = await db.waitlist_admin_alerts.count_documents(
                        {"tenant_id": tenant_id, "product_id": product_id}
                    )
                    assert alerts2 == 1, "Cooldown should prevent duplicate alert"
                finally:
                    es_mod.EmailService.send_waitlist_threshold_alert = orig
            finally:
                # cleanup
                await db.product_waitlist.delete_many({"tenant_id": tenant_id})
                await db.waitlist_admin_alerts.delete_many({"tenant_id": tenant_id})
                await db.tenants.delete_many({"tenant_id": tenant_id})
                if prev_super is None:
                    os.environ.pop("SUPERADMIN_EMAIL", None)
                else:
                    os.environ["SUPERADMIN_EMAIL"] = prev_super
                client.close()

        asyncio.run(run())


# ---------------- reset demo data ----------------

class TestResetDemoData:
    def test_requires_confirm(self, super_token):
        r = requests.post(
            f"{API}/superadmin/tenants/__superadmin__/reset-demo-data",
            headers=_hdr(super_token),
            json={"confirm": False},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_unknown_tenant_returns_404(self, super_token):
        r = requests.post(
            f"{API}/superadmin/tenants/__nope_xxx__/reset-demo-data",
            headers=_hdr(super_token),
            json={"confirm": True},
            timeout=15,
        )
        assert r.status_code == 404, r.text

    def test_non_superadmin_forbidden(self, admin_token):
        r = requests.post(
            f"{API}/superadmin/tenants/__superadmin__/reset-demo-data",
            headers=_hdr(admin_token),
            json={"confirm": True},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403 for non-superadmin, got {r.status_code} {r.text}"

    def test_reset_real_tenant_returns_counts(self, super_token):
        # Target demo-inmobiliaria so we don't wipe superadmin's context.
        r = requests.post(
            f"{API}/superadmin/tenants/demo-inmobiliaria/reset-demo-data",
            headers=_hdr(super_token),
            json={"confirm": True, "include_leads": False},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tenant_id"] == "demo-inmobiliaria"
        for k in ("products_deleted", "waitlist_deleted", "waitlist_alerts_deleted"):
            assert k in data
            assert isinstance(data[k], int)
        # include_leads False => keys absent
        assert "leads_deleted" not in data

    def test_reset_with_include_leads(self, super_token):
        r = requests.post(
            f"{API}/superadmin/tenants/demo-inmobiliaria/reset-demo-data",
            headers=_hdr(super_token),
            json={"confirm": True, "include_leads": True},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("leads_deleted", "conversations_deleted", "messages_deleted"):
            assert k in data and isinstance(data[k], int)


# ---------------- regression ----------------

class TestRegression:
    def test_admin_report_run(self, super_token):
        r = requests.post(f"{API}/superadmin/admin-report/run", headers=_hdr(super_token), timeout=30)
        assert r.status_code == 200, r.text

    def test_unmet_demand(self, super_token):
        r = requests.get(f"{API}/superadmin/unmet-demand", headers=_hdr(super_token), timeout=15)
        assert r.status_code == 200, r.text

    def test_public_demand_detected(self):
        r = requests.get(f"{API}/public/demand-detected", timeout=15)
        assert r.status_code == 200, r.text
