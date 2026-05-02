"""Router de configuración del tenant: bot config, WhatsApp, IA, flujos."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from auth_routes import get_current_user, require_admin, get_db, tenant_filter
from models import BotConfig, User

router = APIRouter(tags=["config"])
logger = logging.getLogger(__name__)
_db = get_db()


# ============================================
# Bot Config (general)
# ============================================

@router.get("/config")
async def get_config(current_user: User = Depends(get_current_user)):
    """Obtiene configuración del bot (por tenant)"""
    tf = tenant_filter(current_user)
    config = await _db.bot_config.find_one(tf, {"_id": 0})
    if not config:
        config = BotConfig(tenant_id=current_user.tenant_id).model_dump()
        config["updated_at"] = config["updated_at"].isoformat()
        await _db.bot_config.insert_one(config)
    return config


@router.put("/config")
async def update_config(config: BotConfig, current_user: User = Depends(require_admin)):
    """Actualiza configuración del bot (por tenant)"""
    config_dict = config.model_dump()
    config_dict["tenant_id"] = current_user.tenant_id
    config_dict["updated_at"] = datetime.utcnow().isoformat()
    await _db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": config_dict},
        upsert=True,
    )
    return {"message": "Configuración actualizada"}


# ============================================
# WhatsApp Config (per tenant)
# ============================================

@router.get("/config/whatsapp")
async def get_whatsapp_config(current_user: User = Depends(require_admin)):
    """Admin: Obtiene config de WhatsApp del tenant"""
    import os
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {
        "whatsapp_phone_number_id": tenant.get("whatsapp_phone_number_id", ""),
        "whatsapp_access_token": (
            "***" + tenant.get("whatsapp_access_token", "")[-10:]
            if tenant.get("whatsapp_access_token") else ""
        ),
        "whatsapp_business_account_id": tenant.get("whatsapp_business_account_id", ""),
        "webhook_verify_token": tenant.get("webhook_verify_token", ""),
        "webhook_url": f"{os.getenv('REACT_APP_BACKEND_URL', '')}/api/webhook",
        "configured": bool(
            tenant.get("whatsapp_access_token") and tenant.get("whatsapp_phone_number_id")
        ),
    }


@router.put("/config/whatsapp")
async def update_whatsapp_config(
    config: dict,
    current_user: User = Depends(require_admin),
):
    """Admin: Actualiza config de WhatsApp del tenant"""
    update_fields = {}
    allowed = [
        "whatsapp_phone_number_id",
        "whatsapp_access_token",
        "whatsapp_business_account_id",
        "webhook_verify_token",
    ]
    for key in allowed:
        if key in config:
            update_fields[key] = config[key]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    update_fields["updated_at"] = datetime.utcnow().isoformat()
    await _db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update_fields},
    )
    return {"message": "Configuracion de WhatsApp actualizada"}


@router.post("/config/whatsapp/test")
async def test_whatsapp_connection(current_user: User = Depends(require_admin)):
    """Admin: prueba la conexión a Meta Graph API con las credenciales
    guardadas del tenant. Hace UN call read-only (no envía mensajes) y
    retorna info útil del número + status de verificación + quality rating.

    Response shape:
      {
        "ok": bool,
        "status": "connected" | "invalid_token" | "not_found" | "permission_denied"
                 | "unverified_number" | "low_quality" | "missing_credentials" | "api_error",
        "message": str,
        "details": {phone_number, verified_name, quality_rating, code_verification_status, ...}
      }
    """
    import httpx

    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    phone_id = tenant.get("whatsapp_phone_number_id", "").strip()
    token = tenant.get("whatsapp_access_token", "").strip()

    if not phone_id or not token:
        return {
            "ok": False,
            "status": "missing_credentials",
            "message": "Faltan credenciales. Cargá Phone Number ID y Access Token y guardá antes de probar.",
            "details": {},
        }

    # Read-only call a Graph API: fetch info del phone number con campos diagnósticos
    url = f"https://graph.facebook.com/v18.0/{phone_id}"
    params = {
        "fields": "id,display_phone_number,verified_name,quality_rating,code_verification_status,name_status,messaging_limit_tier",
        "access_token": token,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
    except httpx.TimeoutException:
        return {
            "ok": False,
            "status": "api_error",
            "message": "Timeout al contactar Meta. Intentá de nuevo en unos segundos.",
            "details": {},
        }
    except Exception as e:
        logger.warning(f"[wa_test] network error tenant={current_user.tenant_id}: {e}")
        return {
            "ok": False,
            "status": "api_error",
            "message": "No se pudo contactar a Meta Graph API.",
            "details": {},
        }

    # Mapeo de errores
    if resp.status_code == 401:
        return {
            "ok": False,
            "status": "invalid_token",
            "message": "Access Token inválido o expirado. Generá uno nuevo en Meta y volvé a guardar.",
            "details": {},
        }
    if resp.status_code == 403:
        return {
            "ok": False,
            "status": "permission_denied",
            "message": "El token no tiene permisos para acceder a este Phone Number ID. Verificá que sean del mismo Business Account.",
            "details": {},
        }
    if resp.status_code == 404:
        return {
            "ok": False,
            "status": "not_found",
            "message": "Phone Number ID no existe o no es accesible con este token.",
            "details": {},
        }
    if resp.status_code == 429:
        return {
            "ok": False,
            "status": "api_error",
            "message": "Meta rate-limited. Esperá un minuto y volvé a probar.",
            "details": {},
        }
    if resp.status_code >= 500:
        return {
            "ok": False,
            "status": "api_error",
            "message": f"Error en Meta ({resp.status_code}). Intentá más tarde.",
            "details": {},
        }
    if resp.status_code != 200:
        # Captura mensaje de error si viene en el body
        try:
            err_body = resp.json().get("error", {})
            err_msg = err_body.get("message", "")
            err_code = err_body.get("code")
            err_subcode = err_body.get("error_subcode")
        except Exception:
            err_msg = ""
            err_code = None
            err_subcode = None
        # Meta a veces devuelve 400 con error code 190 (token inválido) en lugar de 401
        if err_code == 190 or "access token" in err_msg.lower() or "oauth" in err_msg.lower():
            return {
                "ok": False,
                "status": "invalid_token",
                "message": f"Access Token inválido o expirado. Detalle Meta: {err_msg}".strip(),
                "details": {},
            }
        # Code 100 con subcode 33 → object no existe
        if err_code == 100 and err_subcode == 33:
            return {
                "ok": False,
                "status": "not_found",
                "message": "Phone Number ID no existe o no es accesible con este token.",
                "details": {},
            }
        return {
            "ok": False,
            "status": "api_error",
            "message": f"Respuesta inesperada de Meta (HTTP {resp.status_code}). {err_msg}".strip(),
            "details": {},
        }

    data = resp.json()
    details = {
        "phone_number_id": data.get("id"),
        "display_phone_number": data.get("display_phone_number"),
        "verified_name": data.get("verified_name"),
        "quality_rating": data.get("quality_rating"),
        "code_verification_status": data.get("code_verification_status"),
        "name_status": data.get("name_status"),
        "messaging_limit_tier": data.get("messaging_limit_tier"),
    }

    # Reglas de negocio: mostrar warnings si algo no está OK
    code_ver = (data.get("code_verification_status") or "").upper()
    quality = (data.get("quality_rating") or "").upper()

    if code_ver and code_ver != "VERIFIED":
        return {
            "ok": False,
            "status": "unverified_number",
            "message": f"El número aún no está verificado (estado: {code_ver}). Completá la verificación SMS/voz en Meta Business Manager antes de enviar mensajes.",
            "details": details,
        }
    if quality == "RED":
        return {
            "ok": False,
            "status": "low_quality",
            "message": "El número tiene quality rating ROJO en Meta. Riesgo alto de suspensión. Revisá en Meta Business Manager.",
            "details": details,
        }

    return {
        "ok": True,
        "status": "connected",
        "message": (
            f"✅ Conectado a Meta. Número {data.get('display_phone_number') or '—'} "
            f"({data.get('verified_name') or 'sin nombre verificado'}). "
            f"Quality: {quality or 'desconocida'}."
        ),
        "details": details,
    }


# ============================================
# AI Config (per tenant)
# ============================================

@router.get("/config/ai")
async def get_ai_config(current_user: User = Depends(require_admin)):
    """Admin: Obtiene config de IA del tenant"""
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {
        "has_own_key": bool(tenant.get("openai_api_key")),
        "key_preview": (
            "***" + tenant.get("openai_api_key", "")[-8:]
            if tenant.get("openai_api_key") else ""
        ),
        "max_ai_messages": tenant.get("max_ai_messages", 2000),
        "model": "gpt-4o",
    }


@router.put("/config/ai")
async def update_ai_config(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Configura key propia de OpenAI (opcional)"""
    update = {}
    if "openai_api_key" in body:
        update["openai_api_key"] = body["openai_api_key"]
    if not update:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    update["updated_at"] = datetime.utcnow().isoformat()
    await _db.tenants.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update},
    )
    return {"message": "Configuracion de IA actualizada"}


