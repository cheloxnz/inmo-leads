"""Feature Flags por tenant.

Patrón: una sola codebase, distintos flags habilitados por tenant.
- Registry central (FEATURE_FLAGS) define el catálogo de features disponibles.
- get_tenant_features(tenant) devuelve el dict efectivo combinando defaults + overrides.
- has_feature(tenant, name) helper para checks en código.
- SuperAdmin endpoints permiten activar/desactivar via UI.
"""
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase


# Registry: feature_key -> {label, description, category, default}
# Categorías: bot, dashboard, integrations, beta
FEATURE_FLAGS = {
    # --- Beta features (futuras) ---
    "mortgage_calculator": {
        "label": "Calculadora de hipoteca en el bot",
        "description": "Habilita un módulo en el flujo del bot que calcula cuotas de hipoteca con tasa, plazo y monto.",
        "category": "bot",
        "default": False,
    },
    "salesforce_sync": {
        "label": "Sincronización con Salesforce CRM",
        "description": "Cada lead nuevo se replica automáticamente como Contact en Salesforce vía API.",
        "category": "integrations",
        "default": False,
    },
    "advanced_analytics_export": {
        "label": "Export avanzado de métricas",
        "description": "Exportá KPIs a CSV/Excel con filtros custom y rangos personalizados.",
        "category": "dashboard",
        "default": False,
    },
    "custom_webhook_lead_hot": {
        "label": "Webhook custom: lead caliente",
        "description": "POST a una URL externa cuando un lead alcanza score≥7. Configurable por tenant.",
        "category": "integrations",
        "default": False,
    },
    "voice_response_tts": {
        "label": "Respuestas de voz con IA (TTS)",
        "description": "El bot puede responder con audios generados por OpenAI TTS en lugar de texto.",
        "category": "bot",
        "default": False,
    },
    "priority_support": {
        "label": "Soporte prioritario 24/7",
        "description": "Marca al tenant para canal de soporte directo (interno: filtra notificaciones internas).",
        "category": "beta",
        "default": False,
    },
    "white_label": {
        "label": "White label completo",
        "description": "Oculta el branding 'Powered by InmoBot' en landings públicas y emails.",
        "category": "beta",
        "default": False,
    },
    "ai_lead_summary": {
        "label": "Resumen IA del lead",
        "description": "Cada lead tiene un summary auto-generado por GPT con insights y next-step recomendado.",
        "category": "bot",
        "default": False,
    },
}


def get_feature_default(name: str) -> bool:
    f = FEATURE_FLAGS.get(name)
    return bool(f.get("default")) if f else False


def has_feature(tenant: dict, name: str) -> bool:
    """Resuelve si un tenant tiene una feature habilitada.
    Prioridad: override del tenant > default del registry.
    Acepta tenant.features[name] como bool o dict (truthy => habilitado).
    """
    if not tenant or not isinstance(tenant, dict):
        return False
    overrides = tenant.get("features") or {}
    if name in overrides:
        v = overrides[name]
        if isinstance(v, dict):
            return bool(v.get("enabled", False))
        return bool(v)
    return get_feature_default(name)


def get_tenant_features(tenant: dict) -> dict:
    """Retorna un dict {feature_key: bool} con el estado efectivo de todas las features
    del registry para este tenant."""
    overrides = (tenant or {}).get("features") or {}
    out = {}
    for key, meta in FEATURE_FLAGS.items():
        if key in overrides:
            v = overrides[key]
            out[key] = bool(v.get("enabled", False) if isinstance(v, dict) else v)
        else:
            out[key] = bool(meta.get("default", False))
    return out


async def update_tenant_feature(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    feature_name: str,
    enabled: bool,
    config: Optional[dict] = None,
) -> bool:
    """Actualiza un único flag. Si config es dict, persiste {enabled, ...config}."""
    if feature_name not in FEATURE_FLAGS:
        return False
    if config:
        value = {"enabled": enabled, **config}
    else:
        value = enabled
    res = await db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {f"features.{feature_name}": value}},
    )
    return res.matched_count > 0
