"""Iter 16 - Tests E2E con OpenAI MOCKED via respx.

Validamos que con una API key 'fake' (mockeamos la respuesta HTTP de OpenAI):
  - Preview valido devuelve 200 con preview.actions/operations
  - LLM devolviendo JSON malformado -> 502
  - LLM levantando excepcion -> 502
  - Rate-limit kicks in: tras 10 calls successful, el 11vo da 429
  - bot_config_ai y flow_ai ambos cubiertos
"""
import json
import os
import uuid
import pytest
import respx
import httpx
from fastapi.testclient import TestClient


# IMPORTANTE: setear OPENAI_API_KEY ANTES de importar 'server' (lazy llm cache)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-for-mock")


@pytest.fixture(scope="module")
def client():
    # Importar app DESPUES de setear env
    import sys
    # Forzar recarga de llm_service para que recoja la key fake
    if "llm_service" in sys.modules:
        del sys.modules["llm_service"]
    from server import app  # noqa
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "demo@inmobot.com", "password": "Demo123!"},
    )
    assert res.status_code == 200, f"Login fallo: {res.text}"
    return res.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


def _openai_response(content_dict: dict) -> httpx.Response:
    """Construye una respuesta valida del endpoint chat.completions con el content provisto."""
    body = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": json.dumps(content_dict, ensure_ascii=False)},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }
    return httpx.Response(200, json=body)


# ---------------- bot-config/ai-edit ----------------

@respx.mock
def test_bot_config_ai_preview_with_mocked_llm(client, auth_headers):
    """LLM devuelve JSON valido -> preview.actions tiene el cambio."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=_openai_response({
            "actions": [{
                "field": "business_hours_end",
                "value": 19,
                "explanation": "Cambio horario fin a 19hs",
            }],
            "summary": "Actualicé el horario de cierre",
        })
    )
    r = client.post(
        "/api/bot-config/ai-edit",
        json={"instruction": "cambia el horario de cierre a 19hs"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["applied"] is False
    assert len(data["preview"]["actions"]) == 1
    assert data["preview"]["actions"][0]["field"] == "business_hours_end"
    assert data["preview"]["actions"][0]["value"] == 19


@respx.mock
def test_bot_config_ai_invalid_json_returns_502(client, auth_headers):
    """LLM devuelve texto que NO es JSON -> 502."""
    bad = httpx.Response(200, json={
        "id": "x", "object": "chat.completion", "created": 0, "model": "gpt-4o",
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": "esto no es JSON valido"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=bad)
    r = client.post(
        "/api/bot-config/ai-edit",
        json={"instruction": "test invalid json"},
        headers=auth_headers,
    )
    assert r.status_code == 502, r.text
    assert "invalida" in r.json()["detail"].lower() or "malformado" in r.json()["detail"].lower()


@respx.mock
def test_bot_config_ai_openai_5xx_returns_502(client, auth_headers):
    """OpenAI devuelve 500 -> SDK retry y luego excepcion -> nuestro endpoint da 502."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": {"message": "openai down"}})
    )
    r = client.post(
        "/api/bot-config/ai-edit",
        json={"instruction": "test 5xx"},
        headers=auth_headers,
    )
    assert r.status_code == 502, r.text


