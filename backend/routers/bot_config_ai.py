"""Router de Asistente IA para configurar el bot via lenguaje natural.

El admin escribe "configurame el bot para responder solo de 9 a 18hs"
y la IA modifica los settings reales en bot_config / tenant.
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

# Whitelist de campos modificables via IA (subset de bot_config seguro)
_BOT_CONFIG_FIELDS = {
    "business_hours": dict,             # {start: "09:00", end: "18:00", days: [1,2,3,4,5]}
    "fallback_to_human": bool,
    "auto_reply_outside_hours": str,    # mensaje fuera de horario
    "welcome_message": str,
    "confirmation_message": str,
    "closing_message": str,
    "max_consecutive_questions": int,
    "appointment_reminder_hours": int,
    "delay_seconds_between_messages": int,
}


SYSTEM_PROMPT = """Eres un asistente que traduce instrucciones de usuario en JSON de configuracion de bot.

Devuelve SOLO un JSON con esta estructura exacta (sin texto adicional):
{
  "actions": [
    {"field": "nombre_del_campo", "value": <valor>, "explanation": "que cambia en lenguaje natural"}
  ],
  "summary": "resumen breve de los cambios"
}

Campos validos y tipos:
- business_hours: {"start": "HH:MM", "end": "HH:MM", "days": [1=lunes...7=domingo]}
- fallback_to_human: boolean (true=deriva a humano cuando no entiende)
- auto_reply_outside_hours: string (mensaje fuera de horario laboral)
- welcome_message: string
- confirmation_message: string (al confirmar cita)
- closing_message: string (al cerrar conversacion)
- max_consecutive_questions: integer 1-10
- appointment_reminder_hours: integer 1-72 (horas antes de la cita)
- delay_seconds_between_messages: integer 0-10

Si el usuario pide algo fuera de estos campos, responde con actions vacio y summary="No puedo modificar eso desde aqui".
Escribi en ESPANOL rioplatense (vos)."""


@router.post("/bot-config/ai-edit")
async def ai_edit_bot_config(
    body: dict,
    current_user: User = Depends(require_admin),
    db = Depends(get_db),
):
    """Recibe instrucciones en lenguaje natural y modifica bot_config.
    Retorna preview de los cambios; si confirm=true, los aplica."""
    instruction = (body or {}).get("instruction", "").strip()
    confirm = (body or {}).get("confirm", False)

    if not instruction:
        raise HTTPException(status_code=400, detail="instruction requerido")
    if len(instruction) > 500:
        raise HTTPException(status_code=400, detail="instruction demasiado largo (>500 chars)")

    # Rate-limit
    rate_key = f"bot-cfg-ai:{current_user.tenant_id}"
    allowed, remaining = await check_rate_limit(rate_key, _RATE_MAX, _RATE_WINDOW)
    if not allowed:
        retry = await get_retry_after(rate_key, _RATE_WINDOW)
        raise HTTPException(status_code=429, detail=f"Limite alcanzado. Reintentar en {retry}s")

    # Cargar config actual
    bot_config = await db.bot_config.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    ) or {"tenant_id": current_user.tenant_id}

    # Llamar LLM
    from llm_service import create_llm_for_tenant
    tenant = await db.tenants.find_one({"tenant_id": current_user.tenant_id}, {"_id": 0})
    llm = create_llm_for_tenant(tenant)

    if not llm.client:
        raise HTTPException(status_code=503, detail="IA no configurada. Configurá tu OpenAI Key.")

    user_prompt = f"""Configuracion actual:
{json.dumps({k: v for k, v in bot_config.items() if k in _BOT_CONFIG_FIELDS}, indent=2)}

Instruccion del usuario: "{instruction}"

Devolve el JSON con las acciones a aplicar:"""

    try:
        response = await llm._send_message(SYSTEM_PROMPT, user_prompt)
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise HTTPException(status_code=500, detail="IA devolvio respuesta invalida")
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="IA devolvio JSON invalido")
    except Exception as e:
        logger.error(f"Error llamando IA: {e}")
        raise HTTPException(status_code=500, detail=f"Error IA: {e}")

    # Validar acciones contra whitelist
    valid_actions = []
    invalid = []
    for action in parsed.get("actions", []):
        field = action.get("field")
        value = action.get("value")
        if field not in _BOT_CONFIG_FIELDS:
            invalid.append({"field": field, "reason": "campo no permitido"})
            continue
        expected_type = _BOT_CONFIG_FIELDS[field]
        if not isinstance(value, expected_type):
            invalid.append({"field": field, "reason": f"tipo incorrecto, esperado {expected_type.__name__}"})
            continue
        # Validaciones extra
        if field == "max_consecutive_questions" and not (1 <= value <= 10):
            invalid.append({"field": field, "reason": "fuera de rango 1-10"})
            continue
        if field == "appointment_reminder_hours" and not (1 <= value <= 72):
            invalid.append({"field": field, "reason": "fuera de rango 1-72"})
            continue
        if field == "delay_seconds_between_messages" and not (0 <= value <= 10):
            invalid.append({"field": field, "reason": "fuera de rango 0-10"})
            continue
        if field == "business_hours":
            if not all(k in value for k in ("start", "end")):
                invalid.append({"field": field, "reason": "necesita start y end"})
                continue
            if not re.match(r"^\d{2}:\d{2}$", value.get("start", "")) or not re.match(r"^\d{2}:\d{2}$", value.get("end", "")):
                invalid.append({"field": field, "reason": "formato HH:MM"})
                continue
        valid_actions.append(action)

    response_data = {
        "preview": {
            "actions": valid_actions,
            "invalid": invalid,
            "summary": parsed.get("summary", ""),
        },
        "applied": False,
        "rate_limit": {"remaining": remaining, "max": _RATE_MAX, "window_seconds": _RATE_WINDOW}
    }

    # Aplicar cambios solo si confirm=true
    if confirm and valid_actions:
        update_doc = {a["field"]: a["value"] for a in valid_actions}
        update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_doc["updated_by_ai"] = True
        await db.bot_config.update_one(
            {"tenant_id": current_user.tenant_id},
            {"$set": update_doc},
            upsert=True
        )
        # Audit log
        await db.audit_log.insert_one({
            "tenant_id": current_user.tenant_id,
            "user_email": current_user.email,
            "action": "bot_config_ai_edit",
            "instruction": instruction,
            "applied_fields": list(update_doc.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        response_data["applied"] = True
        response_data["applied_fields"] = list(update_doc.keys())

    return response_data
