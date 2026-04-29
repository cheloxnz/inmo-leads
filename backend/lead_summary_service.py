"""AI Lead Summary service.

Genera un resumen IA del lead a partir de su historial de conversación:
- Una línea narrativa de qué busca el lead
- Urgencia 1-10
- Próximo paso recomendado para el agente
- Insights clave (preferencias, objeciones, señales de compra)

Gateado por feature flag `ai_lead_summary`. Resultado cacheado en
`leads.ai_summary` con TTL de 7 días (re-genera si la conversación cambia).
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from llm_service import create_llm_for_tenant

logger = logging.getLogger(__name__)

SUMMARY_TTL_DAYS = 7
MAX_HISTORY_TURNS = 30  # últimos N turnos para no explotar tokens


SYSTEM_PROMPT = """Sos un asistente experto en ventas que analiza conversaciones de WhatsApp \
entre un negocio y un lead potencial. Tu tarea es generar un resumen ejecutivo en JSON \
exactamente con este shape:

{
  "narrative": "Una sola línea (max 140 chars) describiendo qué busca el lead.",
  "urgency": 1-10,
  "urgency_reason": "Razón breve del scoring de urgencia (max 80 chars)",
  "next_step": "Acción concreta y específica que el agente debe tomar AHORA (max 100 chars)",
  "insights": ["3-5 bullets cortos con: preferencias detectadas, objeciones, señales de compra, datos relevantes"],
  "buying_signals": ["Frases textuales del lead que indican intención de compra (vacío si no hay)"]
}

Reglas:
- TODO en español rioplatense, tono profesional pero cercano.
- Urgencia 9-10: pide cerrar/agendar/comprar YA. Urgencia 6-8: muestra interés concreto. Urgencia 3-5: explora. Urgencia 1-2: tibio o frío.
- next_step debe ser accionable (ej: "Mandale los 3 PHs en Palermo bajo USD 200k vía WhatsApp"), nunca genérico.
- Si la conversación es vacía o no hay info útil, urgency=1 y next_step="Hacer primera pregunta de calificación".
- Devolvé SOLO JSON válido, sin markdown ni texto adicional."""


def _format_history(history: list, lead_name: str = "") -> str:
    """Convierte conversation_history en texto plano legible para el LLM."""
    if not history:
        return "(sin conversación previa)"
    turns = history[-MAX_HISTORY_TURNS:]
    lines = []
    for t in turns:
        role = t.get("role") or t.get("from") or "unknown"
        content = (t.get("content") or t.get("text") or t.get("message") or "").strip()
        if not content:
            continue
        if role in ("user", "lead", "client"):
            speaker = lead_name or "Lead"
        else:
            speaker = "Bot"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines) if lines else "(sin mensajes con contenido)"


def _is_summary_fresh(lead: dict) -> bool:
    """¿El summary cacheado sigue siendo válido (no expirado y conversación no creció)?"""
    cached = lead.get("ai_summary")
    if not cached or not isinstance(cached, dict):
        return False
    generated_at_str = cached.get("generated_at")
    if not generated_at_str:
        return False
    try:
        generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
    except Exception:
        return False
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - generated_at > timedelta(days=SUMMARY_TTL_DAYS):
        return False
    # Si el largo de la conversación cambió desde la generación, invalidar
    history_len_at_gen = cached.get("history_len_at_gen", 0)
    current_len = len(lead.get("conversation_history") or [])
    if current_len != history_len_at_gen:
        return False
    return True


async def generate_lead_summary(
    db,
    tenant_id: str,
    lead_phone: str,
    force: bool = False,
) -> Optional[dict]:
    """Genera (o devuelve cache) el resumen IA del lead.

    Returns dict con shape: {
      narrative, urgency, urgency_reason, next_step, insights[], buying_signals[],
      generated_at, history_len_at_gen, cached
    } o None si no se pudo generar.
    """
    lead = await db.leads.find_one(
        {"tenant_id": tenant_id, "phone": lead_phone},
        {"_id": 0},
    )
    if not lead:
        return None

    if not force and _is_summary_fresh(lead):
        cached = dict(lead["ai_summary"])
        cached["cached"] = True
        return cached

    tenant = await db.tenants.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "openai_api_key": 1},
    )
    llm = create_llm_for_tenant(tenant)
    if not llm.enabled:
        logger.warning(f"LLM no disponible para tenant {tenant_id}")
        return None

    history_text = _format_history(
        lead.get("conversation_history") or [],
        lead_name=lead.get("name") or lead.get("nombre") or "",
    )
    user_msg = (
        f"Lead: {lead.get('name') or lead.get('nombre') or 'sin nombre'} "
        f"({lead.get('phone')})\n"
        f"Status actual: {lead.get('status', 'unknown')}\n"
        f"Score: {lead.get('score', 0)}/12\n\n"
        f"Conversación:\n{history_text}\n\n"
        f"Generá el JSON del resumen."
    )

    try:
        raw = await llm.send_message(SYSTEM_PROMPT, user_msg, max_tokens=600)
        # El modelo a veces envuelve en ```json ... ```
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip().rstrip("`").strip()
        parsed = json.loads(cleaned)
    except Exception as e:
        logger.error(f"AI summary parse failed para {lead_phone}: {e}")
        return None

    # Sanitizar shape
    out = {
        "narrative": str(parsed.get("narrative", ""))[:200],
        "urgency": max(1, min(10, int(parsed.get("urgency", 1) or 1))),
        "urgency_reason": str(parsed.get("urgency_reason", ""))[:120],
        "next_step": str(parsed.get("next_step", ""))[:160],
        "insights": [str(x)[:200] for x in (parsed.get("insights") or [])][:6],
        "buying_signals": [str(x)[:200] for x in (parsed.get("buying_signals") or [])][:5],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history_len_at_gen": len(lead.get("conversation_history") or []),
    }

    # Persistir en mongo
    await db.leads.update_one(
        {"tenant_id": tenant_id, "phone": lead_phone},
        {"$set": {"ai_summary": out}},
    )
    out["cached"] = False
    return out
