"""Iter22 - P1/P2 features:
- Email new_referral_commission disparado al crear commission active
- /api/coach/effectiveness ahora devuelve commission_summary
- Trial ending soon: nudge + email
- Weekly digest: email
- UTM/persistence en signup ref
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_TENANT = "demo-inmobiliaria"
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture()
def cleanup_tracker():
    items = []
    yield items
    cli = MongoClient(os.environ["MONGO_URL"])
    d = cli[os.environ["DB_NAME"]]
    for coll, flt in items:
        d[coll].delete_many(flt)
    cli.close()


def _run_async(coro_factory):
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    async def runner():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            adb = cli[os.environ["DB_NAME"]]
            return await coro_factory(adb)
        finally:
            cli.close()

    return asyncio.run(runner())


def _marker():
    return f"TEST_iter22_{uuid.uuid4().hex[:8]}"


# ---------------- /api/coach/effectiveness commission_summary ----------------
class TestEffectivenessCommissionSummary:
    def test_endpoint_returns_commission_summary(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/effectiveness?days=30", headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "commission_summary" in d
        cs = d["commission_summary"]
        for k in ("active_count", "capped_amount_usd", "total_credited_usd",
                  "is_capped", "plan_price_usd"):
            assert k in cs

    def test_commission_summary_reflects_seeded_data(self, admin_headers, db, cleanup_tracker):
        marker = _marker()
        new_tid = f"{marker}_referred"
        now = datetime.now(timezone.utc)
        db.commissions.insert_one({
            "commission_id": f"{marker}_c",
            "referrer_tenant_id": DEMO_TENANT,
            "referred_tenant_id": new_tid,
            "amount_per_month_usd": 5.0, "status": "active",
            "created_at": now, "activated_at": now,
            "expires_at": now + timedelta(days=300),
            "total_credited_usd": 12.0, "applied_invoices": [],
        })
        cleanup_tracker.append(("commissions", {"commission_id": f"{marker}_c"}))

        r = requests.get(f"{BASE}/api/coach/effectiveness?days=30", headers=admin_headers)
        assert r.status_code == 200
        cs = r.json()["commission_summary"]
        assert cs["active_count"] >= 1
        assert cs["total_credited_usd"] >= 12.0


# ---------------- Email triggered on new commission ----------------
class TestNewCommissionEmailTrigger:
    def test_email_called_on_first_commission(self, db, cleanup_tracker, monkeypatch):
        """Cuando create_commission_on_first_payment crea una commission ACTIVE,
        debe disparar send_new_referral_commission.
        """
        from commission_service import create_commission_on_first_payment

        marker = _marker()
        ref_tid = f"{marker}_ref"
        new_tid = f"{marker}_new"
        ref_admin_email = f"{marker.lower()}@example.com"
        db.tenants.insert_many([
            {"tenant_id": ref_tid, "name": "RefBiz",
             "business_name": "Ref Biz Co", "active": True,
             "subscription_plan": "pro",
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"tenant_id": new_tid, "name": "NewBiz",
             "business_name": "Negocio Nuevo", "active": True,
             "subscription_plan": "pro",
             "referred_by": ref_tid,
             "created_at": datetime.now(timezone.utc).isoformat()},
        ])
        db.agents.insert_one({
            "tenant_id": ref_tid, "email": ref_admin_email,
            "name": "Founder", "role": "admin", "active": True,
            "password_hash": "x",
        })
        cleanup_tracker.append(("tenants", {"tenant_id": {"$in": [ref_tid, new_tid]}}))
        cleanup_tracker.append(("agents", {"email": ref_admin_email}))
        cleanup_tracker.append(("commissions", {"referrer_tenant_id": ref_tid}))

        # Forzar SMTP "configurado" via env vars (EmailService los lee en __init__)
        monkeypatch.setenv("SMTP_USERNAME", "fake@smtp")
        monkeypatch.setenv("SMTP_PASSWORD", "fakepass")
        monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@inmobot.test")

        with patch("email_service.EmailService.send_new_referral_commission",
                   new_callable=AsyncMock, return_value=True) as mock_send:
            doc = _run_async(
                lambda adb: create_commission_on_first_payment(adb, new_tid)
            )
        assert doc is not None
        assert doc["status"] == "active"
        # El mock debe haber sido llamado con los kwargs esperados
        assert mock_send.await_count == 1
        kwargs = mock_send.await_args.kwargs
        assert kwargs["to_email"] == ref_admin_email
        assert kwargs["referrer_business_name"] == "Ref Biz Co"
        assert kwargs["referred_business_name"] == "Negocio Nuevo"
        assert kwargs["amount_per_month_usd"] == 5.0
        assert kwargs["active_count"] >= 1

    def test_email_not_called_when_smtp_not_configured(self, db, cleanup_tracker):
        from commission_service import create_commission_on_first_payment

        marker = _marker()
        ref_tid = f"{marker}_ref"
        new_tid = f"{marker}_new"
        ref_admin_email = f"{marker.lower()}_nosmtp@example.com"
        db.tenants.insert_many([
            {"tenant_id": ref_tid, "name": "R", "business_name": "R",
             "active": True, "subscription_plan": "pro",
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"tenant_id": new_tid, "name": "N", "business_name": "N",
             "active": True, "subscription_plan": "pro",
             "referred_by": ref_tid,
             "created_at": datetime.now(timezone.utc).isoformat()},
        ])
        db.agents.insert_one({
            "tenant_id": ref_tid, "email": ref_admin_email,
            "name": "Founder", "role": "admin", "active": True,
            "password_hash": "x",
        })
        cleanup_tracker.append(("tenants", {"tenant_id": {"$in": [ref_tid, new_tid]}}))
        cleanup_tracker.append(("agents", {"email": ref_admin_email}))
        cleanup_tracker.append(("commissions", {"referrer_tenant_id": ref_tid}))

        with patch("email_service.EmailService.send_new_referral_commission",
                   new_callable=AsyncMock, return_value=True) as mock_send:
            # SMTP NO configurado (defaults: None, None)
            doc = _run_async(
                lambda adb: create_commission_on_first_payment(adb, new_tid)
            )
        assert doc is not None
        # Sin SMTP, NO debe haberse llamado al método de envío
        assert mock_send.await_count == 0


# ---------------- Trial ending soon helpers ----------------
class TestTrialEndingHelpers:
    def test_trial_days_left_active_returns_none(self):
        from routers.coach import _trial_days_left
        t = {"subscription_status": "active",
             "created_at": datetime.now(timezone.utc).isoformat()}
        assert _trial_days_left(t) is None

    def test_trial_days_left_within_trial(self):
        from routers.coach import _trial_days_left, TRIAL_DURATION_DAYS
        # Tenant creado hace 12 días, sin subscription -> faltan 2 días
        created = datetime.now(timezone.utc) - timedelta(days=12)
        t = {"subscription_status": "trial", "created_at": created.isoformat()}
        left = _trial_days_left(t)
        assert left == TRIAL_DURATION_DAYS - 12

    def test_trial_days_left_expired_returns_zero(self):
        from routers.coach import _trial_days_left
        # Creado hace 30 días, sin subscription -> 0
        created = datetime.now(timezone.utc) - timedelta(days=30)
        t = {"subscription_status": None, "created_at": created.isoformat()}
        assert _trial_days_left(t) == 0


# ---------------- Trial ending soon nudge ----------------
class TestTrialEndingNudge:
    def test_nudge_created_for_tenant_in_warning_window(self, db, cleanup_tracker):
        """Crea un tenant con created_at hace 12 días, sin sub activa.
        Run coach -> debe crear nudge trial_ending_soon."""
        from routers.coach import _evaluate_tenant

        marker = _marker()
        tid = f"{marker}_trial"
        created = datetime.now(timezone.utc) - timedelta(days=12)
        # Set whatsapp tokens para evitar otros nudges high-priority
        tenant_doc = {
            "tenant_id": tid, "name": "TrialEnding",
            "business_name": "Trial Ending Co",
            "active": True, "subscription_status": "trial",
            "subscription_plan": "pro",
            "whatsapp_access_token": "fake_token",
            "whatsapp_phone_number_id": "fake_phone",
            "logo_url": "https://x.test/logo.png",
            "primary_color": "#abc123", "accent_color": "#def456",
            "created_at": created.isoformat(),
        }
        db.tenants.insert_one(tenant_doc)
        cleanup_tracker.append(("tenants", {"tenant_id": tid}))
        cleanup_tracker.append(("coach_nudges", {"tenant_id": tid}))

        created_count = _run_async(lambda adb: _evaluate_tenant(tenant_doc, adb))
        assert created_count >= 1

        nudge = db.coach_nudges.find_one(
            {"tenant_id": tid, "nudge_type": "trial_ending_soon"}
        )
        assert nudge is not None
        assert nudge["severity"] == "high"
        assert "termina" in nudge["title"].lower() or "trial" in nudge["title"].lower()
        assert nudge["dismissed_at"] is None

    def test_no_nudge_for_active_subscription(self, db, cleanup_tracker):
        from routers.coach import _evaluate_tenant

        marker = _marker()
        tid = f"{marker}_active_sub"
        created = datetime.now(timezone.utc) - timedelta(days=12)
        tenant_doc = {
            "tenant_id": tid, "name": "Active",
            "active": True, "subscription_status": "active",
            "whatsapp_access_token": "x", "whatsapp_phone_number_id": "y",
            "logo_url": "https://x.test/l.png",
            "primary_color": "#abc123", "accent_color": "#def456",
            "created_at": created.isoformat(),
        }
        db.tenants.insert_one(tenant_doc)
        cleanup_tracker.append(("tenants", {"tenant_id": tid}))
        cleanup_tracker.append(("coach_nudges", {"tenant_id": tid}))

        _run_async(lambda adb: _evaluate_tenant(tenant_doc, adb))
        nudge = db.coach_nudges.find_one(
            {"tenant_id": tid, "nudge_type": "trial_ending_soon"}
        )
        assert nudge is None


# ---------------- Email service smoke (signatures exist) ----------------
class TestEmailServiceSignatures:
    def test_email_service_has_new_methods(self):
        from email_service import EmailService
        es = EmailService(db=None)
        for method in (
            "send_new_referral_commission",
            "send_trial_ending_soon",
            "send_weekly_digest",
        ):
            assert hasattr(es, method), f"EmailService missing {method}"
            assert callable(getattr(es, method))
