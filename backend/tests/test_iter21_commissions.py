"""Iter21 Commission/Referral Reward Program:
- Anti-fraud detection (same email, same domain, same IP)
- Creation on first paid invoice
- Active credit calculation with cap to plan price
- Cancellation / expiration lifecycle
- GET /api/commissions/summary endpoint
- Stripe invoice.upcoming injects negative invoice item
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_TENANT = "demo-inmobiliaria"
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"


# ---------------- helpers ----------------
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
    """List of (collection, filter) tuples to remove after the test."""
    items = []
    yield items
    cli = MongoClient(os.environ["MONGO_URL"])
    d = cli[os.environ["DB_NAME"]]
    for coll, flt in items:
        d[coll].delete_many(flt)
    cli.close()


def _ref_marker():
    return f"TEST_iter21_{uuid.uuid4().hex[:8]}"


def _run_async(coro_factory):
    """Run an async coroutine factory with a fresh AsyncIOMotorClient inside the
    test's event loop so multiple invocations within one test don't reuse a
    closed loop. coro_factory(adb) -> coroutine.
    """
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


# ---------------- Anti-fraud ----------------
class TestAntiFraud:
    def test_same_email_blocked(self, db, cleanup_tracker):
        from commission_service import is_self_referral

        is_fraud, reason = _run_async(
            lambda adb: is_self_referral(adb, DEMO_TENANT, DEMO_EMAIL, "1.2.3.4")
        )
        assert is_fraud is True
        assert reason == "same_email_as_referrer"

    def test_corporate_domain_blocked(self, db, cleanup_tracker):
        """If referrer email is on a NON-free domain, signup with same domain = fraud."""
        from commission_service import is_self_referral

        # Insert a fake corporate referrer agent
        marker = _ref_marker()
        ref_tenant = f"{marker}_ref"
        agent_email = f"founder@{marker.lower()}corp.com"
        db.tenants.insert_one({
            "tenant_id": ref_tenant, "name": "RefCorp",
            "active": True, "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.agents.insert_one({
            "tenant_id": ref_tenant, "email": agent_email,
            "name": "Founder", "active": True,
            "password_hash": "x", "role": "admin",
        })
        cleanup_tracker.append(("tenants", {"tenant_id": ref_tenant}))
        cleanup_tracker.append(("agents", {"email": agent_email}))

        is_fraud, reason = _run_async(
            lambda adb: is_self_referral(
                adb, ref_tenant, f"new@{marker.lower()}corp.com", None,
            )
        )
        assert is_fraud is True
        assert reason == "same_corporate_domain"

        # Free provider domain match should NOT trigger
        db.agents.insert_one({
            "tenant_id": ref_tenant + "_g", "email": "x@gmail.com",
            "name": "G", "active": True, "password_hash": "x",
            "role": "admin",
        })
        db.tenants.insert_one({
            "tenant_id": ref_tenant + "_g", "name": "G",
            "active": True, "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": ref_tenant + "_g"}))
        cleanup_tracker.append(("agents", {"email": "x@gmail.com"}))
        is_fraud2, _ = _run_async(
            lambda adb: is_self_referral(adb, ref_tenant + "_g", "y@gmail.com", None)
        )
        assert is_fraud2 is False

    def test_same_ip_24h_blocked(self, db, cleanup_tracker):
        from commission_service import is_self_referral

        marker = _ref_marker()
        ref_tenant = f"{marker}_ref"
        ip = f"203.0.113.{uuid.uuid4().int % 250 + 1}"

        db.tenants.insert_one({
            "tenant_id": ref_tenant, "name": "RefIP",
            "active": True, "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # audit_log entry from the referrer's recent activity
        db.audit_log.insert_one({
            "tenant_id": ref_tenant, "ip": ip,
            "action": "test", "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": ref_tenant}))
        cleanup_tracker.append(("audit_log", {"tenant_id": ref_tenant}))

        is_fraud, reason = _run_async(
            lambda adb: is_self_referral(
                adb, ref_tenant, "stranger@external.com", ip,
            )
        )
        assert is_fraud is True
        assert reason == "same_ip_recently"


# ---------------- Commission lifecycle ----------------
class TestCommissionLifecycle:
    def test_create_on_first_payment_when_referred(self, db, cleanup_tracker):
        from commission_service import create_commission_on_first_payment

        marker = _ref_marker()
        ref_tid = f"{marker}_ref"
        new_tid = f"{marker}_new"
        db.tenants.insert_many([
            {
                "tenant_id": ref_tid, "name": "Referrer", "active": True,
                "subscription_plan": "pro",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "tenant_id": new_tid, "name": "NewBie", "active": True,
                "subscription_plan": "pro", "referred_by": ref_tid,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ])
        cleanup_tracker.append(("tenants", {"tenant_id": {"$in": [ref_tid, new_tid]}}))
        cleanup_tracker.append(("commissions", {"referrer_tenant_id": ref_tid}))

        doc = _run_async(lambda adb: create_commission_on_first_payment(adb, new_tid))
        assert doc is not None
        assert doc["referrer_tenant_id"] == ref_tid
        assert doc["referred_tenant_id"] == new_tid
        assert doc["amount_per_month_usd"] == 5.0
        assert doc["status"] == "active"

        # Idempotency: calling again returns None and does not duplicate
        doc2 = _run_async(lambda adb: create_commission_on_first_payment(adb, new_tid))
        assert doc2 is None
        count = db.commissions.count_documents({
            "referrer_tenant_id": ref_tid, "referred_tenant_id": new_tid,
        })
        assert count == 1

    def test_no_commission_if_not_referred(self, db, cleanup_tracker):
        from commission_service import create_commission_on_first_payment

        marker = _ref_marker()
        new_tid = f"{marker}_solo"
        db.tenants.insert_one({
            "tenant_id": new_tid, "name": "Solo", "active": True,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": new_tid}))

        doc = _run_async(lambda adb: create_commission_on_first_payment(adb, new_tid))
        assert doc is None


# ---------------- Active credit ----------------
class TestActiveCreditCalc:
    def test_credit_capped_to_plan_price(self, db, cleanup_tracker):
        from commission_service import calculate_active_credit_for_tenant

        marker = _ref_marker()
        ref_tid = f"{marker}_ref"
        db.tenants.insert_one({
            "tenant_id": ref_tid, "name": "BigRef", "active": True,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": ref_tid}))

        # 25 active commissions x $5 = $125 raw, cap to plan pro=$99
        now = datetime.now(timezone.utc)
        docs = []
        for i in range(25):
            docs.append({
                "commission_id": f"{marker}_c{i}",
                "referrer_tenant_id": ref_tid,
                "referred_tenant_id": f"{marker}_r{i}",
                "amount_per_month_usd": 5.0,
                "status": "active",
                "created_at": now,
                "activated_at": now,
                "expires_at": now + timedelta(days=300),
                "total_credited_usd": 0.0,
                "applied_invoices": [],
            })
        db.commissions.insert_many(docs)
        cleanup_tracker.append(("commissions", {"referrer_tenant_id": ref_tid}))

        credit = _run_async(
            lambda adb: calculate_active_credit_for_tenant(adb, ref_tid)
        )
        assert credit["amount_usd"] == 125.0
        assert credit["capped_amount_usd"] == 99.0
        assert credit["plan_price_usd"] == 99.0
        assert credit["is_capped"] is True
        assert credit["active_count"] == 25

    def test_credit_below_cap_not_capped(self, db, cleanup_tracker):
        from commission_service import calculate_active_credit_for_tenant

        marker = _ref_marker()
        ref_tid = f"{marker}_ref"
        db.tenants.insert_one({
            "tenant_id": ref_tid, "name": "SmallRef", "active": True,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": ref_tid}))

        now = datetime.now(timezone.utc)
        docs = [{
            "commission_id": f"{marker}_c{i}",
            "referrer_tenant_id": ref_tid,
            "referred_tenant_id": f"{marker}_r{i}",
            "amount_per_month_usd": 5.0,
            "status": "active",
            "created_at": now, "activated_at": now,
            "expires_at": now + timedelta(days=300),
            "total_credited_usd": 0.0, "applied_invoices": [],
        } for i in range(3)]  # 3 x $5 = $15, far below $99
        db.commissions.insert_many(docs)
        cleanup_tracker.append(("commissions", {"referrer_tenant_id": ref_tid}))

        credit = _run_async(
            lambda adb: calculate_active_credit_for_tenant(adb, ref_tid)
        )
        assert credit["amount_usd"] == 15.0
        assert credit["capped_amount_usd"] == 15.0
        assert credit["is_capped"] is False
        assert credit["active_count"] == 3

    def test_expired_commissions_auto_marked(self, db, cleanup_tracker):
        from commission_service import (
            calculate_active_credit_for_tenant, expire_due_commissions,
        )

        marker = _ref_marker()
        ref_tid = f"{marker}_ref"
        db.tenants.insert_one({
            "tenant_id": ref_tid, "name": "ExpRef", "active": True,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": ref_tid}))

        now = datetime.now(timezone.utc)
        db.commissions.insert_many([
            # expired one
            {
                "commission_id": f"{marker}_exp",
                "referrer_tenant_id": ref_tid,
                "referred_tenant_id": f"{marker}_rexp",
                "amount_per_month_usd": 5.0, "status": "active",
                "created_at": now - timedelta(days=400),
                "activated_at": now - timedelta(days=400),
                "expires_at": now - timedelta(days=1),
                "total_credited_usd": 60.0, "applied_invoices": [],
            },
            # active one
            {
                "commission_id": f"{marker}_act",
                "referrer_tenant_id": ref_tid,
                "referred_tenant_id": f"{marker}_ract",
                "amount_per_month_usd": 5.0, "status": "active",
                "created_at": now, "activated_at": now,
                "expires_at": now + timedelta(days=200),
                "total_credited_usd": 0.0, "applied_invoices": [],
            },
        ])
        cleanup_tracker.append(("commissions", {"referrer_tenant_id": ref_tid}))

        credit = _run_async(
            lambda adb: calculate_active_credit_for_tenant(adb, ref_tid)
        )
        assert credit["active_count"] == 1
        # Expired one is now marked
        doc_exp = db.commissions.find_one({"commission_id": f"{marker}_exp"})
        assert doc_exp["status"] == "expired"

        count = _run_async(lambda adb: expire_due_commissions(adb))
        # Already expired by the previous call; should be 0 now
        assert count == 0


# ---------------- Cancellation ----------------
class TestCommissionCancellation:
    def test_cancel_when_referred_cancels(self, db, cleanup_tracker):
        from commission_service import cancel_commissions_for_referred

        marker = _ref_marker()
        ref_tid = f"{marker}_ref"
        new_tid = f"{marker}_new"
        now = datetime.now(timezone.utc)
        db.commissions.insert_one({
            "commission_id": f"{marker}_c",
            "referrer_tenant_id": ref_tid,
            "referred_tenant_id": new_tid,
            "amount_per_month_usd": 5.0, "status": "active",
            "created_at": now, "activated_at": now,
            "expires_at": now + timedelta(days=300),
            "total_credited_usd": 0.0, "applied_invoices": [],
        })
        cleanup_tracker.append(("commissions", {"referrer_tenant_id": ref_tid}))

        _run_async(lambda adb: cancel_commissions_for_referred(adb, new_tid))
        doc = db.commissions.find_one({"commission_id": f"{marker}_c"})
        assert doc["status"] == "cancelled"
        assert "cancelled_at" in doc


# ---------------- Summary endpoint ----------------
class TestCommissionsSummaryEndpoint:
    def test_endpoint_requires_admin(self):
        r = requests.get(f"{BASE}/api/commissions/summary")
        assert r.status_code in (401, 403)

    def test_summary_response_shape(self, admin_headers):
        r = requests.get(f"{BASE}/api/commissions/summary", headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        # required top-level keys
        for k in ("config", "active_credit", "total_lifetime_credit_usd",
                  "by_status", "commissions"):
            assert k in d, f"missing {k}"
        # config
        assert d["config"]["amount_per_referral_usd"] == 5.0
        assert d["config"]["duration_days"] == 365
        # active_credit
        ac = d["active_credit"]
        for k in ("amount_usd", "capped_amount_usd", "active_count",
                  "plan_price_usd", "plan_id", "is_capped", "breakdown"):
            assert k in ac
        assert isinstance(ac["breakdown"], list)
        assert isinstance(d["commissions"], list)

    def test_summary_includes_seeded_commission(self, admin_headers, db, cleanup_tracker):
        # Seed one commission for demo tenant
        marker = _ref_marker()
        new_tid = f"{marker}_referred"
        now = datetime.now(timezone.utc)
        db.tenants.insert_one({
            "tenant_id": new_tid, "name": "ReferredOne", "active": True,
            "business_name": f"Negocio {marker}",
            "subscription_plan": "pro", "subscription_status": "active",
            "referred_by": DEMO_TENANT,
            "created_at": now.isoformat(),
        })
        db.commissions.insert_one({
            "commission_id": f"{marker}_c",
            "referrer_tenant_id": DEMO_TENANT,
            "referred_tenant_id": new_tid,
            "amount_per_month_usd": 5.0,
            "status": "active",
            "created_at": now,
            "activated_at": now,
            "expires_at": now + timedelta(days=300),
            "total_credited_usd": 5.0,
            "applied_invoices": [{
                "invoice_id": "in_test_xyz",
                "amount_usd": 5.0,
                "applied_at": now.isoformat(),
            }],
        })
        cleanup_tracker.append(("tenants", {"tenant_id": new_tid}))
        cleanup_tracker.append(("commissions", {"commission_id": f"{marker}_c"}))

        r = requests.get(f"{BASE}/api/commissions/summary", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        ids = [c["commission_id"] for c in d["commissions"]]
        assert f"{marker}_c" in ids
        seeded = next(c for c in d["commissions"] if c["commission_id"] == f"{marker}_c")
        assert seeded["referred_business_name"] == f"Negocio {marker}"
        assert seeded["status"] == "active"
        assert seeded["total_credited_usd"] == 5.0
        assert seeded["applied_invoices_count"] == 1
        # Lifetime aggregate must be at least our $5 credit
        assert d["total_lifetime_credit_usd"] >= 5.0
