"""Router de Asistente IA para editar el arbol del FlowBuilder via lenguaje natural.

Operaciones soportadas (whitelist):
- add_step: agrega un paso nuevo al final
- update_step: cambia question/type/buttons de un paso por id
- remove_step: elimina paso por id
- reorder_step: cambia posicion de un paso (id + new_index)
- update_welcome: cambia welcome_message
- update_completion: cambia completion_message
- update_appointment: cambia appointment_message

Los cambios se aplican al `custom_flow_steps`/`custom_*` del bot_config (mismo lugar que /flow/config PUT).
"""
import json
import re
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import require_admin, get_db
from models import User
from rate_limit import check_rate_limit, get_retry_after
from cache_util import ttl_cache_get, ttl_cache_set

logger = logging.getLogger(__name__)
router = APIRouter(tags=["flow-ai"])

_RATE_MAX = 8
_RATE_WINDOW = 3600
_TENANT_CACHE_TTL = 60.0   # segundos
_MAX_OPS_PREVIEW = 20      # tope defensivo contra respuestas LLM excesivas

# Whitelist de operaciones
_VALID_OPS = {
    "add_step", "update_step", "remove_step", "reorder_step",
    "update_welcome", "update_completion", "update_appointment",
}
_VALID_STEP_TYPES = {"text", "buttons", "list"}


SYSTEM_PROMPT = """Sos un asistente que traduce instrucciones de un usuario en operaciones JSON sobre un arbol de flujo de bot de WhatsApp.

Devolve SOLO un JSON con esta estructura exacta (sin markdown, sin texto extra):
{
  "operations": [
    {"op": "<operacion>", "params": {<parametros>}, "explanation": "que hace en lenguaje natural"}
  ],
  "summary": "resumen breve"
}

Operaciones validas y sus parametros:
- add_step: {"question": "texto pregunta", "type": "text|buttons|list", "field": "custom_fields.NOMBRE", "buttons": [{"id": "opt1", "title": "Opcion 1"}, ...] (solo si type=buttons)}
- update_step: {"step_id": "id_existente", "question": "...", "type": "...", "buttons": [...]}
  (cualquier campo es opcional; solo cambia los provistos)
- remove_step: {"step_id": "id_existente"}
- reorder_step: {"step_id": "id_existente", "new_index": 0..N-1}
- update_welcome: {"text": "nuevo mensaje de bienvenida"}
- update_completion: {"text": "nuevo mensaje de cierre"}
- update_appointment: {"text": "nuevo mensaje de agendamiento de cita"}

Reglas:
- Si el usuario pide algo fuera de estas operaciones, devolve operations:[] y summary explicando.
- Para add_step, generar field en formato "custom_fields.NOMBRE" (snake_case, sin acentos).
- Para buttons usar maximo 3 botones (limite WhatsApp).
- Para list usar maximo 10 opciones.
- Escribi en ESPANOL rioplatense (vos)."""


def _validate_op(op: dict, existing_steps: list):
    """Valida una operacion. Devuelve (None, normalized_op) o (error_str, None)."""
    if not isinstance(op, dict):
        return ("operacion no es objeto", None)
    name = op.get("op")
    params = op.get("params") or {}
    if name not in _VALID_OPS:
        return (f"op invalida: {name}", None)
    if not isinstance(params, dict):
        return ("params debe ser objeto", None)

    step_ids = {s.get("id") for s in existing_steps if isinstance(s, dict)}

    if name == "add_step":
        q = params.get("question")
        t = params.get("type", "text")
        f = params.get("field", "")
        if not isinstance(q, str) or not (1 <= len(q) <= 500):
            return ("question requerido (1-500 chars)", None)
        if t not in _VALID_STEP_TYPES:
            return (f"type invalido: {t}", None)
        if not isinstance(f, str) or not re.match(r"^custom_fields\.[a-z0-9_]+$", f):
            f = f"custom_fields.campo_{len(existing_steps)+1}"
        bts = params.get("buttons") or []
        if t == "buttons":
            if not isinstance(bts, list) or not (1 <= len(bts) <= 3):
                return ("buttons requeridos (1-3) para type=buttons", None)
            for b in bts:
                if not isinstance(b, dict) or not b.get("title") or not b.get("id"):
                    return ("cada button necesita id y title", None)
        if t == "list" and (not isinstance(bts, list) or len(bts) > 10):
            return ("list maximo 10 opciones", None)
        return (None, {"op": name, "params": {
            "question": q, "type": t, "field": f, "buttons": bts,
        }})

    if name in ("update_step", "remove_step", "reorder_step"):
        sid = params.get("step_id")
        if not sid or sid not in step_ids:
            return (f"step_id no encontrado: {sid}", None)
        if name == "reorder_step":
            ni = params.get("new_index")
            if not isinstance(ni, int) or not (0 <= ni < len(existing_steps)):
                return ("new_index fuera de rango", None)
        if name == "update_step":
            t = params.get("type")
            if t is not None and t not in _VALID_STEP_TYPES:
                return (f"type invalido: {t}", None)
            q = params.get("question")
            if q is not None and (not isinstance(q, str) or not q.strip()):
                return ("question vacio", None)
        return (None, {"op": name, "params": params})

    if name in ("update_welcome", "update_completion", "update_appointment"):
        txt = params.get("text")
        if not isinstance(txt, str) or not (1 <= len(txt) <= 1000):
            return ("text invalido (1-1000 chars)", None)
        return (None, {"op": name, "params": {"text": txt}})

    return ("op no manejada", None)


