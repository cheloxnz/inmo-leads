"""
Servicio de tareas programadas para mensajes automáticos
- Recordatorio 24hs antes de cita
- Seguimiento post-visita 48hs después
- Encuesta NPS
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import os

logger = logging.getLogger(__name__)

class ScheduledMessagesService:
    def __init__(self, wa_service, db):
        self.wa = wa_service
        self.db = db
        self.running = False
    
    async def start(self):
        """Inicia el servicio de mensajes programados"""
        self.running = True
        logger.info("🕐 Servicio de mensajes programados iniciado")
        
        while self.running:
            try:
                await self.check_reminders()
                await self.check_follow_ups()
                await self.check_nps_surveys()
            except Exception as e:
                logger.error(f"Error en scheduled messages: {e}")
            
            # Esperar 5 minutos antes de la próxima verificación
            await asyncio.sleep(300)
    
    async def stop(self):
        """Detiene el servicio"""
        self.running = False
        logger.info("🛑 Servicio de mensajes programados detenido")
    
    async def check_reminders(self):
        """Envía recordatorios 24hs antes de la cita"""
        now = datetime.utcnow()
        reminder_window_start = now + timedelta(hours=23, minutes=30)
        reminder_window_end = now + timedelta(hours=24, minutes=30)
        
        # Buscar citas en las próximas 24hs que no hayan recibido recordatorio
        leads = await self.db.leads.find({
            "appointment_datetime": {
                "$gte": reminder_window_start,
                "$lte": reminder_window_end
            },
            "reminder_sent": {"$ne": True},
            "status": {"$nin": ["cancelled", "completed"]}
        }).to_list(100)
        
        for lead in leads:
            try:
                appointment = lead.get("appointment_datetime")
                if appointment:
                    await self.send_reminder(lead, appointment)
                    
                    # Marcar como enviado
                    await self.db.leads.update_one(
                        {"_id": lead["_id"]},
                        {"$set": {"reminder_sent": True}}
                    )
                    logger.info(f"📅 Recordatorio enviado a {lead.get('phone')}")
            except Exception as e:
                logger.error(f"Error enviando recordatorio a {lead.get('phone')}: {e}")
    
    async def send_reminder(self, lead: dict, appointment: datetime):
        """Envía mensaje de recordatorio"""
        name = lead.get("name", "")
        date_str = appointment.strftime("%d/%m/%Y")
        time_str = appointment.strftime("%H:%M")
        
        message = f"¡Hola {name}! 👋\n\n"
        message += f"Te recordamos que tenés una cita agendada para **mañana**:\n\n"
        message += f"📅 Fecha: {date_str}\n"
        message += f"🕐 Hora: {time_str}\n\n"
        message += "¿Confirmás tu asistencia?"
        
        buttons = [
            {"type": "reply", "reply": {"id": "confirmar_cita", "title": "✅ Confirmo"}},
            {"type": "reply", "reply": {"id": "opcion_reagendar", "title": "📅 Reagendar"}},
            {"type": "reply", "reply": {"id": "opcion_cancelar", "title": "❌ Cancelar"}}
        ]
        
        self.wa.send_interactive_buttons(lead.get("phone"), message, buttons)
    
    async def check_follow_ups(self):
        """Envía seguimiento 48hs después de la cita"""
        now = datetime.utcnow()
        follow_up_window_start = now - timedelta(hours=48, minutes=30)
        follow_up_window_end = now - timedelta(hours=47, minutes=30)
        
        # Buscar citas que ocurrieron hace 48hs
        leads = await self.db.leads.find({
            "appointment_datetime": {
                "$gte": follow_up_window_start,
                "$lte": follow_up_window_end
            },
            "follow_up_sent": {"$ne": True},
            "status": {"$nin": ["cancelled"]}
        }).to_list(100)
        
        for lead in leads:
            try:
                await self.send_follow_up(lead)
                
                # Marcar como enviado
                await self.db.leads.update_one(
                    {"_id": lead["_id"]},
                    {"$set": {"follow_up_sent": True}}
                )
                logger.info(f"📨 Follow-up enviado a {lead.get('phone')}")
            except Exception as e:
                logger.error(f"Error enviando follow-up a {lead.get('phone')}: {e}")
    
    async def send_follow_up(self, lead: dict):
        """Envía mensaje de seguimiento post-visita"""
        name = lead.get("name", "")
        
        message = f"¡Hola {name}! 👋\n\n"
        message += "Hace unos días tuviste una visita/llamada con nosotros.\n\n"
        message += "¿Cómo te fue? ¿Encontraste lo que buscabas?"
        
        buttons = [
            {"type": "reply", "reply": {"id": "follow_up_interesado", "title": "🏠 Sigo interesado"}},
            {"type": "reply", "reply": {"id": "follow_up_otra_visita", "title": "📅 Quiero otra visita"}},
            {"type": "reply", "reply": {"id": "follow_up_no_gracias", "title": "No por ahora"}}
        ]
        
        self.wa.send_interactive_buttons(lead.get("phone"), message, buttons)
    
    async def check_nps_surveys(self):
        """Envía encuesta NPS 7 días después de cerrar"""
        now = datetime.utcnow()
        nps_window_start = now - timedelta(days=7, hours=1)
        nps_window_end = now - timedelta(days=6, hours=23)
        
        # Buscar leads cerrados hace 7 días
        leads = await self.db.leads.find({
            "status": "completed",
            "completed_at": {
                "$gte": nps_window_start,
                "$lte": nps_window_end
            },
            "nps_sent": {"$ne": True}
        }).to_list(100)
        
        for lead in leads:
            try:
                await self.send_nps_survey(lead)
                
                await self.db.leads.update_one(
                    {"_id": lead["_id"]},
                    {"$set": {"nps_sent": True}}
                )
                logger.info(f"📊 Encuesta NPS enviada a {lead.get('phone')}")
            except Exception as e:
                logger.error(f"Error enviando NPS a {lead.get('phone')}: {e}")
    
    async def send_nps_survey(self, lead: dict):
        """Envía encuesta de satisfacción NPS"""
        name = lead.get("name", "")
        
        message = f"¡Hola {name}! 👋\n\n"
        message += "Nos encantaría conocer tu opinión sobre el servicio que recibiste.\n\n"
        message += "Del 1 al 10, ¿qué tan probable es que nos recomiendes a un amigo o conocido?\n\n"
        message += "🔴 1-6: Poco probable\n"
        message += "🟡 7-8: Probable\n"
        message += "🟢 9-10: Muy probable"
        
        buttons = [
            {"type": "reply", "reply": {"id": "nps_9_10", "title": "🟢 9-10 Excelente"}},
            {"type": "reply", "reply": {"id": "nps_7_8", "title": "🟡 7-8 Bueno"}},
            {"type": "reply", "reply": {"id": "nps_1_6", "title": "🔴 1-6 Regular"}}
        ]
        
        self.wa.send_interactive_buttons(lead.get("phone"), message, buttons)


class BroadcastService:
    """Servicio para enviar mensajes masivos"""
    
    def __init__(self, wa_service, db):
        self.wa = wa_service
        self.db = db
    
    async def send_broadcast(
        self,
        message: str,
        filters: dict = None,
        scheduled_at: datetime = None
    ) -> dict:
        """
        Envía mensaje broadcast a múltiples leads
        
        Args:
            message: Mensaje a enviar
            filters: Filtros para seleccionar leads (zona, intención, etc.)
            scheduled_at: Fecha/hora programada (None = enviar ahora)
        """
        # Construir query de filtros
        query = {"status": {"$nin": ["cancelled"]}}
        
        if filters:
            if filters.get("zone"):
                query["zone"] = {"$regex": filters["zone"], "$options": "i"}
            if filters.get("intent"):
                query["intent"] = filters["intent"]
            if filters.get("status"):
                query["status"] = filters["status"]
            if filters.get("tags"):
                query["tags"] = {"$in": filters["tags"]}
        
        # Obtener leads
        leads = await self.db.leads.find(query, {"phone": 1, "name": 1}).to_list(500)
        
        if scheduled_at and scheduled_at > datetime.utcnow():
            # Guardar para envío programado
            broadcast_id = await self.db.broadcasts.insert_one({
                "message": message,
                "filters": filters,
                "scheduled_at": scheduled_at,
                "status": "scheduled",
                "total_recipients": len(leads),
                "sent_count": 0,
                "created_at": datetime.utcnow()
            })
            return {
                "status": "scheduled",
                "broadcast_id": str(broadcast_id.inserted_id),
                "scheduled_at": scheduled_at.isoformat(),
                "total_recipients": len(leads)
            }
        
        # Enviar ahora
        sent_count = 0
        failed_count = 0
        
        for lead in leads:
            try:
                personalized_message = message.replace("{nombre}", lead.get("name", ""))
                self.wa.send_text_message(lead["phone"], personalized_message)
                sent_count += 1
                await asyncio.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.error(f"Error enviando broadcast a {lead['phone']}: {e}")
                failed_count += 1
        
        # Guardar registro
        await self.db.broadcasts.insert_one({
            "message": message,
            "filters": filters,
            "status": "completed",
            "total_recipients": len(leads),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "sent_at": datetime.utcnow()
        })
        
        return {
            "status": "completed",
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_recipients": len(leads)
        }
    
    async def get_broadcast_history(self, limit: int = 20) -> list:
        """Obtiene historial de broadcasts"""
        broadcasts = await self.db.broadcasts.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        for b in broadcasts:
            if b.get("scheduled_at"):
                b["scheduled_at"] = b["scheduled_at"].isoformat()
            if b.get("sent_at"):
                b["sent_at"] = b["sent_at"].isoformat()
            if b.get("created_at"):
                b["created_at"] = b["created_at"].isoformat()
        
        return broadcasts
