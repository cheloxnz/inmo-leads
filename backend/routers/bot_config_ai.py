"""Router de Asistente IA para configurar el bot via lenguaje natural.

El admin escribe "configurame el bot para responder de 9 a 18hs"
y la IA modifica los settings reales en la coleccion bot_config.
"""
import json
import re
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import require_admin, get_db
from models import User
from rate_limit import check_rate_limit, get_retry_after

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bot-config-ai"])

# Rate-limit: 10 calls/hora por tenant
_RATE_MAX = 10
_RATE_WINDOW = 3600

# Whitelist alineada al modelo BotConfig real (models.py)
_VALID_DAYS = {"lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"}

_BOT_CONFIG_FIELDS = {
    "business_hours_start": int,
    "business_hours_end": int,
    "business_days": list,
    "saturday_hours_start": int,
    "saturday_hours_end": int,
    "auto_handoff_score": int,
    "warm_lead_reactivation_days": int,
    "appointment_reminder_hours": int,
    "welcome_message": str,
}


SYSTEM_PROMPT = """Sos un asistente que traduce instrucciones de usuario en JSON de configuracion de un bot de WhatsApp.

Devolve SOLO un JSON con esta estructura exacta (sin texto adicional, sin markdown):
{
  "actions": [
    {"field": "nombre_del_campo", "value": <valor>, "explanation": "que cambia en lenguaje natural"}
  ],
  "summary": "resumen breve de los cambios"
}

Campos validos y tipos exactos:
- business_hours_start: integer 0-23 (hora inicio Lun-Vie, ej: 9)
- business_hours_end: integer 0-23 (hora fin Lun-Vie, ej: 18)
- business_days: array de strings con valores de ["lunes","martes","miercoles","jueves","viernes","sabado","domingo"] (sin tildes)
- saturday_hours_start: integer 0-23 (hora inicio sabado)
- saturday_hours_end: integer 0-23 (hora fin sabado)
- auto_handoff_score: integer 1-12 (score minimo para derivar a humano)
- warm_lead_reactivation_days: integer 1-30
- appointment_reminder_hours: integer 1-72 (horas antes de la cita para recordatorio)
- welcome_message: string (mensaje de bienvenida del bot)

Reglas:
- Si el usuario pide algo fuera de estos campos, devolve actions: [] y summary explicando que no podes modificar eso.
- NUNCA inventes campos.
- Escribi en ESPANOL rioplatense (vos, dale, etc).
- Si el usuario menciona "9 a 18", interpretalo como business_hours_start=9 y business_hours_end=18 (Lun-Vie).
- Si menciona "sabados de X a Y", usa saturday_hours_start/end."""


def _validate_action(field: str, value):
    """Devuelve None si valido, o string con razon de invalidez."""
    if field not in _BOT_CONFIG_FIELDS:
        return "campo no permitido"
    expected = _BOT_CONFIG_FIELDS[field]
    # bool es subclase de int en Python; rechazar bools donde esperamos int
    if expected is int and isinstance(value, bool):
        return "tipo incorrecto, esperado int"
    if not isinstance(value, expected):
        return f"tipo incorrecto, esperado {expected.__name__}"

    if field in ("business_hours_start", "business_hours_end",
                 "saturday_hours_start", "saturday_hours_end"):
        if not (0 <= value <= 23):
            return "fuera de rango 0-23"
    elif field == "auto_handoff_score":
        if not (1 <= value <= 12):
            return "fuera de rango 1-12"
    elif field == "warm_lead_reactivation_days":
        if not (1 <= value <= 30):
            return "fuera de rango 1-30"
    elif field == "appointment_reminder_hours":
        if not (1 <= value <= 72):
            return "fuera de rango 1-72"
    elif field == "welcome_message":
        if not (1 <= len(value) <= 1000):
            return "longitud invalida (1-1000 chars)"
    elif field == "business_days":
        if not value:
            return "lista vacia"
        for d in value:
            if not isinstance(d, str) or d.lower() not in _VALID_DAYS:
                return f"dia invalido: {d}"
    return None