# ============================================
# Custom Flow Builder
# ============================================

@router.get("/flow/config")
async def get_flow_config(current_user: User = Depends(get_current_user)):
    """Obtiene la config del flujo del tenant (custom o template base)"""
    from flow_templates import get_template
    tenant = await _db.tenants.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    template_id = tenant.get("template_id", "servicios") if tenant else "servicios"
    base_template = get_template(template_id)
    config = await _db.bot_config.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    return {
        "template_id": template_id,
        "template_name": base_template.get("name", ""),
        "is_customized": bool(config and config.get("custom_flow_steps")),
        "welcome_message": (config or {}).get("custom_welcome_message")
            or base_template.get("welcome_message", ""),
        "welcome_buttons": (config or {}).get("custom_welcome_buttons")
            or base_template.get("welcome_buttons", []),
        "flow_steps": (config or {}).get("custom_flow_steps")
            or base_template.get("flow_steps", []),
        "scoring": (config or {}).get("custom_scoring")
            or base_template.get("scoring", {}),
        "appointment_message": (config or {}).get("custom_appointment_message")
            or base_template.get("appointment_message", ""),
        "appointment_buttons": (config or {}).get("custom_appointment_buttons")
            or base_template.get("appointment_buttons", []),
        "completion_message": (config or {}).get("custom_completion_message")
            or base_template.get("completion_message", ""),
        "faq": (config or {}).get("custom_faq") or base_template.get("faq", {}),
        "labels": (config or {}).get("custom_labels") or base_template.get("labels", {}),
    }


