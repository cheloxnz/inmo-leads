"""Iter23 - Stripe Coupon Codes para attribution.
- Generación de referral_code único por tenant
- Endpoint GET /api/commissions/promo-code
- Endpoint POST /api/commissions/resolve-promo (público)
- Inclusión en /api/commissions/summary
- Attribution via promo code en webhook Stripe (mockeado)
"""
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

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
    return f"TEST_iter23_{uuid.uuid4().hex[:8]}"


# ---------------- Code generator ----------------
class TestCodeGenerator:
    def test_format_correct(self):
        from commission_service import _generate_referral_code
        code = _generate_referral_code("demo-inmobiliaria")
        assert re.match(r"^[A-Z0-9]+-[A-Z0-9]{6}$", code), code
        assert code.startswith("DEMOIN")

    def test_no_confusing_chars(self):
        from commission_service import _generate_referral_code
        # Chequear varias generaciones — el sufijo nunca debe tener 0/O/1/I (chars confusos)
        for _ in range(50):
            code = _generate_referral_code("acme")
            suffix = code.split("-", 1)[1]
            for ch in suffix:
                assert ch not in "01OI", f"char prohibido en {code}"

    def test_short_tenant_id(self):
        from commission_service import _generate_referral_code
        code = _generate_referral_code("ab")
        assert code.startswith("AB-")

    def test_empty_tenant_id_fallback(self):
        from commission_service import _generate_referral_code
        code = _generate_referral_code("")
        assert code.startswith("REF-")