@router.post("/bot-config/ai-edit")
async def ai_edit_bot_config(
    body: dict,
    current_user: User = Depends(require_admin),
    db = Depends(get_db),
):
    """Recibe instrucciones en lenguaje natural y modifica bot_config.
    Retorna preview de los cambios; si confirm=true, los aplica."""
    instruction = (body or {}).get("instruction", "").strip()
    confirm = bool((body or {}).get("confirm", False))
    confirmed_actions = (body or {}).get("confirmed_actions")  # opcional: preview ya validado

    if not instruction:
        raise HTTPException(status_code=400, detail="instruction requerido")
    if len(instruction) > 500:
        raise HTTPException(status_code=400, detail="instruction demasiado largo (>500 chars)")

    # Si viene confirmed_actions desde el frontend, NO llamamos al LLM otra vez:
    # re-validamos la whitelist (defense in depth) y aplicamos directo.
    # Esto evita la inconsistencia "el usuario edita el textarea entre preview y apply".
    if confirm and isinstance(confirmed_actions, list) and confirmed_actions:
        valid_actions = []
        invalid = []
        for action in confirmed_actions:
            if not isinstance(action, dict):
                continue
            field = action.get("field")
            value = action.get("value")
            if field == "business_days" and isinstance(value, list):
                value = [d.lower() if isinstance(d, str) else d for d in value]
            reason = _validate_action(field, value)
            if reason:
                invalid.append({"field": field, "value": value, "reason": reason})
                continue
            valid_actions.append({"field": field, "value": value})

        if not valid_actions:
            raise HTTPException(status_code=400, detail="confirmed_actions invalidas")

        update_doc = {a["field"]: a["value"] for a in valid_actions}
        update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_doc["updated_by_ai"] = True
        await db.bot_config.update_one(
            {"tenant_id": current_user.tenant_id},
            {"$set": update_doc, "$setOnInsert": {"tenant_id": current_user.tenant_id}},
            upsert=True,
        )
        try:
            await db.audit_log.insert_one({
                "tenant_id": current_user.tenant_id,
                "user_email": current_user.email,
                "action": "bot_config_ai_edit",
                "instruction": instruction,
                "applied_changes": [
                    {"field": a["field"], "value": a["value"]}
                    for a in valid_actions
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"audit_log insert failed: {e}")

        return {
            "applied": True,
            "applied_fields": [a["field"] for a in valid_actions],
            "invalid": invalid,
        }

    # Pre-check: si IA no esta configurada, retornar 503 ANTES de consumir rate-limit.
    from llm_service import create_llm_for_tenant
    tenant = await db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    llm = create_llm_for_tenant(tenant)
    if not llm.client:
        raise HTTPException(
            status_code=503,
            detail="IA no configurada. Configura tu OpenAI Key en Configuracion."
        )

    # Rate-limit (solo cuando vamos a llamar al LLM)
    rate_key = f"bot-cfg-ai:{current_user.tenant_id}"
    allowed, remaining = await check_rate_limit(rate_key, _RATE_MAX, _RATE_WINDOW)
    if not allowed:
        retry = await get_retry_after(rate_key, _RATE_WINDOW)
        raise HTTPException(
            status_code=429,
            detail=f"Limite alcanzado ({_RATE_MAX}/hora). Reintentar en {retry}s"
        )

    # Cargar config actual (solo campos de whitelist)
    bot_config = await db.bot_config.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    ) or {}
    current_view = {k: v for k, v in bot_config.items() if k in _BOT_CONFIG_FIELDS}

    user_prompt = (
        f"Configuracion actual del bot:\n{json.dumps(current_view, indent=2, ensure_ascii=False)}\n\n"
        f'Instruccion del usuario: "{instruction}"\n\n'
        f"Devolve el JSON con las acciones a aplicar:"
    )

    try:
        response = await llm.send_message(SYSTEM_PROMPT, user_prompt, max_tokens=600)
    except Exception as e:
        logger.error(f"Error llamando IA: {e}")
        raise HTTPException(status_code=502, detail=f"Error IA: {e}")

    # Extraer JSON robustamente (LLM a veces wrappea en markdown)
    cleaned = response.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        logger.warning(f"IA respuesta sin JSON: {response[:200]}")
        raise HTTPException(status_code=502, detail="IA devolvio respuesta invalida")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning(f"JSON parse error: {match.group(0)[:200]}")
        raise HTTPException(status_code=502, detail="IA devolvio JSON malformado")

    # Validar acciones
    valid_actions = []
    invalid = []
    for action in parsed.get("actions", []) or []:
        if not isinstance(action, dict):
            continue
        field = action.get("field")
        value = action.get("value")
        if field == "business_days" and isinstance(value, list):
            value = [d.lower() if isinstance(d, str) else d for d in value]

        reason = _validate_action(field, value)
        if reason:
            invalid.append({"field": field, "value": value, "reason": reason})
            continue
        valid_actions.append({
            "field": field,
            "value": value,
            "explanation": action.get("explanation", ""),
            "previous": current_view.get(field),
        })

    return {
        "preview": {
            "actions": valid_actions,
            "invalid": invalid,
            "summary": parsed.get("summary", ""),
        },
        "applied": False,
        "rate_limit": {
            "remaining": remaining,
            "max": _RATE_MAX,
            "window_seconds": _RATE_WINDOW,
        },
    }


@router.get("/bot-config/ai-edit/info")
async def ai_edit_info(current_user: User = Depends(require_admin)):
    """Devuelve metadata para UI: campos editables, ejemplos, rate-limit."""
    return {
        "editable_fields": list(_BOT_CONFIG_FIELDS.keys()),
        "rate_limit": {"max": _RATE_MAX, "window_seconds": _RATE_WINDOW},
        "examples": [
            "Cambia el horario de atencion a 9 a 19hs de lunes a viernes",
            "Los sabados atendemos de 10 a 13hs",
            "Mensaje de bienvenida: 'Hola! Soy el asistente virtual'",
            "Derivar a humano cuando el score sea 8 o mas",
            "Recordame las citas 12 horas antes",
        ],
    }