@router.put("/flow/config")
async def update_flow_config(body: dict, current_user: User = Depends(require_admin)):
    """Admin: Guarda config custom del flujo"""
    update = {"tenant_id": current_user.tenant_id}
    fields_map = {
        "welcome_message": "custom_welcome_message",
        "welcome_buttons": "custom_welcome_buttons",
        "flow_steps": "custom_flow_steps",
        "scoring": "custom_scoring",
        "appointment_message": "custom_appointment_message",
        "appointment_buttons": "custom_appointment_buttons",
        "completion_message": "custom_completion_message",
        "faq": "custom_faq",
        "labels": "custom_labels",
    }
    for key, db_key in fields_map.items():
        if key in body:
            update[db_key] = body[key]
    update["updated_at"] = datetime.utcnow().isoformat()
    await _db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$set": update},
        upsert=True,
    )
    return {"message": "Flujo actualizado"}


@router.post("/flow/reset")
async def reset_flow_config(current_user: User = Depends(require_admin)):
    """Admin: Resetea el flujo custom al template base"""
    custom_fields = [
        "custom_flow_steps", "custom_welcome_message", "custom_welcome_buttons",
        "custom_scoring", "custom_appointment_message", "custom_appointment_buttons",
        "custom_completion_message", "custom_faq", "custom_labels",
    ]
    unset = {f: "" for f in custom_fields}
    await _db.bot_config.update_one(
        {"tenant_id": current_user.tenant_id},
        {"$unset": unset},
    )
    return {"message": "Flujo reseteado al template base"}
