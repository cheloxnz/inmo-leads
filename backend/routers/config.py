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
        "last_check": tenant.get("whatsapp_last_check"),
    }


@router.put("/config/whatsapp")
async def update_whatsapp_config(
    config: dict,
    current_user: User = Depends(require_admin),
):
    """Admin: Actualiza config de WhatsApp del tenant.

    Después de guardar, dispara automáticamente un test de conexión
    contra Meta Graph API y persiste el resultado en
    `tenants.whatsapp_last_check` para que el SuperAdmin pueda ver el
    estado de cada tenant sin tener que abrir la config de cada uno.
    """
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

    # Auto-test de conexión post-save
    test_result = await _run_whatsapp_check(current_user.tenant_id)
    return {
        "message": "Configuracion de WhatsApp actualizada",
        "test": test_result,
    }


async def _run_whatsapp_check(tenant_id: str) -> dict:
    """Ejecuta el check contra Meta Graph API y persiste el resultado
    en `tenants.whatsapp_last_check`. Retorna el resultado para el caller.

    Reusable desde el endpoint manual (`/config/whatsapp/test`) y desde
    el auto-test post-save (PUT `/config/whatsapp`).
    """
    import httpx

    tenant = await _db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tenant:
        return {
            "ok": False,
            "status": "missing_credentials",
            "message": "Tenant no encontrado",
            "details": {},
        }

    phone_id = (tenant.get("whatsapp_phone_number_id") or "").strip()
    token = (tenant.get("whatsapp_access_token") or "").strip()

    if not phone_id or not token:
        result = {
            "ok": False,
            "status": "missing_credentials",
            "message": "Faltan credenciales. Cargá Phone Number ID y Access Token y guardá antes de probar.",
            "details": {},
        }
        await _persist_check_result(tenant_id, result)
        return result

    url = f"https://graph.facebook.com/v18.0/{phone_id}"
    params = {
        "fields": "id,display_phone_number,verified_name,quality_rating,code_verification_status,name_status,messaging_limit_tier",
        "access_token": token,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
    except httpx.TimeoutException:
        result = {
            "ok": False,
            "status": "api_error",
            "message": "Timeout al contactar Meta. Intentá de nuevo en unos segundos.",
            "details": {},
        }
        await _persist_check_result(tenant_id, result)
        return result
    except Exception as e:
        logger.warning(f"[wa_test] network error tenant={tenant_id}: {e}")
        result = {
            "ok": False,
            "status": "api_error",
            "message": "No se pudo contactar a Meta Graph API.",
            "details": {},
        }
        await _persist_check_result(tenant_id, result)
        return result

    # Mapeo de errores
    result = None
    if resp.status_code == 401:
        result = {
            "ok": False,
            "status": "invalid_token",
            "message": "Access Token inválido o expirado. Generá uno nuevo en Meta y volvé a guardar.",
            "details": {},
        }
    elif resp.status_code == 403:
        result = {
            "ok": False,
            "status": "permission_denied",
            "message": "El token no tiene permisos para acceder a este Phone Number ID. Verificá que sean del mismo Business Account.",
            "details": {},
        }
    elif resp.status_code == 404:
        result = {
            "ok": False,
            "status": "not_found",
            "message": "Phone Number ID no existe o no es accesible con este token.",
            "details": {},
        }
    elif resp.status_code == 429:
        result = {
            "ok": False,
            "status": "api_error",
            "message": "Meta rate-limited. Esperá un minuto y volvé a probar.",
            "details": {},
        }
    elif resp.status_code >= 500:
        result = {
            "ok": False,
            "status": "api_error",
            "message": f"Error en Meta ({resp.status_code}). Intentá más tarde.",
            "details": {},
        }
    elif resp.status_code != 200:
        try:
            err_body = resp.json().get("error", {})
            err_msg = err_body.get("message", "")
            err_code = err_body.get("code")
            err_subcode = err_body.get("error_subcode")
        except Exception:
            err_msg = ""
            err_code = None
            err_subcode = None
        if err_code == 190 or "access token" in err_msg.lower() or "oauth" in err_msg.lower():
            result = {
                "ok": False,
                "status": "invalid_token",
                "message": f"Access Token inválido o expirado. Detalle Meta: {err_msg}".strip(),
                "details": {},
            }
        elif err_code == 100 and err_subcode == 33:
            result = {
                "ok": False,
                "status": "not_found",
                "message": "Phone Number ID no existe o no es accesible con este token.",
                "details": {},
            }
        else:
            result = {
                "ok": False,
                "status": "api_error",
                "message": f"Respuesta inesperada de Meta (HTTP {resp.status_code}). {err_msg}".strip(),
                "details": {},
            }

    if result is None:
        # 200 OK
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
        code_ver = (data.get("code_verification_status") or "").upper()
        quality = (data.get("quality_rating") or "").upper()
        name_status = (data.get("name_status") or "").upper()

        # Si Meta nos devolvió quality_rating, el número está conectado y enviando
        # mensajes. El campo code_verification_status puede quedar como EXPIRED en
        # algunos casos (histórico de Meta) aunque el número esté operativo: lo
        # tratamos como warning, no como error bloqueante.
        is_operational = quality in {"GREEN", "YELLOW", "UNKNOWN"} and name_status in {"APPROVED", "AVAILABLE_WITHOUT_REVIEW", ""}

        if code_ver and code_ver != "VERIFIED" and not is_operational:
            result = {
                "ok": False,
                "status": "unverified_number",
                "message": f"El número aún no está verificado (estado: {code_ver}). Completá la verificación SMS/voz en Meta Business Manager antes de enviar mensajes.",
                "details": details,
            }
        elif quality == "RED":
            result = {
                "ok": False,
                "status": "low_quality",
                "message": "El número tiene quality rating ROJO en Meta. Riesgo alto de suspensión. Revisá en Meta Business Manager.",
                "details": details,
            }
        else:
            warning = ""
            if code_ver and code_ver != "VERIFIED":
                # Operativo pero con campo legacy de Meta: aviso suave sin bloquear
                warning = f" ⚠️ Meta reporta code_verification_status={code_ver} (campo histórico, generalmente ignorable si el bot envía mensajes correctamente)."
            result = {
                "ok": True,
                "status": "connected",
                "message": (
                    f"✅ Conectado a Meta. Número {data.get('display_phone_number') or '—'} "
                    f"({data.get('verified_name') or 'sin nombre verificado'}). "
                    f"Quality: {quality or 'desconocida'}.{warning}"
                ),
                "details": details,
            }

    await _persist_check_result(tenant_id, result)
    return result


async def _persist_check_result(tenant_id: str, result: dict) -> None:
    """Guarda el último resultado del WhatsApp test en el tenant para mostrar
    en SuperAdmin sin re-llamar a Meta."""
    try:
        await _db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "whatsapp_last_check": {
                    "ok": result.get("ok", False),
                    "status": result.get("status", "api_error"),
                    "message": result.get("message", ""),
                    "details": result.get("details", {}),
                    "checked_at": datetime.utcnow().isoformat(),
                },
            }},
        )
    except Exception as e:
        logger.warning(f"[wa_test] persist failed tenant={tenant_id}: {e}")


