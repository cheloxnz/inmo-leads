import asyncio
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from email_service import EmailService

logger = logging.getLogger(__name__)

class ScheduledTasks:
    """Gestor de tareas programadas para recordatorios y reactivaciones"""
    
    def __init__(self, db: AsyncIOMotorDatabase, email_service: EmailService):
        self.db = db
        self.email = email_service
        self.running = False
    
    async def start(self):
        """Inicia las tareas programadas"""
        self.running = True
        logger.info("Tareas programadas iniciadas")
        
        asyncio.create_task(self.check_appointment_reminders())
        asyncio.create_task(self.check_warm_lead_reactivation())
    
    async def check_appointment_reminders(self):
        """Revisa citas próximas y envía recordatorios 24hs antes"""
        while self.running:
            try:
                now = datetime.utcnow()
                tomorrow = now + timedelta(hours=24)
                tomorrow_plus_1h = now + timedelta(hours=25)
                
                config = await self.db.bot_config.find_one({})
                reminder_hours = config.get('appointment_reminder_hours', 24) if config else 24
                
                leads = await self.db.leads.find({
                    "appointment_datetime": {
                        "$gte": tomorrow.isoformat(),
                        "$lt": tomorrow_plus_1h.isoformat()
                    },
                    "appointment_reminder_sent": {"$ne": True}
                }, {
                    "_id": 0,
                    "phone": 1,
                    "name": 1,
                    "appointment_datetime": 1,
                    "appointment_type": 1
                }).to_list(100)
                
                for lead in leads:
                    try:
                        logger.info(f"Enviando recordatorio de cita para lead {lead['phone']}")
                        success = await self.email.send_appointment_reminder(lead, reminder_hours)
                        
                        if success:
                            await self.db.leads.update_one(
                                {"phone": lead['phone']},
                                {"$set": {"appointment_reminder_sent": True}}
                            )
                    except Exception as e:
                        logger.error(f"Error enviando recordatorio para {lead['phone']}: {str(e)}")
                
                await asyncio.sleep(3600)
            
            except Exception as e:
                logger.error(f"Error en check_appointment_reminders: {str(e)}")
                await asyncio.sleep(3600)
    
    async def check_warm_lead_reactivation(self):
        """Revisa leads tibios sin actividad y envía reactivación"""
        while self.running:
            try:
                config = await self.db.bot_config.find_one({})
                reactivation_days = config.get('warm_lead_reactivation_days', 3) if config else 3
                
                cutoff_date = (datetime.utcnow() - timedelta(days=reactivation_days)).isoformat()
                
                leads = await self.db.leads.find({
                    "status": "warm",
                    "last_message_at": {"$lt": cutoff_date},
                    "$or": [
                        {"last_reactivation_email_at": {"$exists": False}},
                        {"last_reactivation_email_at": {"$lt": cutoff_date}}
                    ]
                }, {
                    "_id": 0,
                    "phone": 1,
                    "name": 1,
                    "zone": 1,
                    "property_type": 1
                }).to_list(50)
                
                for lead in leads:
                    try:
                        logger.info(f"Enviando reactivación para lead tibio {lead['phone']}")
                        success = await self.email.send_warm_lead_reactivation(lead)
                        
                        if success:
                            await self.db.leads.update_one(
                                {"phone": lead['phone']},
                                {"$set": {"last_reactivation_email_at": datetime.utcnow().isoformat()}}
                            )
                    except Exception as e:
                        logger.error(f"Error enviando reactivación para {lead['phone']}: {str(e)}")
                
                await asyncio.sleep(7200)
            
            except Exception as e:
                logger.error(f"Error en check_warm_lead_reactivation: {str(e)}")
                await asyncio.sleep(7200)
    
    async def stop(self):
        """Detiene las tareas programadas"""
        self.running = False
        logger.info("Tareas programadas detenidas")
