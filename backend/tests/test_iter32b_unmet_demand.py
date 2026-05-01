"""
Tests Iter32b: fuzzy short tokens + unmet demand + waitlist enriched + notify-now.
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
ADMIN = ("admin@inmobot.com", "Admin123!")


def _login(email, pwd):
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": pwd},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ----------------------------------------------------------------
# Fuzzy detection mejorada: tokens cortos como "S24", "X9", "15"
# ----------------------------------------------------------------

def test_fuzzy_matches_short_tokens(headers):
    """Antes 'tienen Samsung S24?' no matcheaba 'Samsung S24'. Ahora sí."""
    tag = uuid.uuid4().hex[:6]
    # Crear producto agotado con token corto
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"Samsung S24 {tag}",
            "price": 1000,
            "category": f"phones-{tag}",
            "stock_quantity": 0,
        },
        timeout=15,
    )
    pid = r.json()["product_id"]

    # Query con stopword + nombre + token corto + signo
    r = requests.post(
        f"{BASE}/api/catalog/substitute-preview",
        headers=headers,
        json={"query": f"tienen Samsung S24?"},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["out_of_stock_product"] is not None, (
        f"fuzzy no detectó match para Samsung S24. body={body}"
    )
    assert body["out_of_stock_product"]["product_id"] == pid

    # Cleanup
    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)


def test_fuzzy_handles_punctuation(headers):
    """Tokens como 'pro?' o 'pro!' deben normalizarse a 'pro'."""
    tag = uuid.uuid4().hex[:6]
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"iPhone Pro {tag}",
            "price": 1500,
            "category": f"iphones-{tag}",
            "stock_quantity": 0,
        },
        timeout=15,
    )
    pid = r.json()["product_id"]

    # Query con puntuación y stopword "tienen"
    for q in ("tienen iphone pro?", "quiero iphone pro!", "iphone Pro"):
        r = requests.post(
            f"{BASE}/api/catalog/substitute-preview",
            headers=headers,
            json={"query": q},
            timeout=15,
        )
        body = r.json()
        assert body["out_of_stock_product"] is not None, f"Falló para '{q}': {body}"

    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)


# ----------------------------------------------------------------
# Waitlist enriched: ahora incluye price, category, stock_quantity, is_out_of_stock
# ----------------------------------------------------------------

def test_waitlist_enriched_response(headers, db):
    tag = uuid.uuid4().hex[:6]
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"Enriched Test {tag}",
            "price": 200,
            "category": f"enr-{tag}",
            "currency": "USD",
            "stock_quantity": 0,
        },
        timeout=15,
    )
    pid = r.json()["product_id"]
    tid = r.json()["tenant_id"]
    db.product_waitlist.insert_one({
        "tenant_id": tid, "product_id": pid,
        "lead_phone": f"54911{tag}",
        "product_name": r.json()["name"],
        "asked_at": "2026-05-01T00:00:00+00:00",
        "notified_at": None,
        "created_at": "2026-05-01T00:00:00+00:00",
    })

    r = requests.get(f"{BASE}/api/catalog/waitlist", headers=headers, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "unique_products" in body
    target = next((p for p in body["by_product"] if p["product_id"] == pid), None)
    assert target is not None
    assert target["price"] == 200
    assert target["currency"] == "USD"
    assert target["is_out_of_stock"] is True
    assert target["leads_count"] == 1

    # Cleanup
    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)
    db.product_waitlist.delete_many({"tenant_id": tid, "product_id": pid})


# ----------------------------------------------------------------
# Notify-now endpoint: dispara notify_back_in_stock manualmente
# ----------------------------------------------------------------

def test_notify_now_endpoint(headers, db):
    tag = uuid.uuid4().hex[:6]
    # Producto AGOTADO → notify_now debe devolver 0 (no se envía si sigue out)
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"NotifyNow {tag}",
            "price": 50,
            "stock_quantity": 0,
        },
        timeout=15,
    )
    pid = r.json()["product_id"]
    tid = r.json()["tenant_id"]
    db.product_waitlist.insert_one({
        "tenant_id": tid, "product_id": pid,
        "lead_phone": "5499900000001",
        "product_name": r.json()["name"],
        "asked_at": "2026-05-01T00:00:00+00:00",
        "notified_at": None,
        "created_at": "2026-05-01T00:00:00+00:00",
    })
    r = requests.post(
        f"{BASE}/api/catalog/waitlist/notify/{pid}",
        headers=headers,
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["notified_leads"] == 0  # producto sigue agotado

    # Cleanup
    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)
    db.product_waitlist.delete_many({"tenant_id": tid, "product_id": pid})


# ----------------------------------------------------------------
# SuperAdmin /unmet-demand: estructura de respuesta + filtra repuestos
# ----------------------------------------------------------------

def test_unmet_demand_endpoint(headers, db):
    tag = uuid.uuid4().hex[:6]
    r = requests.post(
        f"{BASE}/api/catalog",
        headers=headers,
        json={
            "name": f"UnmetTest {tag}",
            "price": 999,
            "category": f"unmet-{tag}",
            "stock_quantity": 0,
        },
        timeout=15,
    )
    pid = r.json()["product_id"]
    tid = r.json()["tenant_id"]
    # 3 leads en waitlist
    db.product_waitlist.insert_many([
        {
            "tenant_id": tid, "product_id": pid,
            "lead_phone": f"54911{tag}{i}",
            "product_name": r.json()["name"],
            "asked_at": "2026-05-01T00:00:00+00:00",
            "notified_at": None,
            "created_at": "2026-05-01T00:00:00+00:00",
        } for i in range(3)
    ])

    r = requests.get(f"{BASE}/api/superadmin/unmet-demand?limit=20", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total_pending_leads" in body
    assert "top_products" in body
    target = next((p for p in body["top_products"] if p["product_id"] == pid), None)
    assert target is not None, f"Producto {pid} no aparece en top. body={body}"
    assert target["leads_count"] == 3
    assert target["urgency_score"] > 0
    assert target["product_exists"] is True
    assert target["price"] == 999

    # Reponer stock → en el siguiente fetch, producto NO debe aparecer
    requests.patch(
        f"{BASE}/api/catalog/products/{pid}/stock",
        headers=headers,
        json={"stock_quantity": 5},
        timeout=15,
    )
    r2 = requests.get(f"{BASE}/api/superadmin/unmet-demand?limit=20", headers=headers, timeout=15)
    body2 = r2.json()
    target2 = next((p for p in body2["top_products"] if p["product_id"] == pid), None)
    assert target2 is None, f"Producto repuesto sigue apareciendo: {target2}"

    # Cleanup
    requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)
    db.product_waitlist.delete_many({"tenant_id": tid, "product_id": pid})


# ----------------------------------------------------------------
# /config/* y /usage/* siguen vivos tras refactor
# ----------------------------------------------------------------

def test_config_endpoints_alive(headers):
    # admin@inmobot.com es superadmin (tenant=__superadmin__)
    # /config y /usage funcionan; /config/whatsapp y /config/ai pueden devolver 404
    # si no hay tenant doc — eso es expected.
    r = requests.get(f"{BASE}/api/config", headers=headers, timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{BASE}/api/usage", headers=headers, timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{BASE}/api/flow/config", headers=headers, timeout=15)
    assert r.status_code == 200
