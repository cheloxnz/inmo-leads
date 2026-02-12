import logging
from typing import Dict, Optional
from models import Lead, FlowStage, LeadIntent, UrgencyLevel, FinancingType, PropertyType, LeadStatus
from whatsapp_service import WhatsAppService
from llm_service import LLMService
from scoring import ScoringEngine
from email_service import EmailService
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

# Palabras clave de urgencia
URGENCY_KEYWORDS = [
    "urgente", "urgencia", "urgentemente",
    "necesito ya", "lo antes posible", "cuanto antes",
    "hoy mismo", "ahora mismo", "inmediato", "inmediatamente",
    "es para hoy", "lo necesito para hoy", "muy urgente",
    "ayuda urgente", "es urgente", "super urgente"
]

class BotFlowManager:
    """Gestiona el flujo conversacional del bot"""
    
    def __init__(self, whatsapp_service: WhatsAppService, llm_service: LLMService, email_service: EmailService):
        self.wa = whatsapp_service
        self.llm = llm_service
        self.email = email_service
    
    def detect_urgency(self, message: str) -> bool:
        """Detecta si el mensaje contiene indicadores de urgencia"""
        message_lower = message.lower()
        for keyword in URGENCY_KEYWORDS:
            if keyword in message_lower:
                return True
        return False
    
    async def process_message(self, lead: Lead, message_text: str, db) -> Lead:
        """Procesa mensaje según el estado del flujo"""
        
        # Detectar urgencia en el mensaje
        if self.detect_urgency(message_text):
            lead.is_urgent = True
            logger.info(f"🚨 URGENCIA detectada para lead {lead.phone}")
        
        # Guardar mensaje en historial
        lead.conversation_history.append({
            "from": "customer",
            "text": message_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Processing message from {lead.phone}: '{message_text}' - Current stage: {lead.flow_stage}")
        
        # PRIMERO: Procesar estados de flujo activos (tienen prioridad)
        
        # Respuestas a recordatorio de cita
        if "confirmar_cita" in message_text.lower():
            response = "¡Perfecto! ✅ Tu cita está confirmada. ¡Te esperamos!"
            self.wa.send_text_message(lead.phone, response)
            await db.leads.update_one(
                {"phone": lead.phone},
                {"$set": {"appointment_confirmed": True}}
            )
            return
        
        # Respuestas a follow-up post-visita
        if "follow_up_interesado" in message_text.lower():
            response = "¡Qué bueno! 🏠 ¿Querés que te enviemos más opciones similares o preferís agendar otra visita?"
            buttons = [
                {"type": "reply", "reply": {"id": "mas_opciones", "title": "📋 Más opciones"}},
                {"type": "reply", "reply": {"id": "opcion_reagendar", "title": "📅 Agendar visita"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            return
        
        if "follow_up_otra_visita" in message_text.lower():
            response = "¡Perfecto! Vamos a agendar otra visita. 📅\n\n¿Qué día te viene mejor?"
            lead.flow_stage = FlowStage.RESCHEDULE_DAY
            await self.save_lead(lead, db)
            self.wa.send_text_message(lead.phone, response)
            return
        
        if "follow_up_no_gracias" in message_text.lower():
            response = f"¡Entendido {lead.name or ''}! Gracias por tu tiempo. 🙏\n\nCualquier cosa que necesites en el futuro, escribinos. ¡Éxitos! 🏠"
            self.wa.send_text_message(lead.phone, response)
            return
        
        # Respuestas a encuesta NPS
        if message_text.lower().startswith("nps_"):
            await self.handle_nps_response(lead, message_text, db)
            return
        
        # Solicitud de ubicación
        if "enviar_ubicacion" in message_text.lower() or "ubicacion" in message_text.lower() or "direccion" in message_text.lower():
            await self.send_property_location(lead)
            return
        
        # Estados de cancelación - verificar que el mensaje sea una respuesta válida
        if lead.flow_stage == FlowStage.CANCEL_CONFIRM:
            # Si es un saludo o mensaje no relacionado, mostrar opciones de nuevo
            if message_text.lower() in ["hola", "hi", "hello", "buenas", "buen dia", "buenos dias"]:
                logger.info(f"Greeting received in CANCEL_CONFIRM, showing options again")
                response = "¿Qué preferís hacer con tu cita?"
                buttons = [
                    {"type": "reply", "reply": {"id": "confirmar_cancelar", "title": "Sí, cancelar"}},
                    {"type": "reply", "reply": {"id": "mejor_reagendar", "title": "Mejor reagendar"}},
                    {"type": "reply", "reply": {"id": "no_mantener", "title": "No, mantener"}}
                ]
                self.wa.send_interactive_buttons(lead.phone, response, buttons)
            else:
                logger.info(f"Handling CANCEL_CONFIRM for {lead.phone}")
                await self.handle_cancel_confirm(lead, message_text)
        
        # Estados de reagendamiento
        elif lead.flow_stage == FlowStage.RESCHEDULE_CONFIRM:
            await self.handle_reschedule_confirm(lead, message_text)
        
        elif lead.flow_stage == FlowStage.RESCHEDULE_DAY:
            await self.handle_reschedule_day(lead, message_text)
        
        elif lead.flow_stage == FlowStage.RESCHEDULE_TIME:
            await self.handle_reschedule_time(lead, message_text)
        
        # SEGUNDO: Detectar intenciones especiales para leads con cita
        
        # Detectar intención de cancelar cita (solo si NO viene de un botón de opción)
        elif lead.appointment_datetime and self.wants_to_cancel(message_text) and "opcion_" not in message_text.lower():
            logger.info(f"Detected cancel intent for {lead.phone}")
            await self.handle_cancel_request(lead, message_text)
        
        # Detectar intención de reagendar (solo si NO viene de un botón de opción)
        elif lead.appointment_datetime and self.wants_to_reschedule(message_text) and "opcion_" not in message_text.lower():
            logger.info(f"Detected reschedule intent for {lead.phone}")
            await self.handle_reschedule_request(lead, message_text)
        
        # Detectar preguntas frecuentes
        elif self.is_faq_question(message_text):
            await self.handle_faq(lead, message_text)
        
        # Lead completado o en handoff que vuelve a escribir
        elif (lead.flow_stage == FlowStage.COMPLETED or lead.flow_stage == FlowStage.HANDOFF or lead.flow_stage == FlowStage.CONFIRMATION) and lead.appointment_datetime:
            await self.handle_completed_lead(lead, message_text, db)
        
        # Lead en HANDOFF sin cita - ofrecer ayuda
        elif lead.flow_stage == FlowStage.HANDOFF or lead.flow_stage == FlowStage.CONFIRMATION:
            response = f"¡Hola {lead.name or ''}! 👋\n\n"
            response += "Un asesor ya está al tanto de tu consulta y se comunicará pronto.\n\n"
            response += "¿Hay algo más en lo que pueda ayudarte mientras tanto?"
            
            buttons = [
                {"type": "reply", "reply": {"id": "nueva_consulta", "title": "Nueva consulta"}},
                {"type": "reply", "reply": {"id": "ver_horarios", "title": "Ver horarios"}},
                {"type": "reply", "reply": {"id": "ver_direccion", "title": "Ver dirección"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
        
        # TERCERO: Procesar flujo normal de calificación
        elif lead.flow_stage == FlowStage.WELCOME:
            await self.handle_welcome(lead, message_text)
        
        elif lead.flow_stage == FlowStage.INTENT:
            await self.handle_intent(lead, message_text)
        
        elif lead.flow_stage == FlowStage.NAME:
            await self.handle_name(lead, message_text)
        
        elif lead.flow_stage == FlowStage.ZONE:
            await self.handle_zone(lead, message_text)
        
        elif lead.flow_stage == FlowStage.BUDGET:
            await self.handle_budget(lead, message_text)
        
        elif lead.flow_stage == FlowStage.PROPERTY_TYPE:
            await self.handle_property_type(lead, message_text)
        
        elif lead.flow_stage == FlowStage.BEDROOMS:
            await self.handle_bedrooms(lead, message_text)
        
        elif lead.flow_stage == FlowStage.MUST_HAVE:
            await self.handle_must_have(lead, message_text)
        
        elif lead.flow_stage == FlowStage.URGENCY:
            await self.handle_urgency(lead, message_text)
        
        elif lead.flow_stage == FlowStage.FINANCING:
            await self.handle_financing(lead, message_text)
        
        elif lead.flow_stage == FlowStage.APPOINTMENT_OFFER:
            await self.handle_appointment_offer(lead, message_text)
        
        elif lead.flow_stage == FlowStage.SELECT_DAY:
            await self.handle_select_day(lead, message_text)
        
        elif lead.flow_stage == FlowStage.SELECT_TIME:
            await self.handle_select_time(lead, message_text)
        
        # Estado de consulta con IA
        elif lead.flow_stage == FlowStage.CONSULTING:
            await self.handle_consulting(lead, message_text)
        
        # Fallback: estado no reconocido - manejar opciones o reiniciar
        else:
            message_lower = message_text.lower()
            
            # Manejar botones del menú
            if message_lower == "buscar_propiedad" or "buscar" in message_lower or "propiedad" in message_lower:
                # Reiniciar flujo de búsqueda
                lead.flow_stage = FlowStage.WELCOME
                await self.handle_welcome(lead, message_text)
            
            elif message_lower == "tengo_consulta" or message_lower == "nueva_consulta":
                response = "¡Claro! Decime tu consulta y te ayudo. 😊\n\n"
                response += "También podés preguntarme sobre:\n"
                response += "• 📍 Dirección\n"
                response += "• 🕐 Horarios\n"
                response += "• 💳 Formas de pago\n"
                response += "• 📋 Requisitos"
                self.wa.send_text_message(lead.phone, response)
                lead.flow_stage = FlowStage.CONSULTING  # Nuevo estado para consultas
            
            elif message_lower == "ver_info" or message_lower == "ver_direccion":
                response = "📍 *Nuestra oficina*\n\n"
                response += "Av. Corrientes 1234, Piso 5\n"
                response += "CABA, Buenos Aires\n\n"
                response += "🕐 *Horarios*\n"
                response += "Lun-Vie: 9:00 - 18:00\n"
                response += "Sáb: 10:00 - 14:00\n\n"
                response += "📞 WhatsApp: +54 9 11 5943-4074"
                self.wa.send_text_message(lead.phone, response)
            
            elif message_lower == "ver_horarios":
                response = "🕐 *Horarios de atención*\n\n"
                response += "Lunes a Viernes: 9:00 - 18:00\n"
                response += "Sábados: 10:00 - 14:00\n"
                response += "Domingos y feriados: Cerrado"
                self.wa.send_text_message(lead.phone, response)
            
            else:
                # Mostrar menú de opciones
                logger.warning(f"Estado no manejado para {lead.phone}: {lead.flow_stage}")
                response = "¡Hola! 👋 ¿En qué puedo ayudarte?"
                buttons = [
                    {"type": "reply", "reply": {"id": "buscar_propiedad", "title": "Buscar propiedad"}},
                    {"type": "reply", "reply": {"id": "tengo_consulta", "title": "Tengo una consulta"}},
                    {"type": "reply", "reply": {"id": "ver_info", "title": "Info de contacto"}}
                ]
                self.wa.send_interactive_buttons(lead.phone, response, buttons)
        
        # Actualizar timestamp
        lead.last_message_at = datetime.utcnow()
        
        # Guardar en DB
        await self.save_lead(lead, db)
        
        return lead
    
    async def handle_welcome(self, lead: Lead, message: str):
        """Maneja etapa de bienvenida"""
        response = "¡Hola! Soy el asistente virtual de la inmobiliaria. Estoy acá para ayudarte a encontrar tu propiedad ideal 🏡\n\n¿Qué estás buscando?"
        
        buttons = [
            {"type": "reply", "reply": {"id": "comprar", "title": "Comprar"}},
            {"type": "reply", "reply": {"id": "alquilar", "title": "Alquilar"}},
            {"type": "reply", "reply": {"id": "inversion", "title": "Inversión"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.INTENT
    
    async def handle_intent(self, lead: Lead, message: str):
        """Maneja clasificación de intención"""
        message_lower = message.lower()
        
        if "comprar" in message_lower or message_lower == "1":
            lead.intent = LeadIntent.COMPRAR
        elif "alquilar" in message_lower or message_lower == "2":
            lead.intent = LeadIntent.ALQUILAR
        elif "vender" in message_lower or message_lower == "3":
            lead.intent = LeadIntent.VENDER
        elif "inversion" in message_lower or "inversión" in message_lower or message_lower == "4":
            lead.intent = LeadIntent.INVERSION
        else:
            result = await self.llm.classify_intent(message)
            intent_str = result.get("intent", "sin_definir")
            if intent_str in ["comprar", "alquilar", "vender", "inversion"]:
                lead.intent = LeadIntent(intent_str)
            else:
                lead.intent = LeadIntent.SIN_DEFINIR
        
        # Flujo diferente para vendedores
        if lead.intent == LeadIntent.VENDER:
            response = f"¡Genial! Querés vender tu propiedad. ¿Cuál es tu nombre completo?"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.NAME
        else:
            response = f"Perfecto. ¿Cuál es tu nombre completo?"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.NAME
    
    async def handle_name(self, lead: Lead, message: str):
        """Maneja captura de nombre"""
        name = message.strip()
        
        if len(name) < 2:
            response = "Por favor, ingresá tu nombre completo."
            self.wa.send_text_message(lead.phone, response)
            return
        
        lead.name = name
        
        response = f"Encantado, {name}. ¿En qué zona estás buscando?\n\nPodés escribir el barrio o zona que te interesa."
        self.wa.send_text_message(lead.phone, response)
        lead.flow_stage = FlowStage.ZONE
    
    async def handle_zone(self, lead: Lead, message: str):
        """Maneja zona de interés o ubicación de propiedad (para vendedores)"""
        zone = await self.llm.extract_zone(message)
        
        if zone:
            lead.zone = zone
            
            # Flujo diferente para vendedores
            if lead.intent == LeadIntent.VENDER:
                response = f"Perfecto, tu propiedad está en {zone}. ¿Qué tipo de propiedad es?\n\n1️⃣ Departamento\n2️⃣ Casa\n3️⃣ PH\n4️⃣ Local comercial\n5️⃣ Terreno\n6️⃣ Otro"
                self.wa.send_text_message(lead.phone, response)
                lead.flow_stage = FlowStage.PROPERTY_TYPE
            else:
                response = f"Genial, {zone}. ¿Cuál es tu presupuesto aproximado? (en USD)\n\nEjemplo: 150.000 USD o 100k-200k"
                self.wa.send_text_message(lead.phone, response)
                lead.flow_stage = FlowStage.BUDGET
        else:
            if lead.intent == LeadIntent.VENDER:
                response = "No pude identificar la zona. ¿En qué barrio está ubicada tu propiedad?\n\nEjemplo: Palermo, Belgrano, etc."
            else:
                response = "No pude identificar la zona. ¿Podés escribirla de nuevo?\n\nEjemplo: Palermo, Belgrano, etc."
            self.wa.send_text_message(lead.phone, response)
    
    async def handle_budget(self, lead: Lead, message: str):
        """Maneja presupuesto con validación de mínimo"""
        budget = await self.llm.extract_budget(message)
        
        if budget or "no" in message.lower() or "sin" in message.lower():
            lead.budget_text = budget if budget else "A definir"
            
            # Validar presupuesto mínimo según intención
            if budget and lead.intent == LeadIntent.COMPRAR:
                # Extraer número del presupuesto para validar
                import re
                numbers = re.findall(r'\d+', budget.replace('.', '').replace(',', ''))
                if numbers:
                    amount = int(numbers[0])
                    
                    # Si es menor a 50,000 USD, descalificar educadamente
                    if amount < 50000:
                        response = f"Gracias por tu interés, {lead.name}. "
                        response += f"Actualmente nuestras propiedades en venta tienen un valor desde USD 50.000. "
                        response += f"Con un presupuesto de {budget}, te recomendaría:\n\n"
                        response += "• Considerar alquilar mientras ahorrás\n"
                        response += "• Buscar zonas más económicas\n"
                        response += "• Consultar opciones de financiamiento\n\n"
                        response += "¿Te gustaría que te asesore sobre alguna de estas opciones?\n\n"
                        response += "Si preferís, puedo contactarte cuando tengamos opciones en tu rango de presupuesto."
                        
                        self.wa.send_text_message(lead.phone, response)
                        lead.flow_stage = FlowStage.DISQUALIFIED
                        lead.status = LeadStatus.COLD
                        lead.score = 0
                        return
            
            # Si pasa la validación, continuar
            response = "¿Qué tipo de propiedad te interesa?"
            buttons = [
                {"type": "reply", "reply": {"id": "departamento", "title": "Departamento"}},
                {"type": "reply", "reply": {"id": "casa", "title": "Casa"}},
                {"type": "reply", "reply": {"id": "ph", "title": "PH"}}
            ]
            
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            lead.flow_stage = FlowStage.PROPERTY_TYPE
        else:
            response = "No pude identificar el presupuesto. ¿Podés indicarlo de nuevo?\n\nEjemplo: 200.000 USD o 150k"
            self.wa.send_text_message(lead.phone, response)
    
    async def handle_property_type(self, lead: Lead, message: str):
        """Maneja tipo de propiedad"""
        message_lower = message.lower()
        
        type_mapping = {
            "departamento": PropertyType.DEPARTAMENTO,
            "depto": PropertyType.DEPARTAMENTO,
            "casa": PropertyType.CASA,
            "ph": PropertyType.PH,
            "local": PropertyType.LOCAL,
            "terreno": PropertyType.TERRENO,
            "oficina": PropertyType.OFICINA
        }
        
        for key, value in type_mapping.items():
            if key in message_lower:
                lead.property_type = value
                break
        
        if not lead.property_type:
            lead.property_type = PropertyType.OTRO
        
        response = "¿Cuántos dormitorios necesitás?"
        buttons = [
            {"type": "reply", "reply": {"id": "1", "title": "1 ambiente"}},
            {"type": "reply", "reply": {"id": "2", "title": "2 ambientes"}},
            {"type": "reply", "reply": {"id": "3+", "title": "3 o más"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.BEDROOMS
    
    async def handle_bedrooms(self, lead: Lead, message: str):
        """Maneja cantidad de dormitorios"""
        if message.isdigit():
            lead.bedrooms = int(message)
        elif "+" in message or "mas" in message.lower() or "más" in message.lower():
            lead.bedrooms = 3
        else:
            numbers = re.findall(r'\d+', message)
            if numbers:
                lead.bedrooms = int(numbers[0])
            else:
                lead.bedrooms = 2
        
        response = "¿Tenés algún requisito obligatorio?\n\nEjemplo: balcón, cochera, seguridad, etc.\n\nO respondé 'no' si no tenés requisitos específicos."
        self.wa.send_text_message(lead.phone, response)
        lead.flow_stage = FlowStage.MUST_HAVE
    
    async def handle_must_have(self, lead: Lead, message: str):
        """Maneja requisitos obligatorios"""
        if "no" not in message.lower():
            requirements = [r.strip() for r in message.split(",")]
            lead.must_have = requirements[:5]
        
        response = "¿Qué tan urgente es tu búsqueda?"
        buttons = [
            {"type": "reply", "reply": {"id": "urgente", "title": "Urgente (semanas)"}},
            {"type": "reply", "reply": {"id": "mes", "title": "Próximo mes"}},
            {"type": "reply", "reply": {"id": "meses", "title": "Próximos meses"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.URGENCY
    
    async def handle_urgency(self, lead: Lead, message: str):
        """Maneja nivel de urgencia"""
        message_lower = message.lower()
        
        if "urgente" in message_lower or "semana" in message_lower:
            lead.urgency = UrgencyLevel.URGENTE
        elif "mes" in message_lower and "meses" not in message_lower:
            lead.urgency = UrgencyLevel.PROXIMO_MES
        elif "meses" in message_lower:
            lead.urgency = UrgencyLevel.MESES
        elif "mirando" in message_lower:
            lead.urgency = UrgencyLevel.SOLO_MIRANDO
        else:
            lead.urgency = UrgencyLevel.MESES
        
        if lead.intent == LeadIntent.COMPRAR:
            response = "¿Cómo pensás financiar la compra?"
            buttons = [
                {"type": "reply", "reply": {"id": "efectivo", "title": "Efectivo"}},
                {"type": "reply", "reply": {"id": "credito", "title": "Crédito hipotecario"}},
                {"type": "reply", "reply": {"id": "nose", "title": "No sé aún"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            lead.flow_stage = FlowStage.FINANCING
        else:
            await self.calculate_and_offer_appointment(lead)
    
    async def handle_financing(self, lead: Lead, message: str):
        """Maneja tipo de financiamiento"""
        message_lower = message.lower()
        
        if "efectivo" in message_lower:
            lead.financing = FinancingType.EFECTIVO
        elif "credito" in message_lower or "crédito" in message_lower:
            lead.financing = FinancingType.CREDITO_HIPOTECARIO
        elif "uva" in message_lower:
            lead.financing = FinancingType.CREDITO_UVA
        elif "procrear" in message_lower:
            lead.financing = FinancingType.PROCREAR
        elif "mixto" in message_lower:
            lead.financing = FinancingType.MIXTO
        else:
            lead.financing = FinancingType.NO_SE
        
        await self.calculate_and_offer_appointment(lead)
    
    async def calculate_and_offer_appointment(self, lead: Lead):
        """Calcula score y ofrece agendar cita"""
        # Calcular score
        lead.score = ScoringEngine.calculate_score(lead)
        lead.status = ScoringEngine.classify_lead(lead.score)
        
        # Mensaje según clasificación
        if lead.status.value == "hot":
            emoji = "🔥"
            message = f"Excelente! {emoji} Encontré varias opciones que se ajustan a lo que buscás.\n\n"
        elif lead.status.value == "warm":
            emoji = "🟡"
            message = f"Perfecto! {emoji} Tengo opciones interesantes para mostrarte.\n\n"
        else:
            emoji = "👍"
            message = f"Entiendo! {emoji} Te voy a mantener informado de nuevas opciones.\n\n"
        
        message += "¿Te gustaría agendar una visita o llamada con un asesor?"
        
        buttons = [
            {"type": "reply", "reply": {"id": "si_visita", "title": "Sí, visita"}},
            {"type": "reply", "reply": {"id": "si_llamada", "title": "Sí, llamada"}},
            {"type": "reply", "reply": {"id": "no_ahora", "title": "No ahora"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, message, buttons)
        lead.flow_stage = FlowStage.APPOINTMENT_OFFER
    
    async def handle_appointment_offer(self, lead: Lead, message: str):
        """Maneja oferta de agendamiento"""
        message_lower = message.lower()
        
        if "no" in message_lower:
            response = "Sin problema! Te voy a mantener al tanto de nuevas propiedades que coincidan con tu búsqueda. ¡Gracias! 👋"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.COMPLETED
        else:
            if "visita" in message_lower:
                lead.appointment_type = "visita"
            else:
                lead.appointment_type = "llamada"
            
            response = "¿Qué día te viene bien?\n\nEjemplos:\n- Mañana\n- Lunes\n- 15/02"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.SELECT_DAY
    
    def _parse_date_from_text(self, message: str) -> datetime:
        """
        Parsea una fecha desde texto en español.
        Maneja formatos como:
        - "mañana", "pasado mañana"
        - "lunes", "martes", etc.
        - "Jueves 12" (día de la semana + número de día)
        - "12" (solo número)
        - "15/02", "15-02"
        - "7 de febrero"
        """
        message_lower = message.lower().strip()
        now = datetime.now()
        
        # Mapeo de días de la semana (en español)
        days_of_week = {
            'lunes': 0, 'martes': 1, 'miercoles': 2, 'miércoles': 2,
            'jueves': 3, 'viernes': 4, 'sabado': 5, 'sábado': 5, 'domingo': 6
        }
        
        # Mapeo de meses
        months = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        
        # 1. Mañana / Pasado mañana
        if "mañana" in message_lower or "manana" in message_lower:
            if "pasado" in message_lower:
                return now + timedelta(days=2)
            return now + timedelta(days=1)
        
        # 2. Formato "DíaSemana Número" (ej: "Jueves 12", "Sábado 7")
        for day_name, day_idx in days_of_week.items():
            if day_name in message_lower:
                # Buscar si hay un número de día
                numbers = re.findall(r'\d{1,2}', message_lower)
                if numbers:
                    # Hay un número, usar ese día del mes
                    day_num = int(numbers[0])
                    if 1 <= day_num <= 31:
                        month = now.month
                        year = now.year
                        # Si el día ya pasó, ir al mes siguiente
                        if day_num <= now.day:
                            month += 1
                            if month > 12:
                                month = 1
                                year += 1
                        try:
                            return datetime(year, month, day_num)
                        except ValueError:
                            pass
                else:
                    # Solo día de la semana, calcular próximo
                    days_ahead = day_idx - now.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    return now + timedelta(days=days_ahead)
        
        # 3. Formato DD/MM o DD-MM
        match = re.search(r'(\d{1,2})[/\-](\d{1,2})', message_lower)
        if match:
            day, month = int(match.group(1)), int(match.group(2))
            year = now.year
            if month < now.month or (month == now.month and day < now.day):
                year += 1
            try:
                return datetime(year, month, day)
            except ValueError:
                pass
        
        # 4. Formato "7 de febrero", "15 de marzo"
        match = re.search(r'(\d{1,2})\s*de\s*(\w+)', message_lower)
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            if month_name in months:
                month = months[month_name]
                year = now.year
                if month < now.month or (month == now.month and day < now.day):
                    year += 1
                try:
                    return datetime(year, month, day)
                except ValueError:
                    pass
        
        # 5. Solo número (asumimos día del mes actual o próximo)
        match = re.search(r'^(\d{1,2})$', message_lower)
        if match:
            day = int(match.group(1))
            if 1 <= day <= 31:
                month = now.month
                year = now.year
                if day <= now.day:
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
                try:
                    return datetime(year, month, day)
                except ValueError:
                    pass
        
        # No se pudo parsear
        return None

    async def handle_select_day(self, lead: Lead, message: str):
        """Maneja selección de día para nueva cita"""
        new_date = self._parse_date_from_text(message)
        
        if new_date is None:
            response = "No pude entender la fecha. Por favor indicala así:\n• Mañana\n• Lunes\n• 12 (día del mes)\n• 15/02\n• 7 de febrero"
            self.wa.send_text_message(lead.phone, response)
            return  # Quedamos en el mismo estado SELECT_DAY
        
        # Guardar la fecha temporalmente
        lead.notes = f"Fecha_cita:{new_date.strftime('%Y%m%d')}"
        
        formatted = new_date.strftime('%d/%m/%Y')
        response = f"Perfecto, {formatted}. ¿Qué horario preferís?\n\nHorarios disponibles:\nLun-Vie: 9-20hs\nSáb: 10-14hs"
        
        buttons = [
            {"type": "reply", "reply": {"id": f"hora_10_{new_date.strftime('%Y%m%d')}", "title": "Mañana (9-12hs)"}},
            {"type": "reply", "reply": {"id": f"hora_15_{new_date.strftime('%Y%m%d')}", "title": "Tarde (14-17hs)"}},
            {"type": "reply", "reply": {"id": f"hora_18_{new_date.strftime('%Y%m%d')}", "title": "Noche (17-20hs)"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.SELECT_TIME
    
    async def handle_select_time(self, lead: Lead, message: str):
        """Maneja selección de horario y confirma cita"""
        message_lower = message.lower()
        
        # Intentar extraer fecha del ID del botón (formato hora_HH_YYYYMMDD)
        appointment_date = None
        match = re.search(r'hora_(\d+)_(\d{8})', message_lower)
        if match:
            hour = int(match.group(1))
            date_str = match.group(2)
            try:
                appointment_date = datetime.strptime(date_str, '%Y%m%d')
                appointment_date = appointment_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            except:
                pass
        
        # Si no, intentar desde notes
        if appointment_date is None and lead.notes and "Fecha_cita:" in lead.notes:
            try:
                date_part = lead.notes.split("Fecha_cita:")[1].strip()[:8]
                appointment_date = datetime.strptime(date_part, '%Y%m%d')
            except:
                pass
        
        # Fallback: mañana
        if appointment_date is None:
            appointment_date = datetime.now() + timedelta(days=1)
        
        # Determinar hora según selección
        if "mañana" in message_lower or "manana" in message_lower or "10" in message_lower or "9" in message_lower:
            appointment_date = appointment_date.replace(hour=10, minute=0, second=0, microsecond=0)
        elif "tarde" in message_lower or "15" in message_lower or "14" in message_lower:
            appointment_date = appointment_date.replace(hour=15, minute=0, second=0, microsecond=0)
        else:
            appointment_date = appointment_date.replace(hour=18, minute=0, second=0, microsecond=0)
        
        lead.appointment_datetime = appointment_date
        lead.notes = None  # Limpiar notes temporal
        
        response = f"¡Perfecto! ✅\n\nTu {lead.appointment_type or 'cita'} quedó agendada para:\n{appointment_date.strftime('%d/%m/%Y a las %H:%M')}\n\nUn asesor se va a comunicar con vos para confirmar. ¡Gracias! 🙌"
        
        self.wa.send_text_message(lead.phone, response)
        lead.flow_stage = FlowStage.COMPLETED
        
        if ScoringEngine.should_handoff_to_human(lead):
            await self.trigger_handoff(lead)
    
    async def trigger_handoff(self, lead: Lead):
        """Dispara notificación a asesor humano"""
        logger.info(f"HANDOFF: Lead {lead.phone} debe pasar a humano")
        lead.flow_stage = FlowStage.HANDOFF
        
        # Enviar notificación por email
        try:
            lead_dict = lead.model_dump()
            self.email.send_hot_lead_notification(lead_dict)
            logger.info(f"Email de notificación enviado para lead {lead.phone}")
        except Exception as e:
            logger.error(f"Error enviando email de notificación: {str(e)}")
    
    async def save_lead(self, lead: Lead, db):
        """Guarda lead en base de datos"""
        lead_dict = lead.model_dump()
        lead_dict["last_message_at"] = lead.last_message_at.isoformat()
        lead_dict["created_at"] = lead.created_at.isoformat()
        if lead.appointment_datetime:
            lead_dict["appointment_datetime"] = lead.appointment_datetime.isoformat()
        
        await db.leads.update_one(
            {"phone": lead.phone},
            {"$set": lead_dict},
            upsert=True
        )

    # ==========================================
    # FUNCIONALIDAD DE REAGENDAMIENTO
    # ==========================================
    
    def wants_to_reschedule(self, message: str) -> bool:
        """Detecta si el usuario quiere reagendar su cita"""
        message_lower = message.lower()
        
        # Palabras clave para reagendamiento
        reschedule_keywords = [
            "cambiar cita", "cambiar la cita", "modificar cita", "modificar la cita",
            "reagendar", "re-agendar", "reprogramar", "otra fecha", "otro día", "otro dia",
            "cambiar fecha", "cambiar la fecha", "cambiar horario", "cambiar el horario",
            "mover cita", "mover la cita", "postergar", "adelantar",
            "no puedo ese día", "no puedo ese dia", "no me sirve",
            "cambiar el día", "cambiar el dia", "otra hora", "reagendar_cita"
        ]
        
        for keyword in reschedule_keywords:
            if keyword in message_lower:
                return True
        
        return False
    
    async def handle_reschedule_request(self, lead: Lead, message: str):
        """Inicia el flujo de reagendamiento"""
        current_appointment = lead.appointment_datetime
        
        if current_appointment:
            formatted_date = current_appointment.strftime('%d/%m/%Y a las %H:%M')
            response = f"Veo que querés cambiar tu cita actual del {formatted_date}.\n\n¿Confirmás que querés reagendar?"
            
            buttons = [
                {"type": "reply", "reply": {"id": "si_reagendar", "title": "Sí, reagendar"}},
                {"type": "reply", "reply": {"id": "no_mantener", "title": "No, mantener cita"}}
            ]
            
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            lead.flow_stage = FlowStage.RESCHEDULE_CONFIRM
        else:
            response = "No tenés una cita agendada actualmente. ¿Te gustaría agendar una?"
            buttons = [
                {"type": "reply", "reply": {"id": "si_agendar", "title": "Sí, agendar"}},
                {"type": "reply", "reply": {"id": "no_gracias", "title": "No, gracias"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
    
    async def handle_reschedule_confirm(self, lead: Lead, message: str):
        """Confirma si el usuario quiere reagendar"""
        message_lower = message.lower()
        
        if "no" in message_lower or "mantener" in message_lower:
            current = lead.appointment_datetime.strftime('%d/%m/%Y a las %H:%M')
            response = f"Perfecto, tu cita del {current} sigue confirmada. ¡Nos vemos! 👋"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.COMPLETED
        else:
            response = "¿Para qué fecha querés reagendar?\n\nPor favor indicá el día y mes, por ejemplo:\n• 7 de febrero\n• 15/02\n• Mañana"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.RESCHEDULE_DAY
    
    async def handle_reschedule_day(self, lead: Lead, message: str):
        """Maneja selección de nuevo día para reagendamiento"""
        new_date = self._parse_date_from_text(message)
        
        if new_date is None:
            response = "No pude entender la fecha. Por favor indicala así:\n• Mañana\n• Lunes\n• 12 (día del mes)\n• 15/02\n• 7 de febrero"
            self.wa.send_text_message(lead.phone, response)
            return  # Quedamos en el mismo estado RESCHEDULE_DAY
        
        # Guardar la fecha parseada en notes
        lead.notes = f"Reagendar:{new_date.strftime('%Y%m%d')}"
        
        response = f"Perfecto, {new_date.strftime('%d/%m/%Y')}. ¿Qué horario te viene mejor?"
        
        buttons = [
            {"type": "reply", "reply": {"id": f"hora_10_{new_date.strftime('%Y%m%d')}", "title": "Mañana (9-12hs)"}},
            {"type": "reply", "reply": {"id": f"hora_15_{new_date.strftime('%Y%m%d')}", "title": "Tarde (14-17hs)"}},
            {"type": "reply", "reply": {"id": f"hora_18_{new_date.strftime('%Y%m%d')}", "title": "Noche (17-20hs)"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.RESCHEDULE_TIME
    
    async def handle_reschedule_time(self, lead: Lead, message: str):
        """Maneja selección de nuevo horario y confirma reagendamiento"""
        message_lower = message.lower()
        
        # Guardar cita anterior para el mensaje
        old_appointment = lead.appointment_datetime
        old_formatted = old_appointment.strftime('%d/%m/%Y a las %H:%M') if old_appointment else "N/A"
        
        new_date = None
        
        # Intentar extraer fecha del ID del botón (formato hora_HH_YYYYMMDD)
        match = re.search(r'hora_(\d+)_(\d{8})', message_lower)
        if match:
            hour = int(match.group(1))
            date_str = match.group(2)
            try:
                new_date = datetime.strptime(date_str, '%Y%m%d')
                new_date = new_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            except:
                pass
        
        # Si no hay fecha del botón, intentar parsear de notes
        if new_date is None and lead.notes and "Reagendar:" in lead.notes:
            try:
                date_part = lead.notes.split("Reagendar:")[1].strip()[:8]
                new_date = datetime.strptime(date_part, '%Y%m%d')
            except:
                pass
        
        # Fallback
        if new_date is None:
            new_date = datetime.now() + timedelta(days=1)
        
        # Determinar hora según selección si no viene del botón
        if not match:
            if "mañana" in message_lower or "manana" in message_lower or "10" in message_lower or "9" in message_lower:
                new_date = new_date.replace(hour=10, minute=0, second=0, microsecond=0)
            elif "tarde" in message_lower or "15" in message_lower or "14" in message_lower:
                new_date = new_date.replace(hour=15, minute=0, second=0, microsecond=0)
            else:
                new_date = new_date.replace(hour=18, minute=0, second=0, microsecond=0)
        
        # Actualizar la cita
        lead.appointment_datetime = new_date
        new_formatted = new_date.strftime('%d/%m/%Y a las %H:%M')
        
        response = f"✅ ¡Cita reagendada exitosamente!\n\n"
        response += f"📅 Cita anterior: {old_formatted}\n"
        response += f"📅 Nueva cita: {new_formatted}\n\n"
        response += f"Un asesor se comunicará para confirmar. ¡Gracias por avisar! 🙌"
        
        self.wa.send_text_message(lead.phone, response)
        lead.flow_stage = FlowStage.COMPLETED
        lead.notes = None  # Limpiar notes temporal
        
        logger.info(f"Lead {lead.phone} reagendó cita de {old_formatted} a {new_formatted}")

    # ==========================================
    # FUNCIONALIDAD DE CANCELACIÓN
    # ==========================================
    
    def wants_to_cancel(self, message: str) -> bool:
        """Detecta si el usuario quiere cancelar su cita"""
        message_lower = message.lower()
        
        cancel_keywords = [
            "cancelar", "anular", "no puedo ir", "no voy a poder",
            "cancelo", "anulo", "dar de baja", "eliminar cita",
            "no quiero la cita", "borrar cita", "cancelar_cita"
        ]
        
        for keyword in cancel_keywords:
            if keyword in message_lower:
                return True
        
        return False
    
    async def handle_cancel_request(self, lead: Lead, message: str):
        """Inicia el flujo de cancelación"""
        logger.info(f"handle_cancel_request called for {lead.phone}")
        current_appointment = lead.appointment_datetime
        formatted_date = current_appointment.strftime('%d/%m/%Y a las %H:%M')
        
        response = f"Veo que querés cancelar tu cita del {formatted_date}.\n\n¿Qué preferís hacer?"
        
        buttons = [
            {"type": "reply", "reply": {"id": "confirmar_cancelar", "title": "Sí, cancelar"}},
            {"type": "reply", "reply": {"id": "mejor_reagendar", "title": "Mejor reagendar"}},
            {"type": "reply", "reply": {"id": "no_mantener", "title": "No, mantener"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.CANCEL_CONFIRM
        logger.info(f"Set flow_stage to CANCEL_CONFIRM for {lead.phone}")
    
    async def handle_cancel_confirm(self, lead: Lead, message: str):
        """Confirma la cancelación o redirige a reagendamiento"""
        message_lower = message.lower()
        logger.info(f"handle_cancel_confirm for {lead.phone}: '{message_lower}'")
        
        # Detectar por ID del botón o palabras clave
        if message_lower == "no_mantener" or message_lower == "mantener" or "mantener" in message_lower:
            current = lead.appointment_datetime.strftime('%d/%m/%Y a las %H:%M')
            response = f"Perfecto, tu cita del {current} sigue confirmada. ¡Te esperamos! 👋"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.COMPLETED
        
        elif message_lower == "mejor_reagendar" or "reagendar" in message_lower:
            lead.flow_stage = FlowStage.COMPLETED  # Reset antes de reagendar
            await self.handle_reschedule_request(lead, message)
        
        elif message_lower == "confirmar_cancelar" or "si" in message_lower or "sí" in message_lower:
            old_appointment = lead.appointment_datetime.strftime('%d/%m/%Y a las %H:%M')
            lead.appointment_datetime = None
            lead.status = LeadStatus.WARM
            
            response = f"✅ Tu cita del {old_appointment} ha sido cancelada.\n\n"
            response += "Si en el futuro querés agendar una nueva cita, escribinos. ¡Éxitos! 🙌"
            
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.COMPLETED
            
            logger.info(f"Lead {lead.phone} canceló su cita del {old_appointment}")
        
        else:
            # No entendió la respuesta, volver a preguntar
            response = "¿Qué preferís hacer con tu cita?"
            buttons = [
                {"type": "reply", "reply": {"id": "confirmar_cancelar", "title": "Sí, cancelar"}},
                {"type": "reply", "reply": {"id": "mejor_reagendar", "title": "Mejor reagendar"}},
                {"type": "reply", "reply": {"id": "no_mantener", "title": "No, mantener"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)

    # ==========================================
    # MANEJO DE LEADS COMPLETADOS
    # ==========================================
    
    async def handle_completed_lead(self, lead: Lead, message: str, db):
        """Responde a leads que ya tienen cita y vuelven a escribir"""
        message_lower = message.lower()
        logger.info(f"handle_completed_lead for {lead.phone}: '{message_lower}'")
        
        # Verificar si la cita ya pasó
        now = datetime.utcnow()
        appointment_passed = lead.appointment_datetime < now
        
        # Si seleccionó reagendar (desde botón o texto)
        if "opcion_reagendar" in message_lower or ("reagendar" in message_lower and "mejor" not in message_lower):
            await self.handle_reschedule_request(lead, message)
            return
        
        # Si seleccionó cancelar (desde botón o texto)
        if "opcion_cancelar" in message_lower:
            await self.handle_cancel_request(lead, message)
            return
        
        # Si seleccionó consulta o hace una pregunta
        if "opcion_consulta" in message_lower:
            response = "¡Claro! Decime tu consulta y te ayudo. 😊"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.CONSULTING
            # Guardar el cambio de estado - IMPORTANTE
            await self.save_lead(lead, db)
            logger.info(f"Lead {lead.phone} changed to CONSULTING state")
            return
        
        # Detectar si es una pregunta (no es saludo ni botón)
        is_question = len(message_lower) > 15 or "?" in message or any(word in message_lower for word in ["quiero", "busco", "necesito", "dudas", "consulta", "ayuda", "zona", "precio", "barrio", "alquiler", "comprar"])
        is_greeting = message_lower in ["hola", "hi", "hello", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches"]
        
        # Si es una pregunta real, usar GPT
        if is_question and not is_greeting:
            await self.handle_consulting(lead, message)
            return
        
        # Si la cita ya pasó
        if appointment_passed:
            response = f"¡Hola {lead.name or ''}! 👋\n\n"
            response += f"Veo que tenías una cita agendada para el {lead.appointment_datetime.strftime('%d/%m/%Y')} que ya pasó.\n\n"
            response += "¿Cómo fue tu experiencia? ¿Necesitás agendar otra cita?"
            
            buttons = [
                {"type": "reply", "reply": {"id": "opcion_reagendar", "title": "Agendar nueva cita"}},
                {"type": "reply", "reply": {"id": "opcion_consulta", "title": "Tengo una consulta"}},
                {"type": "reply", "reply": {"id": "buscar_propiedad", "title": "Buscar propiedades"}}
            ]
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            return
        
        # Mostrar menú de opciones (cita futura)
        appointment = lead.appointment_datetime.strftime('%d/%m/%Y a las %H:%M')
        
        response = f"¡Hola {lead.name or ''}! 👋\n\n"
        response += f"Ya tenés tu cita agendada para el {appointment}.\n\n"
        response += "¿En qué puedo ayudarte?"
        
        buttons = [
            {"type": "reply", "reply": {"id": "opcion_reagendar", "title": "Cambiar fecha/hora"}},
            {"type": "reply", "reply": {"id": "opcion_cancelar", "title": "Cancelar mi cita"}},
            {"type": "reply", "reply": {"id": "opcion_consulta", "title": "Tengo una consulta"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)

    # ==========================================
    # PREGUNTAS FRECUENTES (FAQ)
    # ==========================================
    
    def is_faq_question(self, message: str) -> bool:
        """Detecta si es una pregunta frecuente"""
        message_lower = message.lower()
        
        faq_keywords = [
            "dirección", "direccion", "donde queda", "dónde queda", "ubicación", "ubicacion",
            "horario", "horarios", "a qué hora", "a que hora", "qué días", "que dias",
            "formas de pago", "medios de pago", "como pago", "cómo pago", "efectivo", "tarjeta",
            "teléfono", "telefono", "contacto", "llamar", "whatsapp",
            "requisitos", "que necesito", "qué necesito", "documentos", "documentación",
            "precio", "precios", "cuánto cuesta", "cuanto cuesta", "valor", "costos"
        ]
        
        for keyword in faq_keywords:
            if keyword in message_lower:
                return True
        
        return False
    
    async def handle_faq(self, lead: Lead, message: str):
        """Responde preguntas frecuentes"""
        message_lower = message.lower()
        
        # Dirección/Ubicación
        if any(k in message_lower for k in ["dirección", "direccion", "donde queda", "dónde queda", "ubicación", "ubicacion"]):
            response = "📍 *Nuestra oficina*\n\n"
            response += "Av. Corrientes 1234, Piso 5\n"
            response += "CABA, Buenos Aires\n\n"
            response += "📌 Cerca del subte B - Estación Callao"
        
        # Horarios
        elif any(k in message_lower for k in ["horario", "horarios", "a qué hora", "a que hora", "qué días", "que dias"]):
            response = "🕐 *Horarios de atención*\n\n"
            response += "Lunes a Viernes: 9:00 - 18:00\n"
            response += "Sábados: 10:00 - 14:00\n"
            response += "Domingos y feriados: Cerrado\n\n"
            response += "💡 También podés agendar una cita fuera de horario con previa coordinación."
        
        # Formas de pago
        elif any(k in message_lower for k in ["formas de pago", "medios de pago", "como pago", "cómo pago", "efectivo", "tarjeta"]):
            response = "💳 *Formas de pago*\n\n"
            response += "• Efectivo\n"
            response += "• Transferencia bancaria\n"
            response += "• Tarjeta de débito/crédito\n"
            response += "• Financiación (consultar)\n\n"
            response += "📝 Para reservas y señas, consultá con tu asesor las opciones disponibles."
        
        # Contacto
        elif any(k in message_lower for k in ["teléfono", "telefono", "contacto", "llamar"]):
            response = "📞 *Contacto*\n\n"
            response += "WhatsApp: +54 9 11 5943-4074\n"
            response += "Email: info@inmobiliaria.com\n"
            response += "Web: www.inmobiliaria.com\n\n"
            response += "💬 ¡Estamos para ayudarte!"
        
        # Requisitos
        elif any(k in message_lower for k in ["requisitos", "que necesito", "qué necesito", "documentos", "documentación"]):
            response = "📋 *Requisitos para alquilar/comprar*\n\n"
            response += "*Para alquilar:*\n"
            response += "• DNI\n"
            response += "• Recibos de sueldo (últimos 3)\n"
            response += "• Garantía propietaria o seguro de caución\n\n"
            response += "*Para comprar:*\n"
            response += "• DNI\n"
            response += "• Constancia de CUIL/CUIT\n"
            response += "• Comprobante de ingresos\n\n"
            response += "📌 Cada caso se evalúa individualmente. Tu asesor te dará más detalles."
        
        # Precios
        elif any(k in message_lower for k in ["precio", "precios", "cuánto cuesta", "cuanto cuesta", "valor", "costos"]):
            response = "💰 *Sobre precios*\n\n"
            response += "Los precios varían según:\n"
            response += "• Zona\n"
            response += "• Tipo de propiedad\n"
            response += "• Metros cuadrados\n"
            response += "• Amenities\n\n"
            response += "📊 Contanos tus preferencias y te enviamos opciones dentro de tu presupuesto."
        
        else:
            # Usar GPT para respuestas inteligentes
            try:
                lead_context = {
                    "phone": lead.phone,
                    "name": lead.name,
                    "intent": lead.intent.value if lead.intent else None,
                    "zone": lead.zone,
                    "budget_text": lead.budget_text,
                    "property_type": lead.property_type.value if lead.property_type else None
                }
                response = await self.llm.generate_smart_response(message, lead_context)
                logger.info(f"GPT response generated for {lead.phone}")
            except Exception as e:
                logger.error(f"Error generating GPT response: {e}")
                response = "🤔 No encontré información sobre eso.\n\n"
                response += "Podés preguntarme sobre:\n"
                response += "• 📍 Dirección\n"
                response += "• 🕐 Horarios\n"
                response += "• 💳 Formas de pago\n"
                response += "• 📋 Requisitos\n"
                response += "• 📞 Contacto\n\n"
                response += "O si preferís, un asesor puede ayudarte. ¿Querés que te contacte uno?"
        
        self.wa.send_text_message(lead.phone, response)
    
    async def handle_consulting(self, lead: Lead, message: str):
        """Maneja consultas generales usando IA"""
        message_lower = message.lower()
        
        # Detectar despedida - finalizar conversación
        farewell_keywords = ["nada más", "nada mas", "eso es todo", "gracias", "muchas gracias", "ok gracias", "listo gracias", "perfecto gracias", "bueno gracias", "no nada", "no, nada", "no gracias", "no, gracias", "estoy bien", "todo bien"]
        if any(kw in message_lower for kw in farewell_keywords):
            response = f"¡Perfecto {lead.name or ''}! 😊\n\n"
            response += "Gracias por contactarnos. Cualquier cosa que necesites, escribinos.\n\n"
            response += "¡Que tengas un excelente día! 🏠"
            self.wa.send_text_message(lead.phone, response)
            # Volver a estado COMPLETED
            lead.flow_stage = FlowStage.COMPLETED
            return
        
        # Si explícitamente quiere buscar/agendar (mensajes cortos que son comandos)
        short_commands = ["buscar propiedad", "quiero buscar", "agendar cita", "nueva búsqueda"]
        if any(cmd in message_lower for cmd in short_commands) and len(message) < 30:
            lead.flow_stage = FlowStage.WELCOME
            await self.handle_welcome(lead, message)
            return
        
        # Primero intentar con FAQs predefinidas
        if self.is_faq_question(message):
            await self.handle_faq(lead, message)
            return
        
        # Usar GPT para respuestas inteligentes
        try:
            lead_context = {
                "phone": lead.phone,
                "name": lead.name,
                "intent": lead.intent.value if lead.intent else None,
                "zone": lead.zone,
                "budget_text": lead.budget_text,
                "property_type": lead.property_type.value if lead.property_type else None
            }
            response = await self.llm.generate_smart_response(message, lead_context)
            logger.info(f"GPT consulting response for {lead.phone}")
            
            # Agregar opciones al final (solo si no es muy larga la respuesta)
            if len(response) < 500:
                response += "\n\n¿Hay algo más en lo que pueda ayudarte?"
            
        except Exception as e:
            logger.error(f"Error in consulting GPT: {e}")
            response = "Disculpá, no pude procesar tu consulta. ¿Querés que te conecte con un asesor?"
        
        self.wa.send_text_message(lead.phone, response)


    async def handle_nps_response(self, lead: Lead, message: str, db):
        """Maneja respuesta de encuesta NPS"""
        score_map = {
            "nps_9_10": {"score": 10, "category": "promoter"},
            "nps_7_8": {"score": 8, "category": "passive"},
            "nps_1_6": {"score": 5, "category": "detractor"}
        }
        
        nps_data = score_map.get(message.lower(), {"score": 0, "category": "unknown"})
        
        # Guardar respuesta NPS
        await db.leads.update_one(
            {"phone": lead.phone},
            {"$set": {
                "nps_score": nps_data["score"],
                "nps_category": nps_data["category"],
                "nps_responded_at": datetime.utcnow().isoformat()
            }}
        )
        
        # Guardar en colección de NPS para métricas
        await db.nps_responses.insert_one({
            "lead_phone": lead.phone,
            "lead_name": lead.name,
            "score": nps_data["score"],
            "category": nps_data["category"],
            "created_at": datetime.utcnow()
        })
        
        if nps_data["category"] == "promoter":
            response = f"¡Muchísimas gracias {lead.name or ''}! 🙏💙\n\n"
            response += "Nos alegra mucho que hayas tenido una buena experiencia.\n\n"
            response += "Si conocés a alguien que esté buscando propiedad, ¡no dudes en recomendarnos!"
        elif nps_data["category"] == "passive":
            response = f"¡Gracias por tu feedback {lead.name or ''}! 🙏\n\n"
            response += "¿Hay algo que podríamos haber hecho mejor? Tu opinión nos ayuda a mejorar."
        else:
            response = f"Gracias por tu honestidad {lead.name or ''}. 🙏\n\n"
            response += "Lamentamos que la experiencia no haya sido la mejor. ¿Podrías contarnos qué podríamos mejorar?\n\n"
            response += "Tu feedback es muy importante para nosotros."
        
        self.wa.send_text_message(lead.phone, response)
        logger.info(f"NPS response recorded for {lead.phone}: {nps_data['category']}")

    async def send_property_location(self, lead: Lead):
        """Envía ubicación de la propiedad"""
        # Por ahora usa una ubicación de ejemplo
        # En producción, se obtendría de la propiedad asociada al lead
        
        # Ubicación de ejemplo (Buenos Aires centro)
        latitude = -34.6037
        longitude = -58.3816
        name = "Propiedad - InmoBot"
        address = "Buenos Aires, Argentina"
        
        # Verificar si el lead tiene una propiedad asociada con ubicación
        # Esto se puede expandir para obtener la ubicación real
        
        message = "📍 Aquí te comparto la ubicación de la propiedad:\n\n"
        message += f"📌 {address}\n\n"
        message += "También podés buscarla en Google Maps."
        
        # Enviar mensaje de texto primero
        self.wa.send_text_message(lead.phone, message)
        
        # Enviar ubicación (si el servicio lo soporta)
        try:
            self.wa.send_location(lead.phone, latitude, longitude, name, address)
            logger.info(f"Location sent to {lead.phone}")
        except Exception as e:
            logger.warning(f"Could not send location to {lead.phone}: {e}")
            # Enviar link de Google Maps como fallback
            maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
            self.wa.send_text_message(lead.phone, f"🗺️ Ver en Google Maps: {maps_link}")
