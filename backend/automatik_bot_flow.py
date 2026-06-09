"""
automatik_bot_flow.py
=====================
Flujo de calificación B2B para el tenant "automatik-media".

Cuando alguien escribe al número de WhatsApp desde un ad de Meta Ads,
el bot hace 8 preguntas para calificar si es un prospecto válido para
la Suite IA de Automatik Media (InmoGen + InmoBot + InmoDesk).

Scoring:
  HOT  >= 11  → link Cal.com + notificación Slack + dashboard
  WARM >= 6   → link Cal.com + notificación Slack + dashboard
  COLD < 6    → botón "Hablar con asesor" (handoff manual) + notificación Slack (para que Marcelo tome control)

Estados del flujo (reutiliza FlowStage existente):
  WELCOME         → bienvenida
  NAME            → captura nombre
  INTENT          → tipo de negocio (almacena en metadata.automatik_answers.biz_type)
  ZONE            → tamaño del equipo (almacena en metadata.automatik_answers.team_size)
  BUDGET          → leads por mes (almacena en metadata.automatik_answers.monthly_leads)
  PROPERTY_TYPE   → cierres por mes (almacena en metadata.automatik_answers.monthly_closes)
  MUST_HAVE       → herramientas actuales (almacena en metadata.automatik_answers.current_tools)
  URGENCY         → inversión en ads (almacena en metadata.automatik_answers.ads_invest)
  APPOINTMENT_OFFER / COMPLETED → score calculado, respuesta enviada

Notificaciones:
  - Slack webhook (configurado en .env como SLACK_WEBHOOK_URL)
  - Dashboard WebSocket: notif en tiempo real al SuperAdmin conectado
"""

import logging
import re
import httpx
import os
from datetime import datetime
from models import FlowStage, LeadStatus

logger = logging.getLogger(__name__)

CAL_COM_LINK = "https://cal.com/marcelo-del-valle-bcgavl/30min"
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")

PLAN_SUGGESTIONS = {
    "hot":  "Scale ($1,997/mes) o Enterprise ($3,997/mes)",
    "warm": "Pro ($997/mes) — InmoGen + InmoBot + Meta Ads",
    "cold": "Starter ($497/mes) para empezar",
}


