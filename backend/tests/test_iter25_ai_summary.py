"""Iter25 - AI Lead Summary + Premium Features Showcase.
- Endpoint POST /api/leads/{phone}/ai-summary gateado por feature flag
- Endpoint GET /api/tenant/features-showcase
- Service lead_summary_service: cache, freshness, sanitización
"""
import os
import uuid
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DEMO_TENANT = "demo-inmobiliaria"
DEMO_EMAIL = "demo@inmobot.com"
DEMO_PASSWORD = "Demo123!"
SUPER_EMAIL = "admin@inmobot.com"
SUPER_PASSWORD = "Admin123!"


def _login(email, password):
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def super_headers():
    return {"Authorization": f"Bearer {_login(SUPER_EMAIL, SUPER_PASSWORD)}"}


@pytest.fixture(scope="module")
def tenant_headers():
    return {"Authorization": f"Bearer {_login(DEMO_EMAIL, DEMO_PASSWORD)}"}


@pytest.fixture()
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(autouse=True)
def reset_demo_features():
    """Reset features del demo tenant antes/después de cada test."""
    cli = MongoClient(os.environ["MONGO_URL"])
    d = cli[os.environ["DB_NAME"]]
    d.tenants.update_one({"tenant_id": DEMO_TENANT}, {"$set": {"features": {}}})
    yield
    d.tenants.update_one({"tenant_id": DEMO_TENANT}, {"$set": {"features": {}}})
    cli.close()


def _enable_flag(super_h, flag):
    requests.put(
        f"{BASE}/api/superadmin/tenants/{DEMO_TENANT}/features",
        headers=super_h,
        json={"feature": flag, "enabled": True},
    )