@router.post("/config/whatsapp/test")
async def test_whatsapp_connection(current_user: User = Depends(require_admin)):
    """Admin: prueba la conexión a Meta Graph API con las credenciales
    guardadas del tenant. Hace UN call read-only (no envía mensajes) y
    retorna info útil del número + status de verificación + quality rating.

    Persiste el resultado en `tenants.whatsapp_last_check` para que el
    SuperAdmin pueda ver el estado de cada tenant en su listado.
    """
    return await _run_whatsapp_check(current_user.tenant_id)


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



# ============================================================
# Business Profile (Iter42 - bot fix #4)
# ============================================================

@router.get("/business-profile")
async def get_business_profile(current_user: User = Depends(require_admin)):
    """Admin: trae el profile del negocio para esta cuenta. Si no existe,
    devuelve un dict vacío con el tenant_id (para que el form arranque
    en blanco sin errores)."""
    profile = await _db.business_profiles.find_one(
        {"tenant_id": current_user.tenant_id}, {"_id": 0}
    )
    if not profile:
        return {"tenant_id": current_user.tenant_id, "exists": False}
    profile["exists"] = True
    return profile


@router.put("/business-profile")
async def update_business_profile(
    body: dict,
    current_user: User = Depends(require_admin),
):
    """Admin: upsert del profile. El bot va a usar esta info para responder
    preguntas frecuentes sin inventar datos.

    Validación: tipa el body con Pydantic BusinessProfile (campos opcionales,
    validación de tipos primitivos). Si un campo viene con tipo inválido
    (ej. accepts_cash='texto'), Pydantic lo rechaza con 422.
    """
    from business_profile_service import upsert_business_profile, BusinessProfile

    # Forzar tenant_id desde el JWT (no se acepta del body)
    body_clean = {k: v for k, v in (body or {}).items() if k != "tenant_id"}
    body_clean["tenant_id"] = current_user.tenant_id

    try:
        validated = BusinessProfile(**body_clean)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Datos inválidos: {e}")

    # Sólo persistimos los campos que vinieron en el request (evita pisar
    # con defaults los campos que el form no mandó).
    incoming_keys = set(body_clean.keys()) - {"tenant_id"}
    data = {
        k: getattr(validated, k)
        for k in incoming_keys
        if hasattr(validated, k)
    }

    profile = await upsert_business_profile(_db, current_user.tenant_id, data)
    profile["exists"] = True
    return profile