# ---------------- get_or_create_referral_code ----------------
class TestGetOrCreateCode:
    def test_creates_new_code(self, db, cleanup_tracker):
        from commission_service import get_or_create_referral_code
        marker = _marker()
        tid = f"{marker}_solo"
        db.tenants.insert_one({
            "tenant_id": tid, "name": "Solo", "active": True,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": tid}))

        res = _run_async(
            lambda adb: get_or_create_referral_code(adb, tid, create_in_stripe=False)
        )
        assert res["code"]
        assert res["stripe_enabled"] is False
        # Persistido en mongo
        t = db.tenants.find_one({"tenant_id": tid})
        assert t["referral_code"] == res["code"]

    def test_idempotent(self, db, cleanup_tracker):
        from commission_service import get_or_create_referral_code
        marker = _marker()
        tid = f"{marker}_idem"
        db.tenants.insert_one({
            "tenant_id": tid, "name": "Idem", "active": True,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": tid}))

        res1 = _run_async(
            lambda adb: get_or_create_referral_code(adb, tid, create_in_stripe=False)
        )
        res2 = _run_async(
            lambda adb: get_or_create_referral_code(adb, tid, create_in_stripe=False)
        )
        assert res1["code"] == res2["code"]

    def test_tenant_not_found(self):
        from commission_service import get_or_create_referral_code
        res = _run_async(
            lambda adb: get_or_create_referral_code(adb, "nope_tid_xyz", create_in_stripe=False)
        )
        assert res["code"] is None
        assert res.get("error") == "tenant_not_found"

    def test_stripe_creation_skipped_without_key(self, db, cleanup_tracker, monkeypatch):
        """Sin STRIPE_API_KEY, stripe_enabled=False y no se llama stripe.PromotionCode.create."""
        from commission_service import get_or_create_referral_code
        marker = _marker()
        tid = f"{marker}_nostripe"
        db.tenants.insert_one({
            "tenant_id": tid, "name": "NoStripe", "active": True,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": tid}))

        monkeypatch.delenv("STRIPE_API_KEY", raising=False)
        with patch("stripe.PromotionCode.create") as mock_create:
            res = _run_async(
                lambda adb: get_or_create_referral_code(adb, tid, create_in_stripe=True)
            )
        assert res["code"]
        assert res["stripe_enabled"] is False
        mock_create.assert_not_called()


# ---------------- find_referrer_by_promo_code ----------------
class TestFindReferrerByPromoCode:
    def test_resolves_active_tenant(self, db, cleanup_tracker):
        from commission_service import find_referrer_by_promo_code
        marker = _marker()
        tid = f"{marker}_active"
        code = f"FOOTEST-{marker[-6:].upper()}"
        db.tenants.insert_one({
            "tenant_id": tid, "name": "Active", "active": True,
            "referral_code": code,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": tid}))

        result = _run_async(lambda adb: find_referrer_by_promo_code(adb, code))
        assert result == tid

    def test_inactive_tenant_returns_none(self, db, cleanup_tracker):
        from commission_service import find_referrer_by_promo_code
        marker = _marker()
        tid = f"{marker}_inactive"
        code = f"INACT-{marker[-6:].upper()}"
        db.tenants.insert_one({
            "tenant_id": tid, "name": "Inactive", "active": False,
            "referral_code": code,
            "subscription_plan": "pro",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        cleanup_tracker.append(("tenants", {"tenant_id": tid}))

        result = _run_async(lambda adb: find_referrer_by_promo_code(adb, code))
        assert result is None

    def test_unknown_code(self):
        from commission_service import find_referrer_by_promo_code
        result = _run_async(
            lambda adb: find_referrer_by_promo_code(adb, "UNKNOWN-XYZ123")
        )
        assert result is None

    def test_empty_code(self):
        from commission_service import find_referrer_by_promo_code
        result = _run_async(lambda adb: find_referrer_by_promo_code(adb, ""))
        assert result is None


# ---------------- Endpoint /api/commissions/promo-code ----------------
class TestPromoCodeEndpoint:
    def test_requires_admin(self):
        r = requests.get(f"{BASE}/api/commissions/promo-code")
        assert r.status_code in (401, 403)

    def test_returns_code_for_admin(self, admin_headers):
        r = requests.get(f"{BASE}/api/commissions/promo-code", headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["code"]
        assert "stripe_enabled" in d

    def test_idempotent_endpoint(self, admin_headers):
        r1 = requests.get(f"{BASE}/api/commissions/promo-code", headers=admin_headers)
        r2 = requests.get(f"{BASE}/api/commissions/promo-code", headers=admin_headers)
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["code"] == r2.json()["code"]

    def test_summary_includes_promo_code(self, admin_headers):
        r = requests.get(f"{BASE}/api/commissions/summary", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        assert "promo_code" in d
        assert d["promo_code"]["code"]


# ---------------- Endpoint público /api/commissions/resolve-promo ----------------
class TestResolvePromoPublic:
    def test_resolve_valid_code(self, admin_headers):
        # Primero obtener el código del demo
        r0 = requests.get(f"{BASE}/api/commissions/promo-code", headers=admin_headers)
        code = r0.json()["code"]

        r = requests.post(
            f"{BASE}/api/commissions/resolve-promo",
            json={"code": code},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["valid"] is True
        assert d["ref_tenant_id"] == DEMO_TENANT

    def test_resolve_invalid_code(self):
        r = requests.post(
            f"{BASE}/api/commissions/resolve-promo",
            json={"code": "TOTALLY-INVALID-CODE-NOT-EXIST"},
        )
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_resolve_empty_code_400(self):
        r = requests.post(
            f"{BASE}/api/commissions/resolve-promo",
            json={"code": ""},
        )
        assert r.status_code == 400

    def test_resolve_too_long_code_400(self):
        r = requests.post(
            f"{BASE}/api/commissions/resolve-promo",
            json={"code": "X" * 50},
        )
        assert r.status_code == 400

    def test_resolve_lowercase_normalized(self, admin_headers):
        r0 = requests.get(f"{BASE}/api/commissions/promo-code", headers=admin_headers)
        code = r0.json()["code"]
        # lowercase también debe resolverse
        r = requests.post(
            f"{BASE}/api/commissions/resolve-promo",
            json={"code": code.lower()},
        )
        assert r.status_code == 200
        assert r.json()["valid"] is True


# ---------------- Webhook attribution via promo code ----------------
class TestWebhookPromoAttribution:
    def test_attribute_via_promo_metadata(self, db, cleanup_tracker):
        """_attribute_via_promo_code debe leer session.total_details.breakdown.discounts
        y setear referred_by si encuentra metadata.referrer_tenant_id en el promo code."""
        from payment_service import PaymentService
        from motor.motor_asyncio import AsyncIOMotorClient

        marker = _marker()
        ref_tid = f"{marker}_ref"
        new_tid = f"{marker}_new"
        db.tenants.insert_many([
            {"tenant_id": ref_tid, "name": "Referrer", "active": True,
             "subscription_plan": "pro",
             "referral_code": f"REFTEST-{marker[-6:].upper()}",
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"tenant_id": new_tid, "name": "Referido", "active": True,
             "subscription_plan": "pro",
             "created_at": datetime.now(timezone.utc).isoformat()},
        ])
        cleanup_tracker.append(("tenants", {"tenant_id": {"$in": [ref_tid, new_tid]}}))

        # Mock session: simula breakdown.discounts con un promo_id
        promo_id = "promo_test_123"
        discount = MagicMock()
        discount.discount.promotion_code = promo_id
        breakdown = MagicMock()
        breakdown.discounts = [discount]
        total_details = MagicMock()
        total_details.breakdown = breakdown
        session = MagicMock()
        session.total_details = total_details
        session.metadata = {"tenant_id": new_tid}

        # Mock stripe.PromotionCode.retrieve para devolver metadata.referrer_tenant_id=ref_tid
        promo_obj = MagicMock()
        promo_obj.code = f"REFTEST-{marker[-6:].upper()}"
        promo_obj.metadata = {"referrer_tenant_id": ref_tid}

        async def runner():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            try:
                adb = cli[os.environ["DB_NAME"]]
                ps = PaymentService(adb)
                with patch("stripe.PromotionCode.retrieve", return_value=promo_obj):
                    await ps._attribute_via_promo_code(session, new_tid)
            finally:
                cli.close()

        import asyncio
        asyncio.run(runner())

        # Tenant nuevo debe tener referred_by
        t = db.tenants.find_one({"tenant_id": new_tid})
        assert t.get("referred_by") == ref_tid
        assert t.get("referred_via_promo_code") == f"REFTEST-{marker[-6:].upper()}"

    def test_attribute_skipped_if_already_referred(self, db, cleanup_tracker):
        """Si el tenant ya tiene referred_by, NO debe sobreescribir."""
        from payment_service import PaymentService
        from motor.motor_asyncio import AsyncIOMotorClient

        marker = _marker()
        original_ref = f"{marker}_origref"
        new_promo_ref = f"{marker}_promoref"
        new_tid = f"{marker}_new"
        db.tenants.insert_many([
            {"tenant_id": original_ref, "name": "Original Ref", "active": True,
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"tenant_id": new_promo_ref, "name": "Promo Ref", "active": True,
             "referral_code": f"PROMO-{marker[-6:].upper()}",
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"tenant_id": new_tid, "name": "Already", "active": True,
             "referred_by": original_ref,  # ya atribuido
             "created_at": datetime.now(timezone.utc).isoformat()},
        ])
        cleanup_tracker.append(("tenants", {"tenant_id": {"$in": [original_ref, new_promo_ref, new_tid]}}))

        session = MagicMock()
        session.metadata = {"tenant_id": new_tid}

        async def runner():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            try:
                adb = cli[os.environ["DB_NAME"]]
                ps = PaymentService(adb)
                await ps._attribute_via_promo_code(session, new_tid)
            finally:
                cli.close()

        import asyncio
        asyncio.run(runner())

        t = db.tenants.find_one({"tenant_id": new_tid})
        # Atribución original SE MANTIENE
        assert t.get("referred_by") == original_ref
