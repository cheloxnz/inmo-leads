"""
automatik_bot_flow.py
=====================
Flujo de calificación B2B para el tenant "automatik-media".

Cuando alguien escribe al número de WhatsApp desde un ad de Meta Ads,
el bot hace 8 preguntas para calificar si es un prospecto válido para
la Suite IA de Automatik Media (InmoGen + InmoBot + InmoDesk).

Scoring:
  HOT  >= 11 → link Cal.com + notificación WhatsApp a Marcelo
  WARM  >= 6  → link Cal.com + notificación WhatsApp a Marcelo
  COLD  < 6   → mensaje de nurturing, sin notificación

Estados del flujo (reutiliza FlowStage existente):
  WELCOME         → bienvenida
  NAME            → captura nombre
  INTENT          → tipo de negocio (almacena en metadata.biz_type)
  ZONE            → tamaño del equipo (almacena en metadata.team_size)
  BUDGET          → leads por mes (almacena en metadata.monthly_leads)
  PROPERTY_TYPE   → cierres por mes (almacena en metadata.monthly_closes)
  MUST_HAVE       → herramientas actuales (almacena en metadata.tools)
  URGENCY         → inversión en ads (almacena en metadata.ads_invest)
  APPOINTMENT_OFFER → scoring + respuesta final

Todos los datos se guardan en lead.metadata['automatik_answers'] para
que el dashboard SuperAdmin los muestre en el drawer del lead.
"""

import logging
import re
from datetime import datetime
from models import FlowStage, LeadStatus

logger = logging.getLogger(__name__)

# WhatsApp de Marcelo (asesor que recibe notificaciones)
ADVISOR_PHONE = "5491153250877"
CAL_COM_LINK = "https://cal.com/marcelo-del-valle-bcgavl/30min"

PLAN_SUGGESTIONS = {
    "hot": "Scale ($1,997/mes) o Enterprise ($3,997/mes)",
    "warm": "Pro ($997/mes) — InmoGen + InmoBot + Meta Ads",
    "cold": "Starter ($497/mes) para empezar",
}