@respx.mock
def test_bot_config_ai_invalid_field_goes_to_invalid_array(client, auth_headers):
    """LLM intenta modificar un campo NO whitelisted -> aparece en invalid[]."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=_openai_response({
            "actions": [
                {"field": "campo_no_existe", "value": 123, "explanation": "no permitido"},
                {"field": "auto_handoff_score", "value": 8, "explanation": "ok"},
            ],
            "summary": "mix de validos e invalidos",
        })
    )
    r = client.post(
        "/api/bot-config/ai-edit",
        json={"instruction": "test invalid field"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["preview"]["actions"]) == 1
    assert data["preview"]["actions"][0]["field"] == "auto_handoff_score"
    assert len(data["preview"]["invalid"]) == 1
    assert data["preview"]["invalid"][0]["field"] == "campo_no_existe"


@respx.mock
def test_bot_config_ai_rate_limit_kicks_in_at_11th(client, auth_headers):
    """Tras 10 calls exitosos, el 11vo debe dar 429."""
    # Reset rate-limit bucket (in-memory) reiniciando
    from rate_limit import _in_memory_buckets
    _in_memory_buckets.clear()

    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=_openai_response({"actions": [], "summary": "ok"})
    )
    statuses = []
    for i in range(11):
        r = client.post(
            "/api/bot-config/ai-edit",
            json={"instruction": f"test rate limit {i}"},
            headers=auth_headers,
        )
        statuses.append(r.status_code)
    # Los primeros 10 deben ser 200; el 11vo 429
    assert statuses.count(200) == 10, f"esperaba 10x200, got: {statuses}"
    assert statuses[-1] == 429, f"11vo debio ser 429, got: {statuses}"


# ---------------- flow/ai-edit ----------------

@respx.mock
def test_flow_ai_preview_with_mocked_llm(client, auth_headers):
    """flow-ai: LLM devuelve operations validas -> preview muestra ops y cambia step count."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=_openai_response({
            "operations": [
                {"op": "update_welcome",
                 "params": {"text": "Hola! Soy InmoBot, te ayudo a encontrar tu lugar ideal"},
                 "explanation": "Mensaje de bienvenida nuevo"},
                {"op": "add_step",
                 "params": {"question": "Cual es tu barrio preferido?",
                            "type": "text",
                            "field": "custom_fields.barrio"},
                 "explanation": "Agregar paso barrio"},
            ],
            "summary": "Mensaje + paso barrio",
        })
    )
    r = client.post(
        "/api/flow/ai-edit",
        json={"instruction": "cambia bienvenida y agrega paso barrio"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["applied"] is False
    ops = data["preview"]["operations"]
    assert len(ops) == 2
    assert ops[0]["op"] == "update_welcome"
    assert ops[1]["op"] == "add_step"
    assert data["preview"]["preview_step_count"] == data["preview"]["current_step_count"] + 1


@respx.mock
def test_flow_ai_truncates_to_20_ops(client, auth_headers):
    """LLM devuelve 25 ops -> preview tiene 20 + truncated=true."""
    big_ops = []
    for i in range(25):
        big_ops.append({
            "op": "update_welcome",
            "params": {"text": f"Mensaje variante {i}"},
        })
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=_openai_response({"operations": big_ops, "summary": "muchos ops"})
    )
    r = client.post(
        "/api/flow/ai-edit",
        json={"instruction": "stress test truncate"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Solo update_welcome es valido (el resto son repetidos pero igual validos);
    # lo importante es que NO haya mas de 20 procesados.
    total = len(data["preview"]["operations"]) + len(data["preview"]["invalid"])
    assert total <= 20, f"Esperaba <=20 ops procesadas, got {total}"
    assert data["preview"]["truncated"] is True
    assert data["preview"]["max_ops"] == 20


@respx.mock
def test_flow_ai_apply_path_does_not_call_llm(client, auth_headers):
    """confirm=true + confirmed_ops -> NO llama OpenAI (no respx route necesario)."""
    # Sin route para OpenAI: si el endpoint la llamara, respx daria error.
    r = client.post(
        "/api/flow/ai-edit",
        json={
            "instruction": "apply only",
            "confirm": True,
            "confirmed_ops": [
                {"op": "update_welcome", "params": {"text": "Test apply path - no LLM"}}
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True
    assert r.json()["applied_count"] == 1

    # Restaurar
    client.post("/api/flow/reset", headers=auth_headers)


@respx.mock
def test_bot_config_apply_path_does_not_call_llm(client, auth_headers):
    """bot-config-ai con confirmed_actions -> NO llama OpenAI."""
    r = client.post(
        "/api/bot-config/ai-edit",
        json={
            "instruction": "apply",
            "confirm": True,
            "confirmed_actions": [{"field": "auto_handoff_score", "value": 8}],
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True

    # Restaurar a 7 (default)
    client.post(
        "/api/bot-config/ai-edit",
        json={
            "instruction": "restore",
            "confirm": True,
            "confirmed_actions": [{"field": "auto_handoff_score", "value": 7}],
        },
        headers=auth_headers,
    )