def _seed_lead(db, phone, history=None):
    db.leads.insert_one({
        "tenant_id": DEMO_TENANT,
        "phone": phone,
        "name": "Juan Pérez",
        "status": "warm",
        "score": 6,
        "conversation_history": history or [
            {"role": "user", "content": "Hola, busco un PH 2 ambientes en Palermo, presupuesto USD 180k"},
            {"role": "assistant", "content": "Tenemos varios. ¿Necesita patio?"},
            {"role": "user", "content": "Sí, con patio y luminoso. Necesito mudarme en 30 días"},
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_message_at": datetime.now(timezone.utc).isoformat(),
        "tags": [],
    })


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


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    """Asegura que OPENAI_API_KEY esté seteada para que LLMService.enabled=True
    (sin esto, las nuevas instancias serían disabled y nunca llamarían al mock)."""
    if not os.environ.get("OPENAI_API_KEY"):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-for-mocking")


# ---------------- /api/tenant/features-showcase ----------------
class TestFeaturesShowcaseEndpoint:
    def test_no_auth_blocked(self):
        r = requests.get(f"{BASE}/api/tenant/features-showcase")
        assert r.status_code in (401, 403)

    def test_returns_active_and_available(self, tenant_headers):
        r = requests.get(f"{BASE}/api/tenant/features-showcase", headers=tenant_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("active", "available", "total"):
            assert k in d
        # Sin overrides, todas deberían estar en "available" (defaults=False)
        assert len(d["available"]) == d["total"]
        assert len(d["active"]) == 0
        # Cada item tiene shape correcto
        if d["available"]:
            f = d["available"][0]
            for key in ("key", "label", "description", "category", "enabled"):
                assert key in f
            assert f["enabled"] is False

    def test_active_feature_appears_in_active(self, tenant_headers, super_headers):
        _enable_flag(super_headers, "ai_lead_summary")
        r = requests.get(f"{BASE}/api/tenant/features-showcase", headers=tenant_headers)
        d = r.json()
        active_keys = [f["key"] for f in d["active"]]
        assert "ai_lead_summary" in active_keys
        # Y NO está en available
        avail_keys = [f["key"] for f in d["available"]]
        assert "ai_lead_summary" not in avail_keys
        assert len(d["active"]) + len(d["available"]) == d["total"]


# ---------------- POST /api/leads/{phone}/ai-summary ----------------
class TestAILeadSummaryEndpoint:
    def test_no_auth_blocked(self):
        r = requests.post(f"{BASE}/api/leads/some-phone/ai-summary")
        assert r.status_code in (401, 403)

    def test_feature_disabled_returns_403(self, tenant_headers):
        r = requests.post(
            f"{BASE}/api/leads/anyphone/ai-summary",
            headers=tenant_headers,
        )
        assert r.status_code == 403
        assert "ai_lead_summary" in r.json().get("detail", "").lower()

    def test_feature_enabled_lead_not_found_404(self, tenant_headers, super_headers):
        _enable_flag(super_headers, "ai_lead_summary")
        r = requests.post(
            f"{BASE}/api/leads/non_existent_phone_xyz/ai-summary",
            headers=tenant_headers,
        )
        assert r.status_code == 404

    def test_full_flow_with_mocked_llm(self, tenant_headers, super_headers, db):
        """Llama directo al service con LLM mockeado (los HTTP tests no pueden patchear
        el proceso del server uvicorn corriendo aparte)."""
        from lead_summary_service import generate_lead_summary
        marker = uuid.uuid4().hex[:6]
        phone = f"+54911{marker}"
        _seed_lead(db, phone)

        mock_response = json.dumps({
            "narrative": "Busca PH 2amb en Palermo bajo USD 180k, urge mudarse en 30 días",
            "urgency": 9,
            "urgency_reason": "Plazo de mudanza concreto y presupuesto definido",
            "next_step": "Mandarle 3 PHs en Palermo bajo USD 180k con patio HOY",
            "insights": [
                "Quiere PH 2 ambientes con patio",
                "Presupuesto: USD 180k",
                "Necesita mudarse en 30 días",
            ],
            "buying_signals": [
                "Necesito mudarme en 30 días",
                "Sí, con patio y luminoso",
            ],
        })

        try:
            with patch("llm_service.LLMService.send_message",
                       new_callable=AsyncMock, return_value=mock_response):
                d = _run_async(
                    lambda adb: generate_lead_summary(adb, DEMO_TENANT, phone)
                )
            assert d is not None
            assert d["narrative"].startswith("Busca PH")
            assert d["urgency"] == 9
            assert d["urgency_reason"]
            assert d["next_step"].startswith("Mandarle 3 PHs")
            assert len(d["insights"]) == 3
            assert len(d["buying_signals"]) == 2
            assert d["cached"] is False
            # 2da call sin force=true debe volver cacheado SIN llamar al LLM
            with patch("llm_service.LLMService.send_message",
                       new_callable=AsyncMock) as mock2:
                d2 = _run_async(
                    lambda adb: generate_lead_summary(adb, DEMO_TENANT, phone)
                )
                mock2.assert_not_called()
            assert d2["cached"] is True
        finally:
            db.leads.delete_one({"phone": phone})

    def test_force_regenerates(self, tenant_headers, super_headers, db):
        from lead_summary_service import generate_lead_summary
        marker = uuid.uuid4().hex[:6]
        phone = f"+54912{marker}"
        _seed_lead(db, phone)

        old_response = json.dumps({
            "narrative": "Resumen viejo", "urgency": 5, "urgency_reason": "—",
            "next_step": "Hacer follow-up", "insights": [], "buying_signals": [],
        })
        new_response = json.dumps({
            "narrative": "Resumen nuevo", "urgency": 8, "urgency_reason": "—",
            "next_step": "Cerrar venta", "insights": ["x"], "buying_signals": [],
        })
        try:
            with patch("llm_service.LLMService.send_message",
                       new_callable=AsyncMock, return_value=old_response):
                _run_async(lambda adb: generate_lead_summary(adb, DEMO_TENANT, phone))
            with patch("llm_service.LLMService.send_message",
                       new_callable=AsyncMock, return_value=new_response) as m:
                d = _run_async(
                    lambda adb: generate_lead_summary(adb, DEMO_TENANT, phone, force=True)
                )
                m.assert_called_once()
            assert d["narrative"] == "Resumen nuevo"
            assert d["urgency"] == 8
            assert d["cached"] is False
        finally:
            db.leads.delete_one({"phone": phone})


# ---------------- Service unit tests ----------------
class TestSummaryServiceUnits:
    def test_format_history_handles_empty(self):
        from lead_summary_service import _format_history
        assert _format_history([]) == "(sin conversación previa)"

    def test_format_history_truncates(self):
        from lead_summary_service import _format_history, MAX_HISTORY_TURNS
        history = [{"role": "user", "content": f"msg {i}"} for i in range(50)]
        text = _format_history(history)
        # Solo los últimos MAX_HISTORY_TURNS turnos
        lines = [l for l in text.split("\n") if l]
        assert len(lines) <= MAX_HISTORY_TURNS

    def test_is_summary_fresh_no_cache(self):
        from lead_summary_service import _is_summary_fresh
        assert _is_summary_fresh({"phone": "x"}) is False

    def test_is_summary_fresh_expired(self):
        from lead_summary_service import _is_summary_fresh, SUMMARY_TTL_DAYS
        old = datetime.now(timezone.utc) - timedelta(days=SUMMARY_TTL_DAYS + 1)
        lead = {
            "ai_summary": {"generated_at": old.isoformat(), "history_len_at_gen": 3},
            "conversation_history": [1, 2, 3],
        }
        assert _is_summary_fresh(lead) is False

    def test_is_summary_fresh_history_changed(self):
        from lead_summary_service import _is_summary_fresh
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        lead = {
            "ai_summary": {"generated_at": recent.isoformat(), "history_len_at_gen": 3},
            "conversation_history": [1, 2, 3, 4],  # creció
        }
        assert _is_summary_fresh(lead) is False

    def test_is_summary_fresh_valid(self):
        from lead_summary_service import _is_summary_fresh
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        lead = {
            "ai_summary": {"generated_at": recent.isoformat(), "history_len_at_gen": 3},
            "conversation_history": [1, 2, 3],
        }
        assert _is_summary_fresh(lead) is True

    def test_generate_returns_none_for_unknown_lead(self, db):
        from lead_summary_service import generate_lead_summary
        result = _run_async(
            lambda adb: generate_lead_summary(adb, DEMO_TENANT, "phone_no_existe_xyz")
        )
        assert result is None

    def test_sanitization_clamps_urgency(self, super_headers, tenant_headers, db):
        """Si el LLM devuelve urgency=99, debe clamparse a 10."""
        from lead_summary_service import generate_lead_summary
        marker = uuid.uuid4().hex[:6]
        phone = f"+54913{marker}"
        _seed_lead(db, phone)

        crazy_response = json.dumps({
            "narrative": "x", "urgency": 99, "urgency_reason": "y",
            "next_step": "z", "insights": [], "buying_signals": [],
        })
        try:
            with patch("llm_service.LLMService.send_message",
                       new_callable=AsyncMock, return_value=crazy_response):
                d = _run_async(lambda adb: generate_lead_summary(adb, DEMO_TENANT, phone))
            assert d is not None
            assert d["urgency"] == 10
        finally:
            db.leads.delete_one({"phone": phone})

    def test_handles_markdown_wrapped_json(self, super_headers, tenant_headers, db):
        """Algunos modelos envuelven el JSON en ```json … ```. Debe parsearlo igual."""
        from lead_summary_service import generate_lead_summary
        marker = uuid.uuid4().hex[:6]
        phone = f"+54914{marker}"
        _seed_lead(db, phone)

        wrapped = "```json\n" + json.dumps({
            "narrative": "Wrapped", "urgency": 5, "urgency_reason": "x",
            "next_step": "y", "insights": [], "buying_signals": [],
        }) + "\n```"
        try:
            with patch("llm_service.LLMService.send_message",
                       new_callable=AsyncMock, return_value=wrapped):
                d = _run_async(lambda adb: generate_lead_summary(adb, DEMO_TENANT, phone))
            assert d is not None
            assert d["narrative"] == "Wrapped"
        finally:
            db.leads.delete_one({"phone": phone})
