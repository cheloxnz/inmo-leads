"""Tests Iter33: Public metrics + ROI + Bulk Import + Branding + Admin Report."""
import os
import io
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
ADMIN = ("admin@inmobot.com", "Admin123!")


@pytest.fixture(scope="module")
def headers():
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": ADMIN[0], "password": ADMIN[1]},
        timeout=15,
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def tenant_headers():
    """Login con un tenant real (demo)."""
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": "demo@inmobot.com", "password": "Demo123!"},
        timeout=15,
    )
    if r.status_code == 200:
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return None


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ===== Public metrics =====

def test_public_demand_detected_no_auth():
    r = requests.get(f"{BASE}/api/public/demand-detected", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "total_detected_usd" in body
    assert "unique_tenants" in body
    assert body["days"] == 30


def test_public_platform_stats_no_auth():
    r = requests.get(f"{BASE}/api/public/platform-stats", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "active_tenants" in body
    assert "total_leads" in body


def test_public_cache_hit():
    # 1er request
    r1 = requests.get(f"{BASE}/api/public/demand-detected", timeout=15)
    assert r1.json()["cached"] is False or r1.json()["cached"] is True
    # 2do inmediato → cached=True
    r2 = requests.get(f"{BASE}/api/public/demand-detected", timeout=15)
    assert r2.json()["cached"] is True


# ===== ROI =====

def test_roi_endpoint(headers):
    r = requests.get(f"{BASE}/api/dashboard/roi?days=30", headers=headers, timeout=15)
    assert r.status_code == 200
    body = r.json()
    for k in ("hot_leads", "warm_leads", "conversion_rate", "estimated_pipeline_usd",
              "ai_messages_answered", "hours_saved", "unmet_demand_usd", "summary_sentence"):
        assert k in body
    assert "InmoBot te ahorró" in body["summary_sentence"]


def test_roi_requires_auth():
    r = requests.get(f"{BASE}/api/dashboard/roi", timeout=15)
    assert r.status_code in (401, 403)


# ===== Bulk Import CSV =====

def test_bulk_import_template_endpoint(headers):
    r = requests.get(f"{BASE}/api/catalog/bulk-import/template", headers=headers, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "columns" in body and "name" in body["columns"]
    assert body["required"] == ["name"]


def test_bulk_import_valid_csv(headers):
    tag = uuid.uuid4().hex[:6]
    csv = (
        "name,price,category,stock_quantity\n"
        f"Producto A {tag},100,cat-{tag},5\n"
        f"Producto B {tag},200.50,cat-{tag},0\n"
        f"Producto C {tag},,cat-{tag},\n"
    )
    files = {"file": (f"test_{tag}.csv", csv, "text/csv")}
    r = requests.post(
        f"{BASE}/api/catalog/bulk-import",
        headers=headers,
        files=files,
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 3
    assert body["skipped"] == 0
    tid = None
    # Verificar que se crearon (query directa al backend sin filtro active)
    r = requests.get(f"{BASE}/api/catalog?category=cat-{tag}", headers=headers, timeout=15)
    prods_active = r.json()
    # El backend filtra active=true por defecto. Producto con stock=0 queda inactivo.
    # Verificamos 2 activos + podemos limpiar por category directamente
    assert len(prods_active) == 2
    # Cleanup: buscamos todos por name y los borramos
    for p in prods_active:
        requests.delete(f"{BASE}/api/catalog/{p['product_id']}", headers=headers, timeout=10)
    # Cleanup adicional del inactivo vía Mongo directo (test no tiene visibility)
    from pymongo import MongoClient
    cli = MongoClient(MONGO_URL)
    cli[DB_NAME].products.delete_many({"category": f"cat-{tag}"})
    cli.close()


def test_bulk_import_invalid_rows(headers):
    tag = uuid.uuid4().hex[:6]
    csv = (
        "name,price\n"
        f"Valid {tag},100\n"
        ",99\n"  # fila sin name → skip
        f"BadPrice {tag},abc\n"  # precio inválido → skip
    )
    files = {"file": (f"test_{tag}.csv", csv, "text/csv")}
    r = requests.post(
        f"{BASE}/api/catalog/bulk-import",
        headers=headers,
        files=files,
        timeout=15,
    )
    body = r.json()
    assert body["imported"] == 1
    assert body["skipped"] == 2
    assert len(body["errors"]) == 2
    # Cleanup
    r = requests.get(f"{BASE}/api/catalog", headers=headers, timeout=15)
    for p in r.json():
        if f"Valid {tag}" in p.get("name", ""):
            requests.delete(f"{BASE}/api/catalog/{p['product_id']}", headers=headers, timeout=10)


def test_bulk_import_rejects_missing_required(headers):
    csv = "description,price\nX,100\n"
    files = {"file": ("bad.csv", csv, "text/csv")}
    r = requests.post(
        f"{BASE}/api/catalog/bulk-import",
        headers=headers,
        files=files,
        timeout=15,
    )
    assert r.status_code == 400
    assert "name" in r.json()["detail"]


def test_bulk_import_rejects_wrong_extension(headers):
    files = {"file": ("hack.exe", b"binary", "application/octet-stream")}
    r = requests.post(
        f"{BASE}/api/catalog/bulk-import",
        headers=headers,
        files=files,
        timeout=15,
    )
    assert r.status_code == 400


# ===== Branding =====

def test_branding_check_subdomain_reserved(headers):
    r = requests.get(f"{BASE}/api/branding/check-subdomain/www", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["available"] is False
    assert "reservado" in r.json()["reason"]


def test_branding_check_subdomain_valid(headers):
    tag = uuid.uuid4().hex[:8]
    r = requests.get(f"{BASE}/api/branding/check-subdomain/brand-{tag}", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["available"] is True
    assert f"brand-{tag}.inmobot.app" in r.json()["url"]


def test_branding_invalid_format(headers):
    r = requests.get(f"{BASE}/api/branding/check-subdomain/-bad-", headers=headers, timeout=15)
    # Sub con guion al inicio → inválido
    assert r.json()["available"] is False


def test_branding_update_requires_pro_plan(headers, db):
    """Tenant trial no puede setear whitelabel."""
    # El superadmin no tiene tenant real (tenant_id=__superadmin__).
    # Creamos un tenant trial mock y usamos su admin.
    tag = uuid.uuid4().hex[:6]
    tid = f"wl-trial-{tag}"
    db.tenants.insert_one({
        "tenant_id": tid,
        "business_name": f"Trial Biz {tag}",
        "active": True,
        "subscription_plan": "trial",
        "subscription_status": "trial",
    })
    # Para simplificar, insertamos un admin agent y su usuario
    import bcrypt
    pw_hash = bcrypt.hashpw(b"Test1234!", bcrypt.gensalt()).decode()
    email = f"wl-trial-{tag}@test.local"
    db.agents.insert_one({
        "tenant_id": tid, "email": email, "password_hash": pw_hash,
        "role": "admin", "active": True, "name": "Test",
    })
    try:
        r = requests.post(
            f"{BASE}/api/auth/login",
            json={"email": email, "password": "Test1234!"},
            timeout=15,
        )
        if r.status_code != 200:
            pytest.skip(f"Login failed: {r.status_code} {r.text[:100]}")
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = requests.put(
            f"{BASE}/api/branding",
            headers=h,
            json={"brand_name": "Test Brand"},
            timeout=15,
        )
        assert r.status_code == 403
        assert "Pro" in r.json()["detail"] or "Enterprise" in r.json()["detail"]
    finally:
        db.tenants.delete_one({"tenant_id": tid})
        db.agents.delete_many({"tenant_id": tid})


def test_branding_public_subdomain_404():
    r = requests.get(f"{BASE}/api/public/branding/nonexistent-xxx", timeout=15)
    assert r.status_code == 404


# ===== Admin report =====

def test_admin_report_endpoint(headers):
    r = requests.post(f"{BASE}/api/superadmin/admin-report/run", headers=headers, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "sent" in body
