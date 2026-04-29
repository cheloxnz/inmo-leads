"""Iter19 Referral acquisition loop:
- POST /api/public/share/{tid}/{cid}/lead (capture form)
- Onboarding wizard accepts ?ref + ?ref_celebration_id with attribution persist
- GET /api/coach/referral-stats funnel
"""
import os
import re
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_TENANT = "demo-inmobiliaria"
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def celebration_id(admin_headers):
    """Pick first celebration of demo tenant. If none, skip."""
    r = requests.get(f"{BASE}/api/coach/celebrations", headers=admin_headers)
    assert r.status_code == 200
    cels = r.json().get("celebrations", [])
    if not cels:
        # fallback: known existing one
        return "723fbfc6-187e-4dcd-a7bf-4eb3291d516c"
    return cels[0]["celebration_id"]


@pytest.fixture(scope="module")
def created_tenants():
    items = []
    yield items
    # cleanup at end of module
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if mongo_url and db_name:
            cli = MongoClient(mongo_url)
            db = cli[db_name]
            for tid, email in items:
                db.tenants.delete_one({"tenant_id": tid})
                db.agents.delete_one({"email": email})
                db.products.delete_many({"tenant_id": tid})
            db.referral_leads.delete_many({"email": {"$regex": "^TEST_iter19_"}})
            cli.close()
    except Exception as e:
        print(f"cleanup failed: {e}")


# ---------------- HTML page contains lead form ----------------
class TestHtmlLeadForm:
    def test_html_contains_lead_form_elements(self, celebration_id):
        r = requests.get(f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}")
        assert r.status_code == 200
        html = r.text
        assert 'id="lf"' in html
        assert 'id="email"' in html
        assert 'id="btn"' in html
        assert 'id="ok"' in html
        assert 'id="err"' in html
        assert 'ref-badge' in html
        assert 'Te trajo' in html
        assert 'submitLead' in html
        # capture URL is correct
        assert f"/api/public/share/{DEMO_TENANT}/{celebration_id}/lead" in html
        # signup secondary link
        assert f"/signup?ref={DEMO_TENANT}&ref_celebration_id={celebration_id}" in html


# ---------------- Lead capture endpoint ----------------
class TestLeadCapture:
    def test_capture_invalid_email_no_at(self, celebration_id):
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead",
            json={"email": "notanemail"},
        )
        assert r.status_code == 400
        assert "invalido" in r.json()["detail"].lower() or "inválido" in r.json()["detail"].lower()

    def test_capture_email_too_long(self, celebration_id):
        long_email = "a" * 195 + "@bc.co"  # 201 chars (valid format, >200)
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead",
            json={"email": long_email},
        )
        assert r.status_code == 400

    def test_capture_celebration_not_found(self):
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/nonexistent-cel-id/lead",
            json={"email": "TEST_iter19_x@example.com"},
        )
        assert r.status_code == 404

    def test_capture_valid_email_new(self, celebration_id):
        email = f"TEST_iter19_lead_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead",
            json={"email": email},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["captured"] is True
        assert d["is_new"] is True
        assert "listo" in d["message"].lower() or "Listo" in d["message"]

    def test_capture_idempotent_same_email(self, celebration_id):
        email = f"TEST_iter19_idem_{uuid.uuid4().hex[:8]}@example.com"
        url = f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead"
        r1 = requests.post(url, json={"email": email})
        assert r1.status_code == 200
        assert r1.json()["is_new"] is True
        r2 = requests.post(url, json={"email": email})
        assert r2.status_code == 200
        assert r2.json()["captured"] is True
        assert r2.json()["is_new"] is False

    def test_capture_already_registered_agent(self, celebration_id):
        # demo@inmobot.com is an existing agent
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead",
            json={"email": DEMO_EMAIL},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["captured"] is False
        assert d["reason"] == "already_registered"

    def test_lead_doc_persisted_correctly(self, celebration_id):
        from pymongo import MongoClient
        email = f"test_iter19_persist_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead",
            json={"email": email},
        )
        assert r.status_code == 200
        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        doc = db.referral_leads.find_one({"email": email.lower()})
        assert doc is not None
        assert doc["ref_tenant_id"] == DEMO_TENANT
        assert doc["ref_celebration_id"] == celebration_id
        assert "lead_id" in doc and len(doc["lead_id"]) > 0
        assert doc.get("converted_tenant_id") is None
        assert "created_at" in doc
        assert "user_agent" in doc
        cli.close()


# ---------------- Referral stats counter ----------------
class TestReferralStatsCounter:
    def test_stats_leads_increments(self, celebration_id, admin_headers):
        from pymongo import MongoClient
        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        before = db.tenants.find_one({"tenant_id": DEMO_TENANT}, {"referral_stats": 1}) or {}
        leads_before = (before.get("referral_stats") or {}).get("leads", 0)

        email = f"TEST_iter19_count_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead",
            json={"email": email},
        )
        assert r.status_code == 200
        # background task -> wait briefly
        time.sleep(1.5)

        after = db.tenants.find_one({"tenant_id": DEMO_TENANT}, {"referral_stats": 1}) or {}
        leads_after = (after.get("referral_stats") or {}).get("leads", 0)
        assert leads_after == leads_before + 1
        cli.close()