class AutomatikBotFlow:
    """Gestiona el flujo de calificación B2B de Automatik Media."""

    def __init__(self, wa_service, db):
        self.wa = wa_service
        self.db = db

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def process(self, lead, message_text: str):
        """
        Procesa un mensaje entrante para el tenant automatik-media.
        Se llama desde BotFlowManager.process_message cuando
        lead.tenant_id == 'automatik-media'.
        """
        stage = lead.flow_stage

        if stage == FlowStage.WELCOME or not stage:
            await self._handle_welcome(lead, message_text)

        elif stage == FlowStage.NAME:
            await self._handle_name(lead, message_text)

        elif stage == FlowStage.INTENT:
            await self._handle_biz_type(lead, message_text)

        elif stage == FlowStage.ZONE:
            await self._handle_team_size(lead, message_text)

        elif stage == FlowStage.BUDGET:
            await self._handle_monthly_leads(lead, message_text)

        elif stage == FlowStage.PROPERTY_TYPE:
            await self._handle_monthly_closes(lead, message_text)

        elif stage == FlowStage.MUST_HAVE:
            await self._handle_tools(lead, message_text)

        elif stage == FlowStage.URGENCY:
            await self._handle_ads_invest(lead, message_text)

        elif stage in (FlowStage.COMPLETED, FlowStage.HANDOFF, FlowStage.CONFIRMATION):
            # Lead ya calificado — responder brevemente
            self.wa.send_text_message(
                lead.phone,
                f"Hola {lead.name or ''}! 👋 Ya tenés una reunión coordinada. "
                f"Si necesitás algo más, escribinos. 🙌",
            )

        elif stage == FlowStage.DISQUALIFIED:
            self.wa.send_text_message(
                lead.phone,
                "Hola de nuevo! 👋 Si en algún momento querés explorar cómo "
                "automatizar tu inmobiliaria, escribinos y con gusto te asesoramos. 🚀",
            )

        else:
            # Fallback: reiniciar
            lead.flow_stage = FlowStage.WELCOME
            await self._handle_welcome(lead, message_text)

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    async def _handle_welcome(self, lead, message: str):
        response = (
            "¡Hola! 👋 Soy el asistente de *Automatik Media*.\n\n"
            "Voy a hacerte unas preguntas rápidas para entender tu situación "
            "y ver cómo podemos ayudarte a hacer crecer tu inmobiliaria con IA. "
            "Solo toma 2 minutitos. ¿Empezamos?"
        )
        buttons = [
            {"type": "reply", "reply": {"id": "am_start", "title": "¡Sí, empecemos! 🚀"}},
            {"type": "reply", "reply": {"id": "am_info", "title": "Primero quiero info"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.NAME

    async def _handle_name(self, lead, message: str):
        # Si viene del botón de "quiero info" → dar mini-pitch y pedir nombre igual
        if "am_info" in message.lower():
            self.wa.send_text_message(
                lead.phone,
                "¡Claro! 🔥\n\n"
                "*Automatik Media* ofrece una suite de 3 herramientas IA para inmobiliarias:\n\n"
                "🎨 *InmoGen* — Creativos para Meta Ads en 2 minutos\n"
                "🤖 *InmoBot* — Bot WhatsApp que califica leads 24/7\n"
                "📊 *InmoDesk* — Prospección B2B automatizada\n\n"
                "Planes desde $497/mes. Ahora sí, ¿me decís tu nombre?",
            )
            lead.flow_stage = FlowStage.NAME
            return

        name = message.strip()
        only_digits = name.replace(" ", "").isdigit()
        too_short = len(name) < 2
        only_symbols = not any(c.isalpha() for c in name)

        if too_short or only_digits or only_symbols:
            self.wa.send_text_message(
                lead.phone,
                "No pude reconocer ese nombre. ¿Podés decirme tu nombre y apellido?\n\nEjemplo: Juan García",
            )
            return

        lead.name = " ".join(w.capitalize() for w in name.split())

        response = f"¡Buenísimo, {lead.name.split()[0]}! 😊\n\n¿Cómo describirías tu negocio?"
        buttons = [
            {"type": "reply", "reply": {"id": "biz_inmo", "title": "🏢 Inmobiliaria propia"}},
            {"type": "reply", "reply": {"id": "biz_asesor", "title": "👤 Asesor independiente"}},
            {"type": "reply", "reply": {"id": "biz_dev", "title": "🏗️ Desarrolladora"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.INTENT

    async def _handle_biz_type(self, lead, message: str):
        msg = message.lower()
        if "biz_inmo" in msg or "inmobiliaria" in msg:
            biz = "inmobiliaria"
        elif "biz_dev" in msg or "desarrolladora" in msg or "desarrollo" in msg:
            biz = "desarrolladora"
        else:
            biz = "asesor"

        meta = lead.metadata or {}
        answers = meta.get("automatik_answers", {})
        answers["biz_type"] = biz
        meta["automatik_answers"] = answers
        lead.metadata = meta

        response = "¿Cuántas personas hay en tu equipo? (asesores + administración)"
        buttons = [
            {"type": "reply", "reply": {"id": "team_solo", "title": "Solo yo"}},
            {"type": "reply", "reply": {"id": "team_2_5", "title": "2 a 5 personas"}},
            {"type": "reply", "reply": {"id": "team_6_15", "title": "6 a 15 personas"}},
            {"type": "reply", "reply": {"id": "team_mas", "title": "Más de 15"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.ZONE

    async def _handle_team_size(self, lead, message: str):
        msg = message.lower()
        if "team_solo" in msg or "solo" in msg:
            team = "solo_yo"
        elif "team_2_5" in msg or "2" in msg:
            team = "2_5"
        elif "team_6_15" in msg or "6" in msg:
            team = "6_15"
        elif "team_mas" in msg or "15" in msg or "mas" in msg:
            team = "mas_15"
        else:
            team = "2_5"

        meta = lead.metadata or {}
        answers = meta.get("automatik_answers", {})
        answers["team_size"] = team
        meta["automatik_answers"] = answers
        lead.metadata = meta

        first_name = lead.name.split()[0] if lead.name else ""
        self.wa.send_text_message(
            lead.phone,
            f"Perfecto {first_name}. ¿Cuántos leads nuevos recibís por mes "
            f"aproximadamente? (de redes, portales, boca a boca, etc.)\n\n"
            f"Podés poner un número aproximado, ej: *50* o *200*",
        )
        lead.flow_stage = FlowStage.BUDGET

    async def _handle_monthly_leads(self, lead, message: str):
        numbers = re.findall(r"\d+", message)
        monthly_leads = int(numbers[0]) if numbers else 0

        meta = lead.metadata or {}
        answers = meta.get("automatik_answers", {})
        answers["monthly_leads"] = monthly_leads
        meta["automatik_answers"] = answers
        lead.metadata = meta

        self.wa.send_text_message(
            lead.phone,
            f"Entendido, {monthly_leads} leads por mes. 📊\n\n"
            f"Y de esos, ¿cuántos terminan en una operación cerrada por mes?\n\n"
            f"Ej: *5* o *20*",
        )
        lead.flow_stage = FlowStage.PROPERTY_TYPE

    async def _handle_monthly_closes(self, lead, message: str):
        numbers = re.findall(r"\d+", message)
        closes = int(numbers[0]) if numbers else 0

        meta = lead.metadata or {}
        answers = meta.get("automatik_answers", {})
        answers["monthly_closes"] = closes
        meta["automatik_answers"] = answers
        lead.metadata = meta

        response = "¿Usás actualmente alguna herramienta digital para gestionar tus leads o clientes?"
        buttons = [
            {"type": "reply", "reply": {"id": "tools_si", "title": "✅ Sí, tengo CRM/herramientas"}},
            {"type": "reply", "reply": {"id": "tools_basico", "title": "📋 Algo básico (hojas, notas)"}},
            {"type": "reply", "reply": {"id": "tools_no", "title": "❌ No, nada todavía"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.MUST_HAVE

    async def _handle_tools(self, lead, message: str):
        msg = message.lower()
        if "tools_si" in msg or "crm" in msg or "sí" in msg or "si" in msg:
            tools = "tiene_crm"
        elif "tools_basico" in msg or "básico" in msg or "hoja" in msg:
            tools = "basico"
        else:
            tools = "nada"

        meta = lead.metadata or {}
        answers = meta.get("automatik_answers", {})
        answers["current_tools"] = tools
        meta["automatik_answers"] = answers
        lead.metadata = meta

        response = "¿Invertís hoy en publicidad digital? (Meta Ads, Google, portales inmobiliarios)"
        buttons = [
            {"type": "reply", "reply": {"id": "ads_si", "title": "💰 Sí, invierto"}},
            {"type": "reply", "reply": {"id": "ads_quiero", "title": "🚀 Quiero empezar"}},
            {"type": "reply", "reply": {"id": "ads_no", "title": "❌ No por ahora"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.URGENCY

    async def _handle_ads_invest(self, lead, message: str):
        msg = message.lower()
        if "ads_si" in msg or "invierto" in msg:
            ads = "invierte"
        elif "ads_quiero" in msg or "quiero" in msg or "empezar" in msg:
            ads = "quiere_empezar"
        else:
            ads = "no"

        meta = lead.metadata or {}
        answers = meta.get("automatik_answers", {})
        answers["ads_invest"] = ads
        meta["automatik_answers"] = answers
        meta["scored_at"] = datetime.utcnow().isoformat()
        lead.metadata = meta

        # Calcular score
        score, status = self._score(answers)
        lead.score = score
        lead.status = status

        if status in (LeadStatus.HOT, LeadStatus.WARM):
            await self._respond_qualified(lead, score, status, answers)
        else:
            await self._respond_cold(lead)

        lead.flow_stage = FlowStage.COMPLETED

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score(self, answers: dict):
        score = 0

        # Tipo de negocio
        biz = answers.get("biz_type", "asesor")
        if biz == "inmobiliaria":
            score += 3
        elif biz == "desarrolladora":
            score += 2
        else:
            score += 1

        # Tamaño del equipo
        team = answers.get("team_size", "solo_yo")
        team_pts = {"solo_yo": 0, "2_5": 2, "6_15": 3, "mas_15": 4}
        score += team_pts.get(team, 0)

        # Leads mensuales
        leads = answers.get("monthly_leads", 0)
        if leads >= 100:
            score += 3
        elif leads >= 20:
            score += 2
        elif leads >= 5:
            score += 1

        # Cierres mensuales
        closes = answers.get("monthly_closes", 0)
        if closes >= 5:
            score += 2
        elif closes >= 1:
            score += 1

        # Herramientas actuales (sin herramientas = más oportunidad de venta)
        tools = answers.get("current_tools", "nada")
        if tools == "nada":
            score += 3
        elif tools == "basico":
            score += 2
        else:
            score += 1

        # Inversión en ads
        ads = answers.get("ads_invest", "no")
        if ads == "invierte":
            score += 3
        elif ads == "quiere_empezar":
            score += 2

        # Clasificar
        if score >= 11:
            return score, LeadStatus.HOT
        elif score >= 6:
            return score, LeadStatus.WARM
        else:
            return score, LeadStatus.COLD

    # ------------------------------------------------------------------
    # Respuestas finales
    # ------------------------------------------------------------------

    async def _respond_qualified(self, lead, score: int, status, answers: dict):
        """Lead calificado: HOT o WARM → enviar Cal.com + notificar a Marcelo."""
        first = lead.name.split()[0] if lead.name else ""
        biz_label = {
            "inmobiliaria": "inmobiliaria",
            "desarrolladora": "desarrolladora",
            "asesor": "negocio",
        }.get(answers.get("biz_type", "asesor"), "negocio")

        # Determinar plan sugerido
        plan_sugg = PLAN_SUGGESTIONS.get(status.value if hasattr(status, "value") else str(status), "")

        msg = (
            f"¡Excelente, {first}! 🔥\n\n"
            f"En base a lo que me contaste, creo que hay una oportunidad "
            f"muy concreta para automatizar tu {biz_label} con IA.\n\n"
            f"El siguiente paso es una llamada de 30 minutos con Marcelo "
            f"(fundador de Automatik Media) para ver exactamente qué herramientas "
            f"se adaptan a tu situación.\n\n"
            f"👉 *Reservá tu llamada aquí:*\n{CAL_COM_LINK}\n\n"
            f"¡Sin compromiso! 🙌"
        )
        self.wa.send_text_message(lead.phone, msg)

        # Notificar a Marcelo
        await self._notify_advisor(lead, score, status, answers)

    async def _respond_cold(self, lead):
        """Lead frío → mensaje de nurturing."""
        first = lead.name.split()[0] if lead.name else ""
        self.wa.send_text_message(
            lead.phone,
            f"¡Gracias por tu tiempo, {first}! 🙏\n\n"
            f"Por el momento capaz que el suite completo no es lo que necesitás, "
            f"pero te dejamos el link a nuestra web para que conozcas las herramientas:\n\n"
            f"🌐 https://automatik-media.com\n\n"
            f"Si en algún momento querés escalar tu inmobiliaria con IA, "
            f"escribinos y con gusto te asesoramos. ¡Éxitos! 🚀",
        )

    async def _notify_advisor(self, lead, score: int, status, answers: dict):
        """Envía notificación por WhatsApp a Marcelo con el resumen del lead."""
        biz_labels = {
            "inmobiliaria": "Inmobiliaria propia",
            "desarrolladora": "Desarrolladora",
            "asesor": "Asesor independiente",
        }
        team_labels = {
            "solo_yo": "Solo él/ella",
            "2_5": "2-5 personas",
            "6_15": "6-15 personas",
            "mas_15": "Más de 15",
        }
        tools_labels = {
            "tiene_crm": "Sí, usa CRM/herramientas",
            "basico": "Algo básico (hojas/notas)",
            "nada": "No usa nada",
        }
        ads_labels = {
            "invierte": "Ya invierte en ads",
            "quiere_empezar": "Quiere empezar a invertir",
            "no": "No invierte",
        }

        status_emoji = "🔥" if (status.value if hasattr(status, "value") else str(status)) == "hot" else "🌡️"

        summary = (
            f"{status_emoji} *Nuevo lead calificado — Automatik Media*\n\n"
            f"👤 Nombre: {lead.name or 'Sin nombre'}\n"
            f"📱 Teléfono: +{lead.phone}\n"
            f"🏢 Negocio: {biz_labels.get(answers.get('biz_type', ''), '-')}\n"
            f"👥 Equipo: {team_labels.get(answers.get('team_size', ''), '-')}\n"
            f"📊 Leads/mes: {answers.get('monthly_leads', '-')}\n"
            f"✅ Cierres/mes: {answers.get('monthly_closes', '-')}\n"
            f"🛠️ Herramientas: {tools_labels.get(answers.get('current_tools', ''), '-')}\n"
            f"💰 Ads: {ads_labels.get(answers.get('ads_invest', ''), '-')}\n"
            f"⭐ Score: {score}/18\n\n"
            f"👉 Ya se le envió el link de Cal.com para agendar."
        )

        try:
            self.wa.send_text_message(ADVISOR_PHONE, summary)
            logger.info(f"[automatik] Notificación enviada a asesor {ADVISOR_PHONE}")
        except Exception as e:
            logger.warning(f"[automatik] No se pudo notificar al asesor: {e}")
