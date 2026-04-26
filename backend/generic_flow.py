"""
InmoBot SaaS - Motor de flujo genérico basado en templates
Procesa mensajes según el template del tenant.
"""
import logging
from datetime import datetime, timedelta
from flow_templates import get_template
from scoring import calculate_score
import re

logger = logging.getLogger(__name__)

URGENCY_KEYWORDS = [
    "urgente", "urgencia", "urgentemente", "necesito ya",
    "lo antes posible", "cuanto antes", "hoy mismo",
    "ahora mismo", "inmediato", "inmediatamente",
    "es para hoy", "muy urgente", "super urgente"
]


class GenericFlowEngine:
    """Motor de flujo genérico que lee templates"""

    def __init__(self, wa_service, llm_service, email_service):
        self.wa = wa_service
        self.llm = llm_service
        self.email = email_service

    def detect_urgency(self, message: str) -> bool:
        message_lower = message.lower()
        return any(kw in message_lower for kw in URGENCY_KEYWORDS)

    async def get_tenant_template(self, tenant_id: str, db) -> dict:
        """Obtiene el template del tenant. Prioridad: custom flow en DB > template base"""
        tenant = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if not tenant:
            return get_template("servicios")

        template_id = tenant.get("template_id", "servicios")
        template = get_template(template_id).copy()

        # Check if tenant has custom flow in bot_config
        config = await db.bot_config.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if config:
            # Override with custom flow steps if defined
            if config.get("custom_flow_steps"):
                template["flow_steps"] = config["custom_flow_steps"]
            if config.get("custom_welcome_message"):
                template["welcome_message"] = config["custom_welcome_message"]
            if config.get("custom_welcome_buttons"):
                template["welcome_buttons"] = config["custom_welcome_buttons"]
            if config.get("custom_scoring"):
                template["scoring"] = config["custom_scoring"]
            if config.get("custom_appointment_message"):
                template["appointment_message"] = config["custom_appointment_message"]
            if config.get("custom_appointment_buttons"):
                template["appointment_buttons"] = config["custom_appointment_buttons"]
            if config.get("custom_completion_message"):
                template["completion_message"] = config["custom_completion_message"]
            if config.get("custom_faq"):
                template["faq"] = config["custom_faq"]
            if config.get("custom_labels"):
                template["labels"] = config["custom_labels"]

        # Replace {business_name} placeholder
        bname = tenant.get("business_name", "")
        if bname:
            template["welcome_message"] = template["welcome_message"].replace("{business_name}", bname)

        return template

    async def process_message(self, lead, message_text: str, db, tenant_id: str = "", tenant_wa=None) -> None:
        """Procesa un mensaje según el template del tenant"""

        # Use tenant-specific WA service if provided
        if tenant_wa:
            self.wa = tenant_wa

        template = await self.get_tenant_template(tenant_id, db)

        # Detect urgency
        if self.detect_urgency(message_text):
            lead.is_urgent = True

        # Save to conversation history
        lead.conversation_history.append({
            "from": "customer",
            "text": message_text,
            "timestamp": datetime.utcnow().isoformat()
        })

        flow_stage = lead.flow_stage or "welcome"
        logger.info(f"[GenericFlow] {lead.phone} stage={flow_stage} msg='{message_text[:50]}'")

        # Special stages (appointment, reschedule, cancel, etc.)
        if flow_stage == "appointment_offer":
            await self._handle_appointment_offer(lead, message_text, template, db)
        elif flow_stage == "select_day":
            await self._handle_select_day(lead, message_text, db)
        elif flow_stage == "select_time":
            await self._handle_select_time(lead, message_text, template, db)
        elif flow_stage == "completed" or flow_stage == "handoff":
            await self._handle_completed(lead, message_text, template, db)
        elif flow_stage == "consulting":
            await self._handle_consulting(lead, message_text, db)
        # Normal flow steps
        elif flow_stage == "welcome":
            await self._handle_welcome(lead, template, db)
        else:
            # Process based on current step index
            await self._process_flow_step(lead, message_text, template, db)

        # Update lead in DB
        lead_dict = lead.model_dump() if hasattr(lead, 'model_dump') else dict(lead)
        lead_dict["last_message_at"] = datetime.utcnow().isoformat()
        await db.leads.update_one(
            {"phone": lead.phone, "tenant_id": tenant_id},
            {"$set": lead_dict},
            upsert=True
        )

    async def _handle_welcome(self, lead, template, db):
        """Envía mensaje de bienvenida con botones del template"""
        msg = template["welcome_message"]
        buttons = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
            for b in template["welcome_buttons"][:3]
        ]

        self.wa.send_interactive_buttons(lead.phone, msg, buttons)

        # Move to first flow step
        lead.flow_stage = "flow_step"
        lead.current_step_index = 0

        self._add_bot_message(lead, msg)

    async def _process_flow_step(self, lead, message_text: str, template, db):
        """Procesa el paso actual del flujo"""
        steps = template.get("flow_steps", [])
        step_idx = lead.current_step_index or 0

        if step_idx >= len(steps):
            # All steps done → scoring → appointment offer
            await self._finish_flow(lead, template, db)
            return

        current_step = steps[step_idx]

        # Check if step should be skipped
        if self._should_skip_step(current_step, lead):
            lead.current_step_index = step_idx + 1
            await self._process_flow_step(lead, message_text, template, db)
            return

        # If this is the first time seeing this step, save the user's answer from the PREVIOUS interaction
        # (the question was already asked, now we're receiving the answer)
        if step_idx == 0 and lead.flow_stage == "flow_step":
            # For the first step (intent), process the button/text response
            self._save_answer(lead, current_step, message_text)
            lead.current_step_index = step_idx + 1
            # Ask next question
            await self._ask_next_step(lead, template, db)
            return

        # Save answer to current step
        self._save_answer(lead, current_step, message_text)

        # Move to next step
        lead.current_step_index = step_idx + 1
        await self._ask_next_step(lead, template, db)

    async def _ask_next_step(self, lead, template, db):
        """Pregunta el siguiente paso del flujo"""
        steps = template.get("flow_steps", [])
        step_idx = lead.current_step_index or 0

        # Skip steps that should be skipped
        while step_idx < len(steps) and self._should_skip_step(steps[step_idx], lead):
            step_idx += 1
            lead.current_step_index = step_idx

        if step_idx >= len(steps):
            await self._finish_flow(lead, template, db)
            return

        step = steps[step_idx]
        question = step.get("question", "")

        if step.get("type") == "buttons" and step.get("buttons"):
            buttons = [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                for b in step["buttons"][:3]
            ]
            self.wa.send_interactive_buttons(lead.phone, question, buttons)
        else:
            self.wa.send_text_message(lead.phone, question)

        self._add_bot_message(lead, question)

    def _should_skip_step(self, step: dict, lead) -> bool:
        """Determina si un paso debe saltarse según intent o valores"""
        # Skip for specific intents
        skip_intents = step.get("skip_for_intents", [])
        if skip_intents and lead.intent in skip_intents:
            return True

        # Only for specific intents
        only_intents = step.get("only_for_intents", [])
        if only_intents and lead.intent not in only_intents:
            return True

        return False

    def _save_answer(self, lead, step: dict, message_text: str):
        """Guarda la respuesta del usuario en el campo correcto"""
        field = step.get("field", "")
        value = message_text.strip()

        # Clean button IDs
        if "_" in value and not " " in value:
            parts = value.split("_", 1)
            if len(parts) > 1:
                value = parts[-1]

        if field == "name":
            lead.name = value
        elif field == "intent":
            lead.intent = value
        elif field == "urgency":
            # Normalize urgency from button IDs
            if "urgente" in value.lower() or "hoy" in value.lower():
                lead.urgency = "urgente"
            elif "semana" in value.lower() or "mes" in value.lower() or "proximo" in value.lower():
                lead.urgency = "proximo_mes"
            elif "meses" in value.lower() or "puede" in value.lower() or "despues" in value.lower() or "no_apura" in value.lower():
                lead.urgency = "meses"
            else:
                lead.urgency = value
        elif field.startswith("custom_fields."):
            key = field.replace("custom_fields.", "")
            if not lead.custom_fields:
                lead.custom_fields = {}
            lead.custom_fields[key] = value
        else:
            if not lead.custom_fields:
                lead.custom_fields = {}
            lead.custom_fields[field] = value

    async def _finish_flow(self, lead, template, db):
        """Finaliza el flujo: calcula score y ofrece cita"""
        # Calculate score
        lead_dict = lead.model_dump() if hasattr(lead, 'model_dump') else dict(lead)
        scoring_config = template.get("scoring", {})
        score, status = calculate_score(lead_dict, scoring_config)
        lead.score = score
        lead.status = status

        # Offer appointment
        msg = template.get("appointment_message", "Queres que te contactemos?")
        appt_buttons = template.get("appointment_buttons", [
            {"id": "cita_si", "title": "Si"},
            {"id": "cita_no", "title": "No"}
        ])
        buttons = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
            for b in appt_buttons[:3]
        ]

        score_msg = f"Gracias por toda la info! Tu consulta tiene prioridad {'alta' if status == 'hot' else 'media' if status == 'warm' else 'normal'}.\n\n"
        self.wa.send_interactive_buttons(lead.phone, score_msg + msg, buttons)
        self._add_bot_message(lead, score_msg + msg)

        lead.flow_stage = "appointment_offer"

    async def _handle_appointment_offer(self, lead, message_text, template, db):
        """Maneja respuesta a oferta de cita"""
        msg_lower = message_text.lower()

        if "no" in msg_lower:
            response = f"Entendido {lead.name or ''}! Cualquier cosa que necesites, escribinos. Gracias!"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = "completed"
            self._add_bot_message(lead, response)
        else:
            # Determine appointment type from button
            if "visita" in msg_lower or "turno" in msg_lower or "reserva" in msg_lower or "reunion" in msg_lower:
                lead.appointment_type = "presencial"
            else:
                lead.appointment_type = "llamada"

            response = "Perfecto! Que dia te viene bien?\n\nPodes decirme:\n- 'Manana'\n- 'Jueves'\n- '15/03'\n- 'La semana que viene'"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = "select_day"
            self._add_bot_message(lead, response)

    async def _handle_select_day(self, lead, message_text, db):
        """Parsea fecha del usuario"""
        parsed_date = self._parse_date(message_text)

        if parsed_date:
            lead.appointment_datetime = parsed_date
            response = "Y en que horario preferis?"
            buttons = [
                {"type": "reply", "reply": {"id": "hora_manana", "title": "Manana (9-12hs)"}},
                {"type": "reply", "reply": {"id": "hora_tarde", "title": "Tarde (14-17hs)"}},
                {"type": "reply", "reply": {"id": "hora_noche", "title": "Noche (17-20hs)"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            lead.flow_stage = "select_time"
            self._add_bot_message(lead, response)
        else:
            response = "No entendi la fecha. Podes decirme algo como 'manana', 'jueves', o '15/03'?"
            self.wa.send_text_message(lead.phone, response)
            self._add_bot_message(lead, response)

    async def _handle_select_time(self, lead, message_text, template, db):
        """Procesa horario y confirma cita"""
        msg_lower = message_text.lower()

        if "manana" in msg_lower or "9" in msg_lower:
            hour = 10
        elif "tarde" in msg_lower or "14" in msg_lower:
            hour = 15
        else:
            hour = 18

        if lead.appointment_datetime:
            lead.appointment_datetime = lead.appointment_datetime.replace(hour=hour, minute=0)

        date_str = lead.appointment_datetime.strftime("%d/%m/%Y a las %H:%Hs") if lead.appointment_datetime else "por confirmar"

        completion_msg = template.get("completion_message", "Listo! Tu cita quedo agendada para {appointment_date}.")
        completion_msg = completion_msg.replace("{name}", lead.name or "")
        completion_msg = completion_msg.replace("{appointment_date}", date_str)
        completion_msg = completion_msg.replace("{appointment_type}", lead.appointment_type or "cita")

        self.wa.send_text_message(lead.phone, completion_msg)
        lead.flow_stage = "completed"
        lead.status = "appointment"
        self._add_bot_message(lead, completion_msg)

    async def _handle_completed(self, lead, message_text, template, db):
        """Lead que ya completó el flujo vuelve a escribir"""
        labels = template.get("labels", {})
        agent_label = labels.get("agent", "asesor")

        response = f"Hola {lead.name or ''}! Un {agent_label} ya esta al tanto de tu consulta.\n\nHay algo mas en lo que pueda ayudarte?"
        buttons = [
            {"type": "reply", "reply": {"id": "nueva_consulta", "title": "Nueva consulta"}},
            {"type": "reply", "reply": {"id": "ver_info", "title": "Info de contacto"}}
        ]
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        self._add_bot_message(lead, response)

    async def _handle_consulting(self, lead, message_text, db):
        """Maneja consultas libres con IA"""
        if self.llm and self.llm.enabled:
            response = await self.llm.generate_smart_response(
                message_text,
                {"name": lead.name, "intent": lead.intent}
            )
        else:
            response = "Gracias por tu consulta. Un asesor se comunicara contigo pronto para ayudarte."

        self.wa.send_text_message(lead.phone, response)
        self._add_bot_message(lead, response)

    def _add_bot_message(self, lead, text: str):
        lead.conversation_history.append({
            "from": "bot",
            "text": text,
            "timestamp": datetime.utcnow().isoformat()
        })

    def _parse_date(self, text: str):
        """Parsea fechas en lenguaje natural"""
        text_lower = text.lower().strip()
        now = datetime.utcnow()

        if "hoy" in text_lower:
            return now.replace(hour=10, minute=0, second=0, microsecond=0)
        elif "manana" in text_lower or "mañana" in text_lower:
            return (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        elif "pasado" in text_lower:
            return (now + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)

        # Days of week
        days_map = {
            "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
            "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6
        }
        for day_name, day_num in days_map.items():
            if day_name in text_lower:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return (now + timedelta(days=days_ahead)).replace(hour=10, minute=0, second=0, microsecond=0)

        # DD/MM format
        date_match = re.search(r'(\d{1,2})[/\-.](\d{1,2})', text)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year = now.year
            if month < now.month:
                year += 1
            try:
                return datetime(year, month, day, 10, 0, 0)
            except ValueError:
                pass

        # "semana que viene"
        if "semana" in text_lower:
            return (now + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0)

        return None
