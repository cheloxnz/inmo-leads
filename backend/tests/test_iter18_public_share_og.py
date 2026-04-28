"""Iter18 tests: public OG share endpoints
- GET /api/public/share/{tenant_id}/{celebration_id}.png returns PNG with ETag + Cache-Control
- ETag conditional GET -> 304
- Cache TTL (in-memory) makes 2nd call fast and same ETag
- GET /api/public/share/{tenant_id}/{celebration_id} returns HTML with OG/Twitter meta tags
- X-Forwarded-Host honored for og:image absolute URL
- 404 for missing celebration
- Tracking shares.preview_views + shares.html_views
"""
import os
import re
import time
import struct
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASS = "Demo123!"
DEMO_TENANT = "demo-inmobiliaria"

FAKE_HOST = "inmobot-preview.preview.emergentagent.com"


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


@pytest.fixture(scope="module")
def celebration_id(auth_headers):
    r = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
    cels = r.json().get("celebrations", [])
    if not cels:
        # try forcing detection
        requests.post(f"{BASE_URL}/api/coach/run", headers=auth_headers, timeout=15)
        r = requests.get(f"{BASE_URL}/api/coach/celebrations", headers=auth_headers, timeout=15)
        cels = r.json().get("celebrations", [])
    if not cels:
        pytest.skip("No celebrations available for demo tenant")
    return cels[0]["celebration_id"]


# ---------------- PNG ----------------

def test_png_returns_image_with_etag_and_cache(celebration_id):
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}.png"
    r = requests.get(url, timeout=20)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("image/png")

    # PNG magic header
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n", "Not a PNG"

    # ETag header with quotes
    etag = r.headers.get("ETag")
    assert etag and etag.startswith('"') and etag.endswith('"'), f"Bad ETag: {etag}"

    # Cache-Control: backend sets "public, max-age=3600, s-maxage=86400" but the
    # external CDN/ingress (Cloudflare) overrides it with no-store. Verify backend
    # behavior directly via internal port to avoid the CDN-layer override.
    internal_r = requests.get(
        f"http://localhost:8001/api/public/share/{DEMO_TENANT}/{celebration_id}.png",
        timeout=15,
    )
    cc = (internal_r.headers.get("Cache-Control") or "").lower()
    assert "public" in cc, f"backend Cache-Control missing 'public': {cc}"
    assert "max-age=3600" in cc, f"backend Cache-Control missing max-age=3600: {cc}"

    # Size: should be > 5KB; not strictly ~30KB but in a reasonable range
    assert len(r.content) > 5_000, f"PNG too small: {len(r.content)}"
    assert len(r.content) < 500_000, f"PNG too big: {len(r.content)}"

    # Validate PNG dimensions are 1200x630 (IHDR chunk: bytes 16-24 width/height big-endian)
    width = struct.unpack(">I", r.content[16:20])[0]
    height = struct.unpack(">I", r.content[20:24])[0]
    assert width == 1200
    assert height == 630


def test_png_no_auth_required(celebration_id):
    """Public endpoint - no Authorization header"""
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}.png"
    r = requests.get(url, timeout=15)
    assert r.status_code == 200


def test_png_etag_conditional_get_304(celebration_id):
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}.png"
    r1 = requests.get(url, timeout=15)
    etag = r1.headers["ETag"]
    r2 = requests.get(url, headers={"If-None-Match": etag}, timeout=15)
    assert r2.status_code == 304
    # 304 should have no body (content-length 0 or empty)
    assert len(r2.content) == 0


def test_png_cache_returns_same_etag(celebration_id):
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}.png"
    t0 = time.time()
    r1 = requests.get(url, timeout=15)
    d1 = time.time() - t0
    t0 = time.time()
    r2 = requests.get(url, timeout=15)
    d2 = time.time() - t0
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.headers["ETag"] == r2.headers["ETag"]
    print(f"PNG cold={d1:.3f}s warm={d2:.3f}s")


def test_png_404_for_missing_celebration():
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/does-not-exist-xyz.png"
    r = requests.get(url, timeout=10)
    assert r.status_code == 404


def test_png_increments_preview_views(celebration_id, mongo_db):
    """Each PNG GET should bump shares.preview_views"""
    # Reset
    mongo_db.coach_celebrations.update_one(
        {"celebration_id": celebration_id, "tenant_id": DEMO_TENANT},
        {"$unset": {"shares.preview_views": ""}},
    )
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}.png"
    # 304 path: cached + If-None-Match. Want to skip the conditional path so increments fire.
    # Trick: use unique query? no -- endpoint ignores. Force fresh by hitting with different etag.
    requests.get(url, headers={"If-None-Match": '"deadbeef"'}, timeout=15)
    requests.get(url, headers={"If-None-Match": '"deadbeef"'}, timeout=15)
    doc = mongo_db.coach_celebrations.find_one(
        {"celebration_id": celebration_id, "tenant_id": DEMO_TENANT})
    pv = (doc.get("shares") or {}).get("preview_views") or 0
    assert pv >= 2, f"preview_views should be >=2, got {pv}"