# ---------------- Onboarding ref attribution ----------------
class TestOnboardingRefAttribution:
    def test_ref_valid_persists_and_converts_lead(self, celebration_id, created_tenants):
        from pymongo import MongoClient
        # 1. Capture a lead first
        email = f"test_iter19_conv_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(
            f"{BASE}/api/public/share/{DEMO_TENANT}/{celebration_id}/lead",
            json={"email": email},
        )
        assert r.status_code == 200

        # 2. Sign up with same email and ref
        body = {
            "business_name": f"TestCo {uuid.uuid4().hex[:6]}",
            "description": "Negocio de prueba para iter19 referral attribution test",
            "email": email,
            "password": "Test1234!",
            "ref": DEMO_TENANT,
            "ref_celebration_id": celebration_id,
        }
        r2 = requests.post(f"{BASE}/api/onboarding/auto-setup", json=body)
        assert r2.status_code == 200, r2.text
        tid = r2.json()["tenant_id"]
        created_tenants.append((tid, email))

        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        # Tenant has referred_by
        tdoc = db.tenants.find_one({"tenant_id": tid})
        assert tdoc.get("referred_by") == DEMO_TENANT
        assert tdoc.get("referred_via_celebration") == celebration_id
        # Lead converted
        lead = db.referral_leads.find_one({"email": email, "ref_tenant_id": DEMO_TENANT})
        assert lead is not None
        assert lead.get("converted_tenant_id") == tid
        assert lead.get("converted_at") is not None
        cli.close()

    def test_ref_invalid_silently_ignored(self, created_tenants):
        from pymongo import MongoClient
        email = f"TEST_iter19_bad_{uuid.uuid4().hex[:8]}@example.com"
        body = {
            "business_name": f"NoRefCo {uuid.uuid4().hex[:6]}",
            "description": "Este negocio prueba ref invalido para attribution silencioso",
            "email": email,
            "password": "Test1234!",
            "ref": "tenant-que-no-existe-xyz",
        }
        r = requests.post(f"{BASE}/api/onboarding/auto-setup", json=body)
        assert r.status_code == 200
        tid = r.json()["tenant_id"]
        created_tenants.append((tid, email))

        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        tdoc = db.tenants.find_one({"tenant_id": tid})
        assert "referred_by" not in tdoc
        cli.close()

    def test_ref_inactive_not_persisted(self, created_tenants):
        from pymongo import MongoClient
        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        # create an inactive tenant
        inactive_tid = f"TEST_iter19_inactive_{uuid.uuid4().hex[:6]}"
        db.tenants.insert_one({
            "tenant_id": inactive_tid,
            "name": "Inactive",
            "active": False,
            "created_at": "2025-01-01T00:00:00+00:00",
        })
        try:
            email = f"TEST_iter19_inact_{uuid.uuid4().hex[:8]}@example.com"
            body = {
                "business_name": f"InactCo {uuid.uuid4().hex[:6]}",
                "description": "Negocio que tiene ref hacia tenant inactivo silenciosamente",
                "email": email,
                "password": "Test1234!",
                "ref": inactive_tid,
            }
            r = requests.post(f"{BASE}/api/onboarding/auto-setup", json=body)
            assert r.status_code == 200
            tid = r.json()["tenant_id"]
            created_tenants.append((tid, email))
            tdoc = db.tenants.find_one({"tenant_id": tid})
            assert "referred_by" not in tdoc
        finally:
            db.tenants.delete_one({"tenant_id": inactive_tid})
            cli.close()


# ---------------- Coach referral-stats endpoint ----------------
class TestReferralStatsEndpoint:
    def test_referral_stats_structure(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/referral-stats", headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("shares_explicit", "preview_views", "html_views",
                  "leads_captured", "signups_converted",
                  "tenant_signups_via_ref", "conversion_rate"):
            assert k in d, f"missing {k}"
        assert isinstance(d["leads_captured"], int)
        assert isinstance(d["signups_converted"], int)
        assert isinstance(d["conversion_rate"], (int, float))

    def test_conversion_rate_math(self, admin_headers):
        r = requests.get(f"{BASE}/api/coach/referral-stats", headers=admin_headers)
        d = r.json()
        leads = d["leads_captured"]
        conv = d["signups_converted"]
        if leads == 0:
            assert d["conversion_rate"] == 0
        else:
            expected = round((conv / leads) * 100, 1)
            assert d["conversion_rate"] == expected

    def test_referral_stats_requires_admin(self):
        r = requests.get(f"{BASE}/api/coach/referral-stats")
        assert r.status_code in (401, 403)