def _apply_ops(state: dict, ops: list) -> dict:
    """Aplica ops sobre una copia del state (welcome_message, completion_message, etc., flow_steps).
    Devuelve nuevo state."""
    s = json.loads(json.dumps(state))  # deep copy
    steps = s.setdefault("flow_steps", [])

    for op in ops:
        name = op["op"]
        p = op["params"]
        if name == "add_step":
            new = {
                "id": f"step_{uuid.uuid4().hex[:8]}",
                "question": p["question"],
                "type": p["type"],
                "field": p["field"],
            }
            if p.get("buttons"):
                new["buttons"] = p["buttons"]
            steps.append(new)
        elif name == "update_step":
            for st in steps:
                if st.get("id") == p["step_id"]:
                    for k in ("question", "type", "field", "buttons"):
                        if k in p:
                            st[k] = p[k]
                    break
        elif name == "remove_step":
            s["flow_steps"] = [st for st in steps if st.get("id") != p["step_id"]]
            steps = s["flow_steps"]
        elif name == "reorder_step":
            idx = next((i for i, st in enumerate(steps) if st.get("id") == p["step_id"]), None)
            if idx is None:
                continue
            item = steps.pop(idx)
            steps.insert(p["new_index"], item)
        elif name == "update_welcome":
            s["welcome_message"] = p["text"]
        elif name == "update_completion":
            s["completion_message"] = p["text"]
        elif name == "update_appointment":
            s["appointment_message"] = p["text"]
    return s


async def _load_flow_state(db, current_user) -> dict:
    """Lee el estado actual del flujo (custom + fallback al template base).
    Cachea tenant lookup por TTL corto para soportar trafico alto."""
    from flow_templates import get_template
    cached_tenant = ttl_cache_get("tenants", current_user.tenant_id)
    if cached_tenant is None:
        cached_tenant = await db.tenants.find_one(
            {"tenant_id": current_user.tenant_id}, {"_id": 0}
        ) or {}
        ttl_cache_set("tenants", current_user.tenant_id, cached_tenant, ttl=_TENANT_CACHE_TTL)
    base = get_template(cached_tenant.get("template_id", "servicios"))
    cfg = await db.bot_config.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0}) or {}
    return {
        "welcome_message": cfg.get("custom_welcome_message") or base.get("welcome_message", ""),
        "completion_message": cfg.get("custom_completion_message") or base.get("completion_message", ""),
        "appointment_message": cfg.get("custom_appointment_message") or base.get("appointment_message", ""),
        "flow_steps": cfg.get("custom_flow_steps") or list(base.get("flow_steps", [])),
    }