# ---------------- HTML / OG ----------------

def test_html_meta_tags_contain_og_and_twitter(celebration_id):
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}"
    r = requests.get(url, timeout=15)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    html = r.text

    # OG mandatory tags
    assert re.search(r'<meta\s+property="og:type"\s+content="website"\s*/?>', html)
    assert re.search(r'<meta\s+property="og:title"\s+content="[^"]+"\s*/?>', html)
    assert re.search(r'<meta\s+property="og:image"\s+content="https?://[^"]+\.png"\s*/?>', html)
    assert re.search(r'<meta\s+property="og:image:width"\s+content="1200"\s*/?>', html)
    assert re.search(r'<meta\s+property="og:image:height"\s+content="630"\s*/?>', html)

    # Twitter
    assert re.search(r'<meta\s+name="twitter:card"\s+content="summary_large_image"\s*/?>', html)
    assert re.search(r'<meta\s+name="twitter:image"\s+content="https?://[^"]+\.png"\s*/?>', html)

    # og:image and twitter:image should match
    og_img = re.search(r'property="og:image"\s+content="([^"]+)"', html).group(1)
    tw_img = re.search(r'name="twitter:image"\s+content="([^"]+)"', html).group(1)
    assert og_img == tw_img
    # And contain the expected path
    assert f"/api/public/share/{DEMO_TENANT}/{celebration_id}.png" in og_img


def test_html_uses_x_forwarded_host(celebration_id):
    """When X-Forwarded-Host is set, og:image should use that hostname, not internal."""
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}"
    headers = {"X-Forwarded-Host": FAKE_HOST, "X-Forwarded-Proto": "https"}
    r = requests.get(url, headers=headers, timeout=15)
    assert r.status_code == 200
    html = r.text
    og_img = re.search(r'property="og:image"\s+content="([^"]+)"', html).group(1)
    assert og_img.startswith(f"https://{FAKE_HOST}/"), f"og:image={og_img}"
    assert og_img.endswith(f"/api/public/share/{DEMO_TENANT}/{celebration_id}.png")
    # Internal hosts should NOT leak
    assert "emergentcf.cloud" not in og_img
    assert "localhost" not in og_img


def test_html_no_emoji_in_title(celebration_id):
    """og:title should be sin emojis (Pillow tofu fix)."""
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}"
    r = requests.get(url, timeout=15)
    title_m = re.search(r'property="og:title"\s+content="([^"]+)"', r.text)
    assert title_m
    title = title_m.group(1)
    # No surrogate-pair / emoji unicode plane > BMP
    assert not re.search(r"[\U00010000-\U0010FFFF]", title), f"Emoji leaked: {title!r}"


def test_html_404_for_missing_celebration():
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/does-not-exist-xyz"
    r = requests.get(url, timeout=10)
    assert r.status_code == 404


def test_html_increments_html_views(celebration_id, mongo_db):
    mongo_db.coach_celebrations.update_one(
        {"celebration_id": celebration_id, "tenant_id": DEMO_TENANT},
        {"$unset": {"shares.html_views": ""}},
    )
    url = f"{BASE_URL}/api/public/share/{DEMO_TENANT}/{celebration_id}"
    requests.get(url, timeout=15)
    requests.get(url, timeout=15)
    requests.get(url, timeout=15)
    doc = mongo_db.coach_celebrations.find_one(
        {"celebration_id": celebration_id, "tenant_id": DEMO_TENANT})
    hv = (doc.get("shares") or {}).get("html_views") or 0
    assert hv >= 3, f"html_views should be >=3, got {hv}"


def test_share_endpoint_returns_tenant_id_in_card_data(auth_headers, celebration_id):
    """coach.py POST /share must include tenant_id in card_data for FE to build public URL."""
    r = requests.post(
        f"{BASE_URL}/api/coach/celebrations/{celebration_id}/share",
        headers=auth_headers, json={"platform": "twitter"}, timeout=15)
    assert r.status_code == 200
    card = r.json().get("card_data") or {}
    assert card.get("tenant_id") == DEMO_TENANT, f"card_data missing tenant_id: {card}"
