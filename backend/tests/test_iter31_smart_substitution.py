"""Iter31 - Smart Substitution: stock, substitutes, out-of-stock detection."""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
DEMO = ("demo@inmobot.com", "Demo123!")


def _login(email, pwd):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers():
    return {"Authorization": f"Bearer {_login(*DEMO)}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture
def tmp_products(headers):
    """Crea producto A (agotado) + 2 sustitutos + cleanup."""
    tag = uuid.uuid4().hex[:6]
    created_ids = []
    # A (protagonista, lo marcaremos agotado)
    r = requests.post(f"{BASE}/api/catalog", headers=headers, json={
        "name": f"iPhone 15 Pro Test {tag}", "description": "Celular premium",
        "price": 1200, "currency": "USD", "category": f"cat_{tag}",
    }, timeout=20)
    a = r.json(); created_ids.append(a["product_id"])
    # B (sustituto mismo categoria, precio cercano)
    r = requests.post(f"{BASE}/api/catalog", headers=headers, json={
        "name": f"iPhone 15 Test {tag}", "description": "Celular",
        "price": 1000, "currency": "USD", "category": f"cat_{tag}",
    }, timeout=20)
    b = r.json(); created_ids.append(b["product_id"])
    # C (misma categoria, precio lejano)
    r = requests.post(f"{BASE}/api/catalog", headers=headers, json={
        "name": f"iPhone 13 Test {tag}", "description": "Celular viejo",
        "price": 600, "currency": "USD", "category": f"cat_{tag}",
    }, timeout=20)
    c = r.json(); created_ids.append(c["product_id"])
    yield {"A": a, "B": b, "C": c, "tag": tag}
    # cleanup: desactivar
    for pid in created_ids:
        try:
            requests.delete(f"{BASE}/api/catalog/{pid}", headers=headers, timeout=10)
        except Exception:
            pass


# ============================================================
# Stock endpoint
# ============================================================

def test_set_stock_to_zero_marks_out_of_stock(headers, tmp_products, db):
    pid = tmp_products["A"]["product_id"]
    r = requests.patch(f"{BASE}/api/catalog/products/{pid}/stock",
                       headers=headers, json={"stock_quantity": 0}, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["stock_quantity"] == 0
    assert body["active"] is False
    assert body["availability_status"] == "out_of_stock"


def test_set_stock_positive_reactivates(headers, tmp_products):
    pid = tmp_products["A"]["product_id"]
    requests.patch(f"{BASE}/api/catalog/products/{pid}/stock",
                   headers=headers, json={"stock_quantity": 0}, timeout=20)
    r = requests.patch(f"{BASE}/api/catalog/products/{pid}/stock",
                       headers=headers, json={"stock_quantity": 5}, timeout=20)
    body = r.json()
    assert body["stock_quantity"] == 5
    assert body["active"] is True
    assert body["availability_status"] in ("available", "low_stock")


def test_set_stock_null_means_no_tracking(headers, tmp_products):
    pid = tmp_products["A"]["product_id"]
    r = requests.patch(f"{BASE}/api/catalog/products/{pid}/stock",
                       headers=headers, json={"stock_quantity": None}, timeout=20)
    body = r.json()
    assert body["stock_quantity"] is None
    assert body["availability_status"] == "no_tracking"


def test_set_stock_invalid_type_400(headers, tmp_products):
    pid = tmp_products["A"]["product_id"]
    r = requests.patch(f"{BASE}/api/catalog/products/{pid}/stock",
                       headers=headers, json={"stock_quantity": "mucho"}, timeout=20)
    assert r.status_code == 400


def test_set_stock_404_for_nonexistent(headers):
    r = requests.patch(f"{BASE}/api/catalog/products/pid-que-no-existe/stock",
                       headers=headers, json={"stock_quantity": 5}, timeout=20)
    assert r.status_code == 404


# ============================================================
# Substitutes config
# ============================================================

def test_set_substitutes_valid(headers, tmp_products):
    a = tmp_products["A"]["product_id"]
    b = tmp_products["B"]["product_id"]
    c = tmp_products["C"]["product_id"]
    r = requests.put(f"{BASE}/api/catalog/products/{a}/substitutes",
                     headers=headers,
                     json={"substitute_product_ids": [b, c]}, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["substitute_product_ids"] == [b, c]


def test_set_substitutes_rejects_unknown_id(headers, tmp_products):
    a = tmp_products["A"]["product_id"]
    r = requests.put(f"{BASE}/api/catalog/products/{a}/substitutes",
                     headers=headers,
                     json={"substitute_product_ids": ["no-existo-xyz"]},
                     timeout=20)
    assert r.status_code == 404


def test_set_substitutes_rejects_non_array(headers, tmp_products):
    a = tmp_products["A"]["product_id"]
    r = requests.put(f"{BASE}/api/catalog/products/{a}/substitutes",
                     headers=headers,
                     json={"substitute_product_ids": "not-a-list"},
                     timeout=20)
    assert r.status_code == 400


def test_set_substitutes_max_10(headers, tmp_products):
    a = tmp_products["A"]["product_id"]
    r = requests.put(f"{BASE}/api/catalog/products/{a}/substitutes",
                     headers=headers,
                     json={"substitute_product_ids": [f"x{i}" for i in range(11)]},
                     timeout=20)
    assert r.status_code == 400


# ============================================================
# Substitute preview endpoint (query + product_id modes)
# ============================================================

def test_preview_by_query_detects_out_of_stock(headers, tmp_products):
    a = tmp_products["A"]
    # Marcar A como agotado
    requests.patch(f"{BASE}/api/catalog/products/{a['product_id']}/stock",
                   headers=headers, json={"stock_quantity": 0}, timeout=20)
    # Cliente pregunta por ese producto usando parte del nombre
    query = f"tienen disponible el iPhone 15 Pro Test {tmp_products['tag']}?"
    r = requests.post(f"{BASE}/api/catalog/substitute-preview",
                      headers=headers, json={"query": query}, timeout=25)
    assert r.status_code == 200
    body = r.json()
    assert body["out_of_stock_product"] is not None
    assert body["out_of_stock_product"]["product_id"] == a["product_id"]
    # Sustitutos: al menos 1 (B es el mas cercano en categoria+precio)
    assert len(body["substitutes"]) >= 1
    # El primer sustituto debería ser B (precio más cercano en misma cat)
    assert body["substitutes"][0]["product_id"] == tmp_products["B"]["product_id"]
    assert "agotado" in body["message"].lower()
    assert tmp_products["B"]["name"] in body["message"]


def test_preview_no_match_returns_null(headers, tmp_products):
    r = requests.post(f"{BASE}/api/catalog/substitute-preview",
                      headers=headers, json={"query": "quiero un tractor amarillo"},
                      timeout=20)
    body = r.json()
    assert body["out_of_stock_product"] is None
    assert body["substitutes"] == []
    assert body["message"] is None


def test_preview_by_product_id_when_out_of_stock(headers, tmp_products):
    a = tmp_products["A"]
    requests.patch(f"{BASE}/api/catalog/products/{a['product_id']}/stock",
                   headers=headers, json={"stock_quantity": 0}, timeout=20)
    r = requests.post(f"{BASE}/api/catalog/substitute-preview",
                      headers=headers,
                      json={"product_id": a["product_id"]}, timeout=25)
    body = r.json()
    assert body["out_of_stock_product"]["product_id"] == a["product_id"]


def test_preview_by_product_id_when_available_returns_null(headers, tmp_products):
    b = tmp_products["B"]
    # B está disponible (stock=None = no_tracking)
    r = requests.post(f"{BASE}/api/catalog/substitute-preview",
                      headers=headers,
                      json={"product_id": b["product_id"]}, timeout=20)
    body = r.json()
    assert body["out_of_stock_product"] is None


# ============================================================
# Substitution cascade: manual > category > GPT fallback
# ============================================================

def test_manual_substitutes_take_priority(headers, tmp_products):
    a, b, c = tmp_products["A"], tmp_products["B"], tmp_products["C"]
    # Config: A tiene como sustituto manual SOLO a C (no B que es el mejor por precio)
    requests.put(f"{BASE}/api/catalog/products/{a['product_id']}/substitutes",
                 headers=headers,
                 json={"substitute_product_ids": [c["product_id"]]}, timeout=20)
    # Marcar A como agotado
    requests.patch(f"{BASE}/api/catalog/products/{a['product_id']}/stock",
                   headers=headers, json={"stock_quantity": 0}, timeout=20)
    # Preview
    r = requests.post(f"{BASE}/api/catalog/substitute-preview",
                      headers=headers,
                      json={"product_id": a["product_id"]}, timeout=25)
    subs = r.json()["substitutes"]
    assert len(subs) >= 1
    # C (manual) debe aparecer primero, aunque B sea mejor por precio automatico
    assert subs[0]["product_id"] == c["product_id"]


def test_message_built_correctly_single_substitute(headers, tmp_products):
    a = tmp_products["A"]
    requests.patch(f"{BASE}/api/catalog/products/{a['product_id']}/stock",
                   headers=headers, json={"stock_quantity": 0}, timeout=20)
    r = requests.post(f"{BASE}/api/catalog/substitute-preview",
                      headers=headers,
                      json={"product_id": a["product_id"]}, timeout=25)
    msg = r.json()["message"]
    assert "🙂" not in msg or True  # no exige emoji específico
    assert a["name"] in msg
    assert "diferencias" in msg or "alternativas" in msg or "interesan" in msg.lower()


def test_availability_status_low_stock(headers, tmp_products):
    b = tmp_products["B"]
    r = requests.patch(f"{BASE}/api/catalog/products/{b['product_id']}/stock",
                       headers=headers, json={"stock_quantity": 2}, timeout=20)
    assert r.json()["availability_status"] == "low_stock"