class AutomatikBotFlow:
    """Gestiona el flujo de calificación B2B de Automatik Media."""

    def __init__(self, wa_service, db):
        self.wa = wa_service
        self.db = db

    # ──────────────────────────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────────────────────────

    async def process(self, lead, message_text: str):
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

        elif stage == FlowStage.APPOINTMENT_OFFER:
            await self._handle_main_problem(lead, message_text)

        elif stage in (FlowStage.HANDOFF, FlowStage.CONSULTING):
            # Lead en handoff — Marcelo ya está hablando con él
            self.wa.send_text_message(
                lead.phone,
                f"Hola {lead.name or ''}! 👋 Marcelo ya está al tanto de tu consulta "
                f"y se va a comunicar muy pronto. ¡Gracias por tu paciencia! 🙌",
            )

        elif stage in (FlowStage.COMPLETED, FlowStage.CONFIRMATION):
            self.wa.send_text_message(
                lead.phone,
                f"Hola {lead.name or ''}! 👋 Si necesitás algo más, escribinos. "
                f"¿Querés agendar una llamada? {CAL_COM_LINK} 🚀",
            )

        elif stage == FlowStage.DISQUALIFIED:
            # Puede que el lead frío quiera retomar — re-ofrecer hablar con asesor
            buttons = [
                {"type": "reply", "reply": {"id": "ak_hablar_asesor", "title": "📞 Hablar con asesor"}},
                {"type": "reply", "reply": {"id": "ak_mas_info", "title": "📖 Más información"}},
            ]
            self.wa.send_interactive_buttons(
                lead.phone,
                "¡Hola de nuevo! 👋 Si querés explorar cómo automatizar tu negocio, "
                "puedo conectarte con un asesor.",
                buttons,
            )

        else:
            lead.flow_stage = FlowStage.WELCOME
            await self._handle_welcome(lead, message_text)

    # ──────────────────────────────────────────────────────────────────
    # Step handlers
    # ──────────────────────────────────────────────────────────────────

    async def _handle_welcome(self, lead, message: str):
        response = (
            "¡Hola! 👋 Vi que te interesó la *Suite IA de Automatik Media*.\n\n"
            "Antes de mostrarte cómo funciona, quiero entender tu negocio "
            "para ver qué tanto impacto podés tener. Son solo 6 preguntas, "
            "te lleva 2 minutos.\n\n"
            "¿Empezamos?"
        )
        buttons = [
            {"type": "reply", "reply": {"id": "am_start", "title": "Sí, empecemos 🚀"}},
            {"type": "reply", "reply": {"id": "am_info",  "title": "Primero quiero info"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.NAME

    async def _handle_name(self, lead, message: str):
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
            return

        name = message.strip()
        if len(name) < 2 or not any(c.isalpha() for c in name):
            self.wa.send_text_message(
                lead.phone,
                "No pude reconocer ese nombre. ¿Podés decirme tu nombre y apellido?\n\nEjemplo: Juan García",
            )
            return

        # Limpiar prefijos como "si," "sí," "me llamo" antes de capitalizar
        import re as _re
        name_clean = _re.sub(r"^(si[,.]?\s*|sí[,.]?\s*|me llamo\s*|soy\s*)", "", name, flags=_re.IGNORECASE).strip()
        if len(name_clean) < 2:
            name_clean = name  # fallback si quedó vacío
        lead.name = " ".join(w.capitalize() for w in name_clean.split())
        first = lead.name.split()[0].rstrip(",.")
        response = f"¡Buenísimo, {first}! 😊\n\n¿Cómo describirías tu negocio?"
        # Lista (soporta 4+ opciones, botones tienen máx 3)
        sections = [{
            "title": "Tipo de negocio",
            "rows": [
                {"id": "biz_inmo",   "title": "🏢 Inmobiliaria",   "description": "Inmobiliaria propia con cartera"},
                {"id": "biz_asesor", "title": "👤 Asesor",          "description": "Asesor o broker independiente"},
                {"id": "biz_dev",    "title": "🏗️ Desarrolladora",  "description": "Empresa de desarrollo inmobiliario"},
                {"id": "biz_otro",   "title": "✏️ Otro",             "description": "Contame brevemente qué hacés"},
            ],
        }]
        self.wa.send_list_message(lead.phone, response, "Ver opciones", sections)
        lead.flow_stage = FlowStage.INTENT

    async def _handle_biz_type(self, lead, message: str):
        msg = message.lower()

        # Si eligió "Otro" y aún no tenemos la descripción libre, pedirla
        if "biz_otro" in msg:
            self.wa.send_text_message(
                lead.phone,
                "¡Genial! Contame en pocas palabras a qué se dedica tu negocio. 📝\n\n"
                "Ej: *\"Agencia de alquileres temporarios\"* o *\"Franquicia de RE/MAX\"*",
            )
            # Guardamos que está esperando la descripción libre
            meta = lead.metadata or {}
            meta["_awaiting_biz_description"] = True
            lead.metadata = meta
            return

        # Si viene la descripción libre (no es una opción del menú)
        meta = lead.metadata or {}
        if meta.get("_awaiting_biz_description"):
            # Guardar la descripción textual como biz_type
            self._set_answer(lead, "biz_type", f"otro: {message.strip()[:80]}")
            meta.pop("_awaiting_biz_description", None)
            lead.metadata = meta
        else:
            biz = ("inmobiliaria" if "biz_inmo" in msg or "inmobiliaria" in msg
                   else "desarrolladora" if "biz_dev" in msg or "desarrolladora" in msg or "desarrollo" in msg
                   else "asesor")
            self._set_answer(lead, "biz_type", biz)

        # Lista para tamaño de equipo (4 opciones → usa list_message)
        sections = [{
            "title": "Tamaño del equipo",
            "rows": [
                {"id": "team_solo", "title": "Solo yo",         "description": "Trabajo de manera independiente"},
                {"id": "team_2_5",  "title": "2 a 5 personas",  "description": "Equipo pequeño"},
                {"id": "team_6_15", "title": "6 a 15 personas", "description": "Equipo mediano"},
                {"id": "team_mas",  "title": "Más de 15",       "description": "Empresa grande"},
            ],
        }]
        self.wa.send_list_message(
            lead.phone,
            "¿Cuántas personas hay en tu equipo? (asesores + administración)",
            "Ver opciones",
            sections,
        )
        lead.flow_stage = FlowStage.ZONE

    async def _handle_team_size(self, lead, message: str):
        msg = message.lower()
        if   "team_solo" in msg or "solo" in msg: team = "solo_yo"
        elif "team_2_5"  in msg or "2" in msg:    team = "2_5"
        elif "team_6_15" in msg or "6" in msg:    team = "6_15"
        else:                                      team = "mas_15"
        self._set_answer(lead, "team_size", team)

        first = lead.name.split()[0] if lead.name else ""
        self.wa.send_text_message(
            lead.phone,
            f"Perfecto {first}. ¿Cuántos leads nuevos recibís por mes aproximadamente?\n"
            f"(de redes, portales, boca a boca, etc.)\n\n"
            f"Podés poner un número aproximado, ej: *50* o *200*",
        )
        lead.flow_stage = FlowStage.BUDGET

    async def _handle_monthly_leads(self, lead, message: str):
        numbers = re.findall(r"\d+", message)
        monthly_leads = int(numbers[0]) if numbers else 0
        self._set_answer(lead, "monthly_leads", monthly_leads)

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
        self._set_answer(lead, "monthly_closes", closes)

        response = "¿Usás actualmente alguna herramienta digital para gestionar tus leads o clientes?"
        buttons = [
            {"type": "reply", "reply": {"id": "tools_si",     "title": "✅ Sí, tengo CRM"}},
            {"type": "reply", "reply": {"id": "tools_basico", "title": "📋 Algo básico"}},
            {"type": "reply", "reply": {"id": "tools_no",     "title": "❌ No uso nada"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.MUST_HAVE

    async def _handle_tools(self, lead, message: str):
        msg = message.lower()
        tools = ("tiene_crm" if "tools_si" in msg or ("si" in msg and "tools" not in msg and "no" not in msg)
                 else "basico" if "tools_basico" in msg or "básico" in msg or "hoja" in msg
                 else "nada")
        self._set_answer(lead, "current_tools", tools)

        response = "¿Invertís hoy en publicidad digital? (Meta Ads, Google, portales inmobiliarios)"
        buttons = [
            {"type": "reply", "reply": {"id": "ads_si",     "title": "💰 Sí, invierto"}},
            {"type": "reply", "reply": {"id": "ads_quiero", "title": "🚀 Quiero empezar"}},
            {"type": "reply", "reply": {"id": "ads_no",     "title": "❌ No por ahora"}},
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.URGENCY

    async def _handle_ads_invest(self, lead, message: str):
        msg = message.lower()
        ads = ("invierte"       if "ads_si" in msg or ("invierto" in msg)
               else "quiere_empezar" if "ads_quiero" in msg or "quiero" in msg or "empezar" in msg
               else "no")
        self._set_answer(lead, "ads_invest", ads)

        # Última pregunta: mayor problema del negocio
        first = lead.name.split()[0] if lead.name else ""
        self.wa.send_text_message(
            lead.phone,
            f"Última pregunta, {first} 🙌\n\n"
            f"¿Cuál es el *mayor problema* que tenés hoy en tu negocio?\n\n"
            f"Por ejemplo: _\"mis leads no tienen seguimiento\"_, "
            f"_\"no tengo presencia en redes\"_, _\"pierdo mucho tiempo cargando datos\"_...\n\n"
            f"Contame en tus palabras 👇",
        )
        lead.flow_stage = FlowStage.APPOINTMENT_OFFER

    async def _handle_main_problem(self, lead, message: str):
        """Recibe el texto libre del mayor problema → analiza con LLM → guarda tags."""
        problem_text = message.strip()
        self._set_answer(lead, "main_problem", problem_text)

        # Analizar con LLM para extraer tags de problema y oportunidades
        tags, opportunities = await self._analyze_problem(problem_text)
        self._set_answer(lead, "problem_tags", tags)
        self._set_answer(lead, "opportunities", opportunities)

        # Marcar timestamp del scoring
        meta = lead.metadata or {}
        meta["scored_at"] = datetime.utcnow().isoformat()
        lead.metadata = meta

        answers = (lead.metadata or {}).get("automatik_answers", {})
        score, status = self._score(answers)
        lead.score = score
        lead.status = status

        status_str = status.value if hasattr(status, "value") else str(status)

        if status_str in ("hot", "warm"):
            await self._respond_qualified(lead, score, status_str, answers)
        else:
            await self._respond_cold(lead, score, answers)

        lead.flow_stage = FlowStage.COMPLETED

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    async def _analyze_problem(self, problem_text: str):
        """Usa GPT-4o-mini para extraer tags de problema y oportunidades comerciales."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

            system_prompt = (
                "Sos un analista de ventas B2B para una empresa de herramientas IA para el sector inmobiliario. "
                "Las herramientas que vendemos son:\n"
                "- 🤖 InmoBot: bot de WhatsApp que califica leads 24/7 + dashboard de gestión de leads\n"
                "- 🎨 InmoGen: generador IA de creativos para Meta Ads en 2 minutos\n"
                "- 📊 InmoDesk: sistema de búsqueda y prospección de leads B2B\n\n"
                "Dado el texto del prospecto, devolvé un JSON con:\n"
                "{\n"
                "  \"problem_tags\": [lista de 2 a 5 etiquetas cortas del problema, máx 4 palabras cada una],\n"
                "  \"opportunities\": [lista de 1 a 3 herramientas/soluciones concretas que le servirían, máx 6 palabras cada una]\n"
                "}\n\n"
                "Ejemplos de problem_tags: \"Sin seguimiento de leads\", \"Carga manual de datos\", "
                "\"Sin presencia en redes\", \"Publicidad ineficiente\", \"Sin CRM\", \"Sin web\", "
                "\"Respuesta lenta a consultas\", \"No automatiza WhatsApp\"\n\n"
                "Ejemplos de opportunities: \"InmoBot para seguimiento automático\", "
                "\"InmoGen para creativos de ads\", \"InmoDesk como CRM central\"\n\n"
                "Respondé SOLO el JSON, sin explicaciones."
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"El prospecto dijo: \"{problem_text}\""},
                ],
                temperature=0.3,
                max_tokens=300,
            )

            import json
            raw = response.choices[0].message.content.strip()
            # Limpiar posibles bloques ```json
            raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
            data = json.loads(raw)
            tags = data.get("problem_tags", [])[:5]
            opportunities = data.get("opportunities", [])[:3]
            logger.info(f"[automatik] Problem analysis: tags={tags}, opp={opportunities}")
            return tags, opportunities

        except Exception as e:
            logger.warning(f"[automatik] Problem analysis failed: {e}")
            # Fallback: guardar texto crudo sin tags
            return [], []

    def _set_answer(self, lead, key: str, value):
        meta = lead.metadata or {}
        answers = meta.get("automatik_answers", {})
        answers[key] = value
        meta["automatik_answers"] = answers
        lead.metadata = meta

    # ──────────────────────────────────────────────────────────────────
    # Scoring
    # ──────────────────────────────────────────────────────────────────

    def _score(self, answers: dict):
        score = 0
        biz = answers.get("biz_type", "asesor")
        biz_key = biz if biz in ("inmobiliaria", "desarrolladora", "asesor") else "otro"
        score += {"inmobiliaria": 3, "desarrolladora": 2, "asesor": 1, "otro": 2}.get(biz_key, 1)

        team = answers.get("team_size", "solo_yo")
        score += {"solo_yo": 0, "2_5": 2, "6_15": 3, "mas_15": 4}.get(team, 0)

        leads = answers.get("monthly_leads", 0)
        score += 3 if leads >= 100 else 2 if leads >= 20 else 1 if leads >= 5 else 0

        closes = answers.get("monthly_closes", 0)
        score += 2 if closes >= 5 else 1 if closes >= 1 else 0

        tools = answers.get("current_tools", "nada")
        score += {"nada": 3, "basico": 2, "tiene_crm": 1}.get(tools, 1)

        ads = answers.get("ads_invest", "no")
        score += {"invierte": 3, "quiere_empezar": 2, "no": 0}.get(ads, 0)

        if score >= 11:
            return score, LeadStatus.HOT
        elif score >= 6:
            return score, LeadStatus.WARM
        else:
            return score, LeadStatus.COLD

    # ──────────────────────────────────────────────────────────────────
    # Respuestas finales
    # ──────────────────────────────────────────────────────────────────

    async def _respond_qualified(self, lead, score: int, status_str: str, answers: dict):
        """HOT o WARM → Cal.com + Slack + dashboard notification."""
        first = lead.name.split()[0] if lead.name else ""
        biz_label = {"inmobiliaria": "inmobiliaria", "desarrolladora": "desarrolladora", "asesor": "negocio"}.get(
            answers.get("biz_type", "asesor"), "negocio"
        )
        plan_sugg = PLAN_SUGGESTIONS.get(status_str, "")

        # Mensaje al lead
        msg = (
            f"¡Excelente, {first}! 🔥\n\n"
            f"En base a lo que me contaste, hay una oportunidad concreta para "
            f"automatizar tu {biz_label} con IA.\n\n"
            f"El siguiente paso es una llamada de 30 minutos con Marcelo (fundador de Automatik Media) "
            f"para ver exactamente qué herramientas se adaptan a tu situación.\n\n"
            f"👉 *Reservá tu llamada aquí:*\n{CAL_COM_LINK}\n\n"
            f"¡Sin compromiso! 🙌"
        )
        self.wa.send_text_message(lead.phone, msg)

        # Notificar a Slack
        await self._notify_slack(lead, score, status_str, answers)

        # Notificar en el dashboard (WebSocket)
        await self._notify_dashboard(lead, score, status_str)

    async def _respond_cold(self, lead, score: int, answers: dict):
        """COLD → botón "Hablar con asesor" + Slack para que Marcelo decida si lo toma."""
        first = lead.name.split()[0] if lead.name else ""

        # Mensaje con botón de contacto
        buttons = [
            {"type": "reply", "reply": {"id": "ak_hablar_asesor", "title": "📞 Hablar con asesor"}},
            {"type": "reply", "reply": {"id": "ak_mas_info",      "title": "🌐 Ver automatik-media.com"}},
        ]
        self.wa.send_interactive_buttons(
            lead.phone,
            f"¡Gracias por tu tiempo, {first}! 🙏\n\n"
            f"Por el momento quizás el suite completo no es lo que necesitás, "
            f"pero si querés hablar con un asesor para ver si hay algo que te pueda servir, "
            f"tocá el botón. 👇",
            buttons,
        )

        # Notificar a Slack (con menor urgencia)
        await self._notify_slack(lead, score, "cold", answers)

        # Notificar en dashboard también (para que aparezca el lead)
        await self._notify_dashboard(lead, score, "cold")

        # Poner el lead en estado HANDOFF para que Marcelo pueda tomar control
        lead.flow_stage = FlowStage.HANDOFF

    # ──────────────────────────────────────────────────────────────────
    # Notificaciones
    # ──────────────────────────────────────────────────────────────────

    async def _notify_slack(self, lead, score: int, status_str: str, answers: dict):
        """Envía notificación al canal Slack de Automatik Media."""
        emoji = {"hot": "🔥", "warm": "🌡️", "cold": "❄️"}.get(status_str, "📋")
        biz_raw = answers.get('biz_type', '')
        biz_labels_map = {"inmobiliaria": "Inmobiliaria propia", "desarrolladora": "Desarrolladora", "asesor": "Asesor independiente"}
        biz_labels = {k: v for k, v in biz_labels_map.items()}
        # Si es "otro: descripción", mostrar la descripción directamente
        if biz_raw.startswith("otro:"):
            biz_labels[biz_raw] = f"Otro — {biz_raw[5:].strip()}"
        team_labels  = {"solo_yo": "Solo él/ella", "2_5": "2-5 personas", "6_15": "6-15 personas", "mas_15": "Más de 15"}
        tools_labels = {"tiene_crm": "Usa CRM/herramientas", "basico": "Algo básico", "nada": "No usa nada"}
        ads_labels   = {"invierte": "Ya invierte en ads", "quiere_empezar": "Quiere empezar", "no": "No invierte"}

        action_text = (
            "✅ *Ya se le envió el link de Cal.com para agendar.*"
            if status_str in ("hot", "warm")
            else "⚠️ *Lead frío — se le ofreció el botón de hablar con asesor. Revisalo en el dashboard.*"
        )

        # Tags del problema y oportunidades
        problem_tags = answers.get("problem_tags", [])
        opportunities = answers.get("opportunities", [])
        main_problem = answers.get("main_problem", "")
        problem_block = []
        if main_problem:
            problem_block.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*💬 Problema:*\n_{main_problem}_"},
            })
        if problem_tags:
            tags_str = "  ".join(f"`{t}`" for t in problem_tags)
            problem_block.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🏷️ Tags detectados:*\n{tags_str}"},
            })
        if opportunities:
            opp_str = "\n".join(f"• {o}" for o in opportunities)
            problem_block.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🎯 Oportunidades:*\n{opp_str}"},
            })

        payload = {
            "text": f"{emoji} *Nuevo lead Automatik Media — {status_str.upper()}*",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{emoji} Nuevo lead — {status_str.upper()} (Score: {score}/18)"},
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Nombre:*\n{lead.name or 'Sin nombre'}"},
                        {"type": "mrkdwn", "text": f"*Teléfono:*\n+{lead.phone}"},
                        {"type": "mrkdwn", "text": f"*Negocio:*\n{biz_labels.get(answers.get('biz_type',''), '-')}"},
                        {"type": "mrkdwn", "text": f"*Equipo:*\n{team_labels.get(answers.get('team_size',''), '-')}"},
                        {"type": "mrkdwn", "text": f"*Leads/mes:*\n{answers.get('monthly_leads', '-')}"},
                        {"type": "mrkdwn", "text": f"*Cierres/mes:*\n{answers.get('monthly_closes', '-')}"},
                        {"type": "mrkdwn", "text": f"*Herramientas:*\n{tools_labels.get(answers.get('current_tools',''), '-')}"},
                        {"type": "mrkdwn", "text": f"*Ads:*\n{ads_labels.get(answers.get('ads_invest',''), '-')}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": action_text},
                },
                *problem_block,
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "📊 Ver en Dashboard"},
                            "url": f"https://www.inmobot-ia.com/superadmin/leads",
                            "style": "primary",
                        }
                    ],
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(SLACK_WEBHOOK, json=payload)
            logger.info(f"[automatik] Slack notificado para lead {lead.phone}")
        except Exception as e:
            logger.warning(f"[automatik] Slack notification failed: {e}")

    async def _notify_dashboard(self, lead, score: int, status_str: str):
        """Envía notificación en tiempo real al dashboard via WebSocket."""
        try:
            # Importar el connection_manager global del server
            from server import connection_manager
            emoji = {"hot": "🔥", "warm": "🌡️", "cold": "❄️"}.get(status_str, "📋")
            notification = {
                "type": "new_lead",
                "title": f"{emoji} Nuevo lead Automatik — {status_str.upper()}",
                "message": f"{lead.name or 'Nuevo prospecto'} completó el formulario (score: {score}/18)",
                "lead_phone": lead.phone,
                "status": status_str,
                "score": score,
                "timestamp": datetime.utcnow().isoformat(),
                "link": "/superadmin/leads",
            }
            # Enviar a todos los admins conectados (SuperAdmin incluido)
            await connection_manager.send_to_admins(notification)
        except Exception as e:
            logger.warning(f"[automatik] Dashboard notification failed: {e}")
