import logging
from typing import Dict, Optional
from models import Lead, FlowStage, LeadIntent, UrgencyLevel, FinancingType, PropertyType
from whatsapp_service import WhatsAppService
from llm_service import LLMService
from scoring import ScoringEngine
from email_service import EmailService
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class BotFlowManager:
    """Gestiona el flujo conversacional del bot"""
    
    def __init__(self, whatsapp_service: WhatsAppService, llm_service: LLMService, email_service: EmailService):
        self.wa = whatsapp_service
        self.llm = llm_service
        self.email = email_service
    
    async def process_message(self, lead: Lead, message_text: str, db) -> Lead:
        """Procesa mensaje según el estado del flujo"""
        
        # Guardar mensaje en historial
        lead.conversation_history.append({
            "from": "customer",
            "text": message_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Procesar según etapa del flujo
        if lead.flow_stage == FlowStage.WELCOME:
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
        elif "inversion" in message_lower or "inversión" in message_lower or message_lower == "3":
            lead.intent = LeadIntent.INVERSION
        else:
            result = await self.llm.classify_intent(message)
            intent_str = result.get("intent", "sin_definir")
            if intent_str in ["comprar", "alquilar", "inversion"]:
                lead.intent = LeadIntent(intent_str)
            else:
                lead.intent = LeadIntent.SIN_DEFINIR
        
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
        """Maneja zona de interés"""
        zone = await self.llm.extract_zone(message)
        
        if zone:
            lead.zone = zone
            response = f"Genial, {zone}. ¿Cuál es tu presupuesto aproximado? (en USD)\n\nEjemplo: 150.000 USD o 100k-200k"
            self.wa.send_text_message(lead.phone, response)
            lead.flow_stage = FlowStage.BUDGET
        else:
            response = "No pude identificar la zona. ¿Podés escribirla de nuevo?\n\nEjemplo: Palermo, Belgrano, etc."
            self.wa.send_text_message(lead.phone, response)
    
    async def handle_budget(self, lead: Lead, message: str):
        """Maneja presupuesto"""
        budget = await self.llm.extract_budget(message)
        
        if budget or "no" in message.lower() or "sin" in message.lower():
            lead.budget_text = budget if budget else "A definir"
            
            response = "¿Qué tipo de propiedad te interesa?"
            buttons = [
                {"type": "reply", "reply": {"id": "departamento", "title": "Departamento"}},
                {"type": "reply", "reply": {"id": "casa", "title": "Casa"}},
                {"type": "reply", "reply": {"id": "ph", "title": "PH"}}
            ]
            
            self.wa.send_interactive_buttons(lead.phone, response, buttons)
            lead.flow_stage = FlowStage.PROPERTY_TYPE
        else:
            response = "No pude identificar el presupuesto. ¿Podés indicarlo de nuevo?\n\nEjemplo: 200.000 USD"
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
    
    async def handle_select_day(self, lead: Lead, message: str):
        """Maneja selección de día"""
        response = "¿Qué horario preferís?\n\nHorarios disponibles:\nLun-Vie: 9-20hs\nSáb: 10-14hs"
        
        buttons = [
            {"type": "reply", "reply": {"id": "manana", "title": "Mañana (9-12hs)"}},
            {"type": "reply", "reply": {"id": "tarde", "title": "Tarde (14-17hs)"}},
            {"type": "reply", "reply": {"id": "noche", "title": "Noche (17-20hs)"}}
        ]
        
        self.wa.send_interactive_buttons(lead.phone, response, buttons)
        lead.flow_stage = FlowStage.SELECT_TIME
    
    async def handle_select_time(self, lead: Lead, message: str):
        """Maneja selección de horario y confirma"""
        message_lower = message.lower()
        
        now = datetime.now()
        appointment_date = now + timedelta(days=1)
        
        if "manana" in message_lower or "mañana" in message_lower:
            appointment_date = appointment_date.replace(hour=10, minute=0)
        elif "tarde" in message_lower:
            appointment_date = appointment_date.replace(hour=15, minute=0)
        else:
            appointment_date = appointment_date.replace(hour=18, minute=0)
        
        lead.appointment_datetime = appointment_date
        
        response = f"¡Perfecto! ✅\n\nTu {lead.appointment_type} quedó agendada para:\n{appointment_date.strftime('%d/%m/%Y a las %H:%M')}\n\nUn asesor se va a comunicar con vos para confirmar. ¡Gracias! 🙌"
        
        self.wa.send_text_message(lead.phone, response)
        lead.flow_stage = FlowStage.CONFIRMATION
        
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