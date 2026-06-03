"""
InmoBot SaaS - Motor de flujo genérico basado en templates
Procesa mensajes según el template del tenant.
"""
import logging
from datetime import datetime, timedelta, timezone
from flow_templates import get_template
from scoring import calculate_score
from whatsapp_service import create_wa_service_for_tenant
import re

logger = logging.getLogger(__name__)

URGENCY_KEYWORDS = [
    "urgente", "urgencia", "urgentemente", "necesito ya",
    "lo antes posible", "cuanto antes", "hoy mismo",
    "ahora mismo", "inmediato", "inmediatamente",
    "es para hoy", "muy urgente", "super urgente"
]

CATALOG_KEYWORDS = [
    "catalogo", "catálogo", "catalog",
    "productos", "ver productos", "lista de productos",
    "ofertas", "precios", "ver precios",
    "que tienen", "que ofrecen", "mostrame",
    "ver propiedades", "propiedades disponibles",
    "menu", "menú", "carta", "servicios disponibles"
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

    def detect_catalog_request(self, message: str) -> bool:
        """Detecta si el usuario pide ver el catalogo de productos"""
        msg_lower = message.lower().strip()
        return any(kw in msg_lower for kw in CATALOG_KEYWORDS)

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

        # Replace {business_name} placeholder en TODOS los mensajes del template.
        # Prioridad: business_profiles.business_name > tenants.business_name > tenants.name > default.
        # business_profiles es la fuente de verdad cuando el usuario completó /config.
        profile = await db.business_profiles.find_one({"tenant_id": tenant_id}, {"_id": 0})
        bname = (
            (profile.get("business_name") if profile else None)
            or tenant.get("business_name")
            or tenant.get("name")
            or "nuestro equipo"
        )

        def _replace(s):
            return s.replace("{business_name}", bname) if isinstance(s, str) else s

        for key in ["welcome_message", "appointment_message", "completion_message"]:
            if template.get(key):
                template[key] = _replace(template[key])

        # FAQ y otros pueden ser dicts/listas
        if isinstance(template.get("faq"), list):
            template["faq"] = [
                {**q, "answer": _replace(q.get("answer", ""))} for q in template["faq"]
            ]

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

        # Welcome buttons con archivo adjunto: si el cliente clickea un botón
        # del welcome que tiene `media_url` configurado, enviamos el archivo
        # ANTES de continuar con el flujo. No interrumpe el flujo normal:
        # el flujo sigue procesando el button_id como un mensaje más.
        await self._maybe_send_button_media(lead, message_text, template)

        # Catalog: detect product selection from buttons/list (id starts with prod_ or product_)
        catalog_handled = False
        msg_id_check = message_text.strip().lower()
        if msg_id_check.startswith("prod_") or msg_id_check.startswith("product_"):
            await self._handle_product_selection(lead, message_text, db, tenant_id)
            catalog_handled = True
        # Catalog: detect catalog/products request keyword (only outside appointment flow)
        elif flow_stage not in ("select_day", "select_time", "appointment_offer") \
                and self.detect_catalog_request(message_text):
            catalog_handled = await self._handle_catalog_request(lead, db, tenant_id)

        # Special stages (appointment, reschedule, cancel, etc.)
        if catalog_handled:
            pass  # ya respondio catalogo, saltar flujo regular
        elif flow_stage == "appointment_offer":
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

    async def _maybe_send_button_media(self, lead, message_text: str, template):
        """Si el mensaje matchea el id de un welcome_button con media adjunta,
        envia el archivo (imagen o documento) al cliente. No bloquea el flujo:
        después de mandar el archivo, el flujo continua normalmente."""
        msg_id = (message_text or "").strip()
        if not msg_id:
            return
        welcome_buttons = template.get("welcome_buttons", []) or []
        match = next(
            (b for b in welcome_buttons if b.get("id") == msg_id and b.get("media_url")),
            None,
        )
        if not match:
            return

        media_url = match.get("media_url")
        media_type = (match.get("media_type") or "image").lower()
        caption = match.get("media_caption") or match.get("title") or ""
        filename = match.get("media_filename")

        try:
            if media_type == "document":
                self.wa.send_document_message(
                    lead.phone, media_url, filename=filename, caption=caption
                )
                self._add_bot_message(lead, f"📄 [Documento enviado: {caption or filename or 'archivo'}]")
            else:
                self.wa.send_image_message(lead.phone, media_url, caption=caption)
                self._add_bot_message(lead, f"🖼️ [Imagen enviada: {caption or 'archivo'}]")
        except Exception as e:
            logger.warning(f"[generic_flow] No se pudo enviar media del boton {msg_id}: {e}")

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

        score_msg = f"¡Gracias por toda la información! Tu consulta tiene prioridad {'alta' if status == 'hot' else 'media' if status == 'warm' else 'normal'}.\n\n"
        self.wa.send_interactive_buttons(lead.phone, score_msg + msg, buttons)
        self._add_bot_message(lead, score_msg + msg)

        lead.flow_stage = "appointment_offer"

    async def _handle_appointment_offer(self, lead, message_text, template, db):
        """Maneja respuesta a oferta de cita"""
        msg_lower = message_text.lower()

        if "no" in msg_lower:
            response = f"¡Entendido{', ' + lead.name if lead.name else ''}! Ante cualquier consulta, escríbenos. ¡Gracias!"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = "completed"
            self._add_bot_message(lead, response)
        else:
            # Determine appointment type from button
            if "visita" in msg_lower or "turno" in msg_lower or "reserva" in msg_lower or "reunion" in msg_lower:
                lead.appointment_type = "visita"
            else:
                lead.appointment_type = "llamada"

            response = "¡Perfecto! ¿Qué día te queda bien?\n\nPuedes decirme:\n- 'Mañana'\n- 'Jueves'\n- '15/03'\n- 'La próxima semana'"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = "select_day"
            self._add_bot_message(lead, response)

    async def _handle_select_day(self, lead, message_text, db):
        """Parsea fecha del usuario"""
        parsed_date = self._parse_date(message_text)

        if parsed_date:
            lead.appointment_datetime = parsed_date
            response = "¿En qué horario prefieres?"
            buttons = [
                {"type": "reply", "reply": {"id": "hora_manana", "title": "Mañana (9-12h)"}},
                {"type": "reply", "reply": {"id": "hora_tarde", "title": "Tarde (14-17h)"}},
                {"type": "reply", "reply": {"id": "hora_noche", "title": "Noche (17-20h)"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            lead.flow_stage = "select_time"
            self._add_bot_message(lead, response)
        else:
            response = "No entendí la fecha. ¿Puedes decirme algo como 'mañana', 'jueves' o '15/03'?"
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
        """Lead que ya completó el flujo vuelve a escribir.
        Procesa los botones 'nueva_consulta' / 'ver_info', detecta intents por keyword,
        y delega a IA en último caso."""
        labels = template.get("labels", {})
        agent_label = labels.get("agent", "asesor")
        msg_raw = (message_text or "").strip()
        msg_id = msg_raw.lower()

        # Helper: detección de keywords (intent post-cita)
        CONTACT_KW = [
            "info de contacto", "informacion de contacto", "información de contacto",
            "info contacto", "datos de contacto", "datos del negocio",
            "info del negocio", "donde estan", "donde están", "donde quedan",
            "direccion", "dirección", "telefono", "teléfono",
            "email", "mail", "correo", "sitio web", "pagina", "página",
            "horario", "horarios", "atencion", "atención",
            "como contactarlos", "cómo contactarlos"
        ]
        NEW_QUERY_KW = [
            "otra consulta", "nueva consulta", "otra cosa", "otra pregunta",
            "tengo otra", "consultar de nuevo", "preguntar otra cosa",
            "hacer otra consulta", "necesito otra"
        ]

        def matches_any(kws):
            return any(kw in msg_id for kw in kws)

        # Botón "Nueva consulta" o keywords → reset del flow
        if msg_id == "nueva_consulta" or matches_any(NEW_QUERY_KW):
            lead.flow_stage = "welcome"
            lead.current_step_index = 0
            await self._handle_welcome(lead, template, db)
            return

        # Botón "Info de contacto" o keywords → mandar info del business_profile
        if msg_id == "ver_info" or matches_any(CONTACT_KW):
            tenant = await db.tenants.find_one({"tenant_id": lead.tenant_id}, {"_id": 0}) if lead.tenant_id else None
            profile = await db.business_profiles.find_one({"tenant_id": lead.tenant_id}, {"_id": 0}) if lead.tenant_id else None
            faq = template.get("faq", {}) or {}

            bname = (
                (profile.get("business_name") if profile else None)
                or (tenant.get("business_name") if tenant else None)
                or "nuestro equipo"
            )
            address = (profile.get("address") if profile else None) or faq.get("direccion", "")
            city = (profile.get("city") if profile else None) or ""
            full_address = f"{address}, {city}" if address and city else (address or city)

            phone = (profile.get("phone") if profile else None) or faq.get("telefono", "")
            email = (profile.get("email") if profile else None) or faq.get("email", "")
            website = (profile.get("website") if profile else None) or ""
            hours = (profile.get("business_hours") if profile else None) or faq.get("horarios", "")
            description = (profile.get("business_description") if profile else None) or ""

            lines = [f"📍 *Info de contacto - {bname}*", ""]
            if description:
                lines.append(f"_{description}_")
                lines.append("")
            if full_address:
                lines.append(f"📌 {full_address}")
            if hours:
                lines.append(f"🕐 {hours}")
            if phone:
                lines.append(f"📞 {phone}")
            if email:
                lines.append(f"✉️ {email}")
            if website:
                lines.append(f"🌐 {website}")
            if len(lines) <= 2:
                lines.append("Pronto un asesor se contactará con vos. ¡Gracias!")

            response = "\n".join(lines)
            self.wa.send_text_message(lead.phone, response)
            self._add_bot_message(lead, response)
            return

        # Texto libre / consulta nueva en estado completed → handoff con IA
        if self.llm and self.llm.enabled:
            ai_response = await self.llm.generate_smart_response(
                message_text,
                {"name": lead.name, "intent": lead.intent}
            )
            self.wa.send_text_message(lead.phone, ai_response)
            self._add_bot_message(lead, ai_response)
            return

        # Fallback: reofrecer el menú
        response = f"¡Hola{', ' + lead.name if lead.name else ''}! 👋 Un {agent_label} ya tiene tu consulta. ¿Hay algo más en lo que pueda ayudarte?"
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
            response = "Gracias por tu consulta. Un asesor se comunicará contigo pronto para ayudarte."

        self.wa.send_text_message(lead.phone, response)
        self._add_bot_message(lead, response)

    async def _handle_catalog_request(self, lead, db, tenant_id: str) -> bool:
        """Envia el catalogo de productos del tenant via WhatsApp interactive message.
        Si hay LLM habilitado y el lead tiene contexto/intent, envia recomendaciones personalizadas.

        Retorna True si se envio el catalogo (debe saltarse el flujo regular).
        """
        # Importar aqui para evitar circular import
        from catalog_service import CatalogService

        catalog = CatalogService(db)

        # Smart Substitution (Iter31): si el cliente menciona específicamente un
        # producto agotado, responder con sustituto en lugar del catálogo completo.
        last_msg = ""
        if lead.conversation_history:
            for m in reversed(lead.conversation_history):
                if m.get("from") == "customer":
                    last_msg = m.get("text", "")
                    break
        if last_msg:
            try:
                agotado = await catalog.find_out_of_stock_match(tenant_id, last_msg)
                if agotado:
                    subs = await catalog.find_substitute(tenant_id, agotado, max_results=3)
                    msg = catalog.build_substitute_message(agotado, subs)
                    wa = create_wa_service_for_tenant(
                        await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})
                    )
                    await wa.send_message(lead.phone, msg)
                    # Registrar en waitlist para avisar cuando reponga stock
                    try:
                        await catalog.add_to_waitlist(
                            tenant_id,
                            lead.phone,
                            agotado.get("product_id", ""),
                            agotado.get("name", ""),
                        )
                    except Exception as e:
                        logger.warning(f"[waitlist] add failed: {e}")
                    # Marcamos en el log para analytics
                    await db.substitute_events.insert_one({
                        "tenant_id": tenant_id,
                        "lead_phone": lead.phone,
                        "asked_for_product_id": agotado.get("product_id"),
                        "asked_for_name": agotado.get("name"),
                        "substitutes_offered": [s.get("product_id") for s in subs],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(
                        f"[substitute] tenant={tenant_id} lead={lead.phone} "
                        f"agotado='{agotado.get('name')}' subs={len(subs)}"
                    )
                    return True
            except Exception as e:
                logger.warning(f"[substitute] check failed: {e}")

        products = await catalog.get_products(tenant_id)

        if not products:
            return False  # no hay catalogo, dejar al flujo regular continuar

        # Si hay LLM y el lead tiene contexto, pedir recomendaciones personalizadas
        filtered = products
        personalized = False
        if self.llm and self.llm.enabled and len(products) > 3:
            last_msg = ""
            if lead.conversation_history:
                for m in reversed(lead.conversation_history):
                    if m.get("from") == "customer":
                        last_msg = m.get("text", "")
                        break
            lead_ctx = {
                "name": lead.name,
                "intent": lead.intent,
                "urgency": lead.urgency,
                **(lead.custom_fields or {})
            }
            try:
                rec_ids = await self.llm.recommend_products(last_msg, products, lead_ctx, max_results=3)
                if rec_ids:
                    filtered = [p for p in products if p.get("product_id") in rec_ids]
                    # Ordenar por relevancia
                    filtered.sort(key=lambda p: rec_ids.index(p["product_id"]))
                    personalized = True
            except Exception as e:
                logger.error(f"Error recomendaciones IA: {e}")

        try:
            header = "Recomendados para ti" if personalized else "Catalogo"
            if len(filtered) <= 3:
                body_text, buttons = catalog.build_carousel_buttons(filtered)
                intro = "Basado en tu busqueda, estos son los mas recomendados:\n\n" if personalized else ""
                self.wa.send_interactive_buttons(
                    lead.phone,
                    intro + (body_text or "Mira nuestros productos:"),
                    buttons,
                    header_text=header
                )
            else:
                list_data = catalog.build_product_list_message(filtered, header=header)
                self.wa.send_list_message(
                    lead.phone,
                    list_data["body"]["text"],
                    list_data["action"]["button"],
                    list_data["action"]["sections"],
                    header_text=list_data["header"]["text"]
                )
            self._add_bot_message(lead, f"[Catalogo enviado: {len(filtered)} productos{'(personalizado)' if personalized else ''}]")
            return True
        except Exception as e:
            logger.error(f"Error enviando catalogo: {e}")
            return False

    async def _handle_product_selection(self, lead, message_text: str, db, tenant_id: str):
        """Cuando el cliente selecciona un producto del catalogo (id prod_xxx), envia detalle"""
        from catalog_service import CatalogService

        catalog = CatalogService(db)
        msg_id = message_text.strip().lower()

        # Extraer product_id del prefijo (formato: prod_<uuid_30chars>)
        selected = None
        if msg_id.startswith("prod_"):
            pid_prefix = msg_id[5:]  # quitar "prod_"
            # Buscar producto cuyo product_id empiece con este prefijo
            products = await catalog.get_products(tenant_id)
            for p in products:
                pid = (p.get("product_id") or "")[:30].lower()
                if pid == pid_prefix or pid.startswith(pid_prefix):
                    selected = p
                    break
        elif msg_id.startswith("product_"):
            # Backward compat con prefijo viejo
            products = await catalog.get_products(tenant_id)
            name_prefix = msg_id[8:]
            for p in products:
                pname = p["name"][:15].replace(" ", "_").lower()
                if pname == name_prefix:
                    selected = p
                    break

        if not selected:
            self.wa.send_text_message(lead.phone, "No encontré ese producto. Escribe 'catálogo' para ver las opciones disponibles.")
            return

        msg = catalog.build_single_product_message(selected)
        # CTA buttons
        buttons = [
            {"type": "reply", "reply": {"id": "cita_si", "title": "Quiero info"}},
            {"type": "reply", "reply": {"id": "ver_catalogo", "title": "Ver mas"}}
        ]
        if selected.get("image_url"):
            self.wa.send_text_message(lead.phone, msg + f"\n\n{selected['image_url']}", preview_url=True)
        else:
            self.wa.send_text_message(lead.phone, msg)
        self.wa.send_interactive_buttons(lead.phone, "¿Te interesa esta propiedad?", buttons)
        self._add_bot_message(lead, f"[Detalle producto: {selected['name']}]")

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
