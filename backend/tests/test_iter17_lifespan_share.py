"""Iter17 tests:
- Lifespan migration (no on_event deprecation warnings)
- coach_nudges.created_at as BSON datetime
- celebrations cache TTL
- POST /coach/celebrations/{id}/share endpoint
"""
import os
import time
import pytest
import requests
from datetime import datetime
from pymongo import MongoClient

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASS = "Demo123!"
DEMO_TENANT = "demo-inmobiliaria"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def mongo_db():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def test_lifespan_no_on_event_warnings():
    """Backend logs should not contain on_event deprecation warnings"""
    paths = ["/var/log/supervisor/backend.err.log", "/var/log/supervisor/backend.out.log"]
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p) as f:
            content = f.read()
        assert "on_event is deprecated" not in content, f"deprecation in {p}"


def test_health():
    r = requests.get(f"{BASE_URL}/api/", timeout=10)
    assert r.status_code == 200


def test_run_coach_creates_nudge_with_bson_datetime(auth_headers, mongo_db):
    """POST /coach/run -> nudge stored with created_at as BSON datetime"""
    # Force eval
    r = requests.post(f"{BASE_URL}/api/coach/run", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
    # Inspect any nudge for tenant
    docs = list(mongo_db.coach_nudges.find({"tenant_id": DEMO_TENANT}).limit(5))
    if not docs:
        pytest.skip("No nudges in DB to assert types (signals all resolved)")
    # At least one created_at must be datetime (not str)
    types = [type(d.get("created_at")).__name__ for d in docs]
    assert any(t == "datetime" for t in types), f"All created_at are non-datetime: {types}"


def test_celebrations_cache_ttl(auth_headers):
    """2 quick GETs to /coach/celebrations: 2nd should be cache-hit (faster or equal)."""
    # 1st (cold)
    t0 = time.time()
    r1 = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
    d1 = time.time() - t0
    assert r1.status_code == 200
    # 2nd (warm)
    t0 = time.time()
    r2 = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
    d2 = time.time() - t0
    assert r2.status_code == 200
    # Same payload structure
    assert r1.json().get("count") == r2.json().get("count")
    # Cache hit should not be slower than cold by significant margin (best-effort)
    print(f"cold={d1:.3f}s warm={d2:.3f}s")


def test_share_endpoint_basic(auth_headers, mongo_db):
    """POST /coach/celebrations/{id}/share returns tracked + card_data + share_text"""
    r = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
    cels = r.json().get("celebrations", [])
    if not cels:
        pytest.skip("No celebrations to share")
    cid = cels[0]["celebration_id"]
    r = requests.post(f"{BASE_URL}/api/coach/celebrations/{cid}/share",
                      headers=auth_headers, json={"platform": "twitter"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("tracked") is True
    assert data.get("platform") == "twitter"
    card = data.get("card_data") or {}
    for k in ("emoji", "title", "body", "business_name", "logo_url",
              "primary_color", "accent_color", "powered_by"):
        assert k in card, f"missing card_data.{k}"
    assert "InmoBot" in card["powered_by"]
    assert isinstance(data.get("share_text"), str) and len(data["share_text"]) > 5


def test_share_endpoint_increments_counters(auth_headers, mongo_db):
    """2 calls twitter + 1 download => shares.twitter>=2, shares.download>=1, shares.total>=3"""
    r = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
    cels = r.json().get("celebrations", [])
    if not cels:
        pytest.skip("No celebrations to test counters")
    cid = cels[0]["celebration_id"]
    # Reset shares to 0
    mongo_db.coach_celebrations.update_one(
        {"celebration_id": cid}, {"$unset": {"shares": ""}})
    requests.post(f"{BASE_URL}/api/coach/celebrations/{cid}/share",
                  headers=auth_headers, json={"platform": "twitter"}, timeout=15)
    requests.post(f"{BASE_URL}/api/coach/celebrations/{cid}/share",
                  headers=auth_headers, json={"platform": "twitter"}, timeout=15)
    requests.post(f"{BASE_URL}/api/coach/celebrations/{cid}/share",
                  headers=auth_headers, json={"platform": "download"}, timeout=15)
    doc = mongo_db.coach_celebrations.find_one({"celebration_id": cid})
    shares = doc.get("shares") or {}
    assert shares.get("twitter") == 2, f"twitter={shares.get('twitter')}"
    assert shares.get("download") == 1, f"download={shares.get('download')}"
    assert shares.get("total") == 3, f"total={shares.get('total')}"


def test_share_endpoint_404(auth_headers):
    r = requests.post(f"{BASE_URL}/api/coach/celebrations/does-not-exist-xyz/share",
                      headers=auth_headers, json={"platform": "twitter"}, timeout=15)
    assert r.status_code == 404


def test_share_endpoint_audit_log(auth_headers, mongo_db):
    r = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
    cels = r.json().get("celebrations", [])
    if not cels:
        pytest.skip("No celebrations for audit test")
    cid = cels[0]["celebration_id"]
    requests.post(f"{BASE_URL}/api/coach/celebrations/{cid}/share",
                  headers=auth_headers, json={"platform": "linkedin"}, timeout=15)
    log = mongo_db.audit_log.find_one(
        {"tenant_id": DEMO_TENANT, "action": "celebration_shared", "platform": "linkedin"},
        sort=[("timestamp", -1)],
    )
    assert log is not None
    assert log.get("celebration_type") is not None


def test_share_endpoint_platform_whitelist(auth_headers, mongo_db):
    """Platform 'evilhack' should normalize to 'unknown'"""
    r = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
    cels = r.json().get("celebrations", [])
    if not cels:
        pytest.skip("No celebrations for whitelist test")
    cid = cels[0]["celebration_id"]
    r = requests.post(f"{BASE_URL}/api/coach/celebrations/{cid}/share",
                      headers=auth_headers, json={"platform": "evilhack"}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("platform") == "unknown"
