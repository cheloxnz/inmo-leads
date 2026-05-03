"""
Business Profile Service
========================

Datos del negocio que el bot puede usar para responder preguntas como:
"¿Hacen envíos?", "¿Qué medios de pago aceptan?", "¿Atienden los domingos?",
"¿Tienen estacionamiento?", "¿Cuál es la dirección?", etc.

Centraliza un perfil del negocio por tenant, con campos opcionales que el
admin completa desde Configuración. El bot inyecta este contexto en el
system prompt del LLM para evitar respuestas inventadas (alucinación).

Si un campo no está definido, el bot dirá honestamente "no tengo esa info,
te conecto con un humano" en lugar de inventar.
"""
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


# Campos que se pueden completar (todos opcionales, todos string excepto faq)
class BusinessProfile(BaseModel):
    tenant_id: str

    # Identidad
    business_name: Optional[str] = None
    business_description: Optional[str] = None  # 1-2 frases
    industry: Optional[str] = None  # texto libre, ej: "panadería artesanal"

    # Ubicación y contacto
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None

    # Horarios (texto libre, ej: "Lun-Vie 9-18, Sáb 10-14, Dom cerrado")
    business_hours: Optional[str] = None

    # Operación
    accepts_cash: bool = False
    accepts_credit_card: bool = False
    accepts_debit_card: bool = False
    accepts_transfer: bool = False
    accepts_crypto: bool = False
    accepts_mercadopago: bool = False
    payment_notes: Optional[str] = None  # "3 cuotas sin interés", etc.

    # Delivery / pickup / atención presencial
    offers_delivery: bool = False
    delivery_zones: Optional[str] = None  # "CABA y GBA Norte"
    delivery_cost: Optional[str] = None  # "$500 fijo" o "Gratis sobre $5000"
    offers_pickup: bool = False
    offers_in_person: bool = False
    has_parking: bool = False

    # Políticas
    return_policy: Optional[str] = None  # "Cambios dentro de 30 días con ticket"
    warranty_policy: Optional[str] = None
    appointment_required: bool = False  # ¿Necesita cita previa?

    # FAQ libre: lista de {pregunta, respuesta} para casos específicos del negocio
    custom_faqs: List[dict] = Field(default_factory=list)

    # Cosas que NO ofrece (importante para evitar promesas falsas)
    not_offered: Optional[str] = None  # ej: "No hacemos envíos al exterior"

    # Tono del bot (config opcional para vertical-aware)
    bot_tone: Optional[str] = None  # "casual" | "formal" | "vendedor" | "neutro"

    updated_at: Optional[str] = None


def build_business_context_text(profile: dict) -> str:
    """Convierte un BusinessProfile dict a texto plano que se inyecta en el
    system prompt del LLM. Sólo incluye los campos que están seteados.

    El LLM recibe esto como "INFORMACIÓN VERIFICADA DEL NEGOCIO" y se le
    instruye explícitamente a NO inventar datos no listados.
    """
    if not profile:
        return ""
    lines = []
    p = profile

    # Identidad
    if p.get("business_name"):
        lines.append(f"- Nombre: {p['business_name']}")
    if p.get("business_description"):
        lines.append(f"- Descripción: {p['business_description']}")
    if p.get("industry"):
        lines.append(f"- Rubro: {p['industry']}")

    # Contacto
    if p.get("address"):
        addr = p["address"]
        if p.get("city"):
            addr += f", {p['city']}"
        lines.append(f"- Dirección: {addr}")
    if p.get("phone"):
        lines.append(f"- Teléfono: {p['phone']}")
    if p.get("email"):
        lines.append(f"- Email: {p['email']}")
    if p.get("website"):
        lines.append(f"- Web: {p['website']}")
    if p.get("google_maps_url"):
        lines.append(f"- Maps: {p['google_maps_url']}")

    # Horarios
    if p.get("business_hours"):
        lines.append(f"- Horarios: {p['business_hours']}")

    # Pagos
    payments = []
    if p.get("accepts_cash"):
        payments.append("efectivo")
    if p.get("accepts_credit_card"):
        payments.append("tarjeta de crédito")
    if p.get("accepts_debit_card"):
        payments.append("tarjeta de débito")
    if p.get("accepts_transfer"):
        payments.append("transferencia")
    if p.get("accepts_mercadopago"):
        payments.append("Mercado Pago")
    if p.get("accepts_crypto"):
        payments.append("crypto")
    if payments:
        lines.append(f"- Medios de pago: {', '.join(payments)}")
    if p.get("payment_notes"):
        lines.append(f"- Notas de pago: {p['payment_notes']}")

    # Delivery / pickup
    fulfilment = []
    if p.get("offers_delivery"):
        d = "delivery"
        if p.get("delivery_zones"):
            d += f" ({p['delivery_zones']})"
        if p.get("delivery_cost"):
            d += f" — {p['delivery_cost']}"
        fulfilment.append(d)
    if p.get("offers_pickup"):
        fulfilment.append("retiro en local")
    if p.get("offers_in_person"):
        fulfilment.append("atención presencial")
    if fulfilment:
        lines.append(f"- Modalidades: {', '.join(fulfilment)}")
    if p.get("has_parking"):
        lines.append("- Tiene estacionamiento")
    if p.get("appointment_required"):
        lines.append("- Atención con cita previa")

    # Políticas
    if p.get("return_policy"):
        lines.append(f"- Política de cambios/devoluciones: {p['return_policy']}")
    if p.get("warranty_policy"):
        lines.append(f"- Garantía: {p['warranty_policy']}")

    # NOT offered (importante)
    if p.get("not_offered"):
        lines.append(f"- IMPORTANTE - NO ofrecemos: {p['not_offered']}")

    # Custom FAQs
    if p.get("custom_faqs"):
        lines.append("- Preguntas frecuentes específicas:")
        for faq in p["custom_faqs"][:10]:
            q = faq.get("question", "").strip()
            a = faq.get("answer", "").strip()
            if q and a:
                lines.append(f"  • Q: {q}")
                lines.append(f"    A: {a}")

    if not lines:
        return ""

    return (
        "\n=== INFORMACIÓN VERIFICADA DEL NEGOCIO ===\n"
        + "\n".join(lines)
        + "\n=== FIN INFO NEGOCIO ===\n"
        "\nREGLAS DE USO:\n"
        "1. Si la respuesta a una pregunta del cliente está en esta info, usala.\n"
        "2. Si NO está, decí honestamente: 'No tengo esa info exacta, "
        "pero te conecto con un humano que puede ayudarte'. NO INVENTES datos.\n"
        "3. Si pregunta por algo listado en 'NO ofrecemos', sé claro y no prometas eso.\n"
    )


async def get_business_context(db, tenant_id: str) -> str:
    """Helper que carga el profile y devuelve el texto listo para inyectar."""
    if not tenant_id:
        return ""
    profile = await db.business_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    return build_business_context_text(profile) if profile else ""


async def upsert_business_profile(db, tenant_id: str, data: dict) -> dict:
    """Crea o actualiza el profile. Retorna el doc actualizado."""
    update = {k: v for k, v in data.items() if k != "tenant_id"}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.business_profiles.update_one(
        {"tenant_id": tenant_id},
        {"$set": update, "$setOnInsert": {"tenant_id": tenant_id}},
        upsert=True,
    )
    return await db.business_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