@router.post("/flow/ai-edit")
async def ai_edit_flow(
    body: dict,
    current_user: User = Depends(require_admin),
    db = Depends(get_db),
):
    """Recibe instruction (lenguaje natural) y devuelve un preview de operaciones.
    Si confirm=True + confirmed_ops viene del preview, las aplica al bot_config."""
    instruction = (body or {}).get("instruction", "").strip()
    confirm = bool((body or {}).get("confirm", False))
    confirmed_ops = (body or {}).get("confirmed_ops")

    if not instruction:
        raise HTTPException(status_code=400, detail="instruction requerido")
    if len(instruction) > 500:
        raise HTTPException(status_code=400, detail="instruction demasiado largo (>500 chars)")

    # Apply path: usa ops ya validadas del preview (no llama LLM otra vez)
    if confirm and isinstance(confirmed_ops, list) and confirmed_ops:
        state = await _load_flow_state(db, current_user)
        valid = []
        invalid = []
        for op in confirmed_ops:
            err, normalized = _validate_op(op, state["flow_steps"])
            if err:
                invalid.append({"op": op.get("op"), "reason": err})
            else:
                valid.append(normalized)
                # Re-leemos steps para validar la siguiente op contra estado intermedio
                state = _apply_ops(state, [normalized])

        if not valid:
            raise HTTPException(status_code=400, detail="confirmed_ops invalidas")

        # Persistir
        update_doc = {
            "custom_flow_steps": state["flow_steps"],
            "custom_welcome_message": state["welcome_message"],
            "custom_completion_message": state["completion_message"],
            "custom_appointment_message": state["appointment_message"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by_ai": True,
        }
        await db.bot_config.update_one(
            {"tenant_id": current_user.tenant_id},
            {"$set": update_doc, "$setOnInsert": {"tenant_id": current_user.tenant_id}},
            upsert=True,
        )
        try:
            await db.audit_log.insert_one({
                "tenant_id": current_user.tenant_id,
                "user_email": current_user.email,
                "action": "flow_ai_edit",
                "instruction": instruction,
                "applied_ops": [{"op": o["op"], "params": o["params"]} for o in valid],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"audit_log flow falla: {e}")

        return {"applied": True, "applied_count": len(valid), "invalid": invalid}

    # Pre-check IA antes de rate-limit (con cache de tenant)
    from llm_service import create_llm_for_tenant
    cached_tenant = ttl_cache_get("tenants", current_user.tenant_id)
    if cached_tenant is None:
        cached_tenant = await db.tenants.find_one(
            {"tenant_id": current_user.tenant_id}, {"_id": 0}
        )
        if cached_tenant:
            ttl_cache_set("tenants", current_user.tenant_id, cached_tenant, ttl=_TENANT_CACHE_TTL)
    llm = create_llm_for_tenant(cached_tenant)
    if not llm.client:
        raise HTTPException(
            status_code=503,
            detail="IA no configurada. Configura tu OpenAI Key en Configuracion."
        )

    rate_key = f"flow-ai:{current_user.tenant_id}"
    allowed, remaining = await check_rate_limit(rate_key, _RATE_MAX, _RATE_WINDOW)
    if not allowed:
        retry = await get_retry_after(rate_key, _RATE_WINDOW)
        raise HTTPException(
            status_code=429,
            detail=f"Limite alcanzado ({_RATE_MAX}/hora). Reintentar en {retry}s",
        )

    state = await _load_flow_state(db, current_user)
    # Resumen compacto del estado para el prompt
    state_summary = {
        "welcome_message": state["welcome_message"][:200],
        "completion_message": state["completion_message"][:200],
        "appointment_message": state["appointment_message"][:200],
        "flow_steps": [
            {"id": s.get("id"), "question": s.get("question", "")[:120],
             "type": s.get("type"), "buttons": [b.get("title") for b in s.get("buttons", [])]}
            for s in state["flow_steps"]
        ],
    }
    user_prompt = (
        f"Estado actual del flujo:\n{json.dumps(state_summary, indent=2, ensure_ascii=False)}\n\n"
        f'Instruccion: "{instruction}"\n\n'
        f"Devolve el JSON con operations a aplicar:"
    )

    try:
        raw = await llm.send_message(SYSTEM_PROMPT, user_prompt, max_tokens=900)
    except Exception as e:
        logger.error(f"Error IA flow: {e}")
        raise HTTPException(status_code=502, detail=f"Error IA: {e}")

    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        raise HTTPException(status_code=502, detail="IA devolvio respuesta invalida")
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="IA devolvio JSON malformado")

    valid_ops = []
    invalid_ops = []
    sim_state = state
    # Truncar a _MAX_OPS_PREVIEW como defensa ante respuestas LLM excesivas
    raw_ops = (parsed.get("operations") or [])[:_MAX_OPS_PREVIEW]
    truncated = len(parsed.get("operations") or []) > _MAX_OPS_PREVIEW
    for op in raw_ops:
        err, normalized = _validate_op(op, sim_state["flow_steps"])
        if err:
            invalid_ops.append({"op": (op or {}).get("op"), "reason": err, "params": (op or {}).get("params")})
        else:
            normalized["explanation"] = (op or {}).get("explanation", "")
            valid_ops.append(normalized)
            sim_state = _apply_ops(sim_state, [normalized])

    return {
        "preview": {
            "operations": valid_ops,
            "invalid": invalid_ops,
            "summary": parsed.get("summary", ""),
            "current_step_count": len(state["flow_steps"]),
            "preview_step_count": len(sim_state["flow_steps"]),
            "truncated": truncated,
            "max_ops": _MAX_OPS_PREVIEW,
        },
        "applied": False,
        "rate_limit": {"remaining": remaining, "max": _RATE_MAX, "window_seconds": _RATE_WINDOW},
    }


@router.get("/flow/ai-edit/info")
async def flow_ai_info(current_user: User = Depends(require_admin)):
    return {
        "valid_ops": sorted(_VALID_OPS),
        "rate_limit": {"max": _RATE_MAX, "window_seconds": _RATE_WINDOW},
        "examples": [
            "Agrega un paso para preguntar el barrio donde busca",
            "Cambia el mensaje de bienvenida a: 'Hola! Soy InmoBot, tu asesor virtual'",
            "Eliminar el paso que pregunta por el presupuesto",
            "Agrega botones de Si/No a la pregunta de visita",
            "Mover el paso de email al final del flujo",
        ],
    }
