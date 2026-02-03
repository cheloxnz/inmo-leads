import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
from models import EmailType, EmailLog

logger = logging.getLogger(__name__)

class EmailService:
    """Servicio para envío de notificaciones por email usando Gmail SMTP"""
    
    def __init__(self, db=None):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL")
        self.from_name = os.getenv("SMTP_FROM_NAME", "InmoBot AI")
        self.notification_emails = os.getenv("NOTIFICATION_EMAILS", "").split(",")
        self.db = db
        
        if not self.smtp_username or not self.smtp_password:
            logger.warning("Credenciales SMTP no configuradas. Emails deshabilitados.")
    
    async def send_email(self, to_emails: List[str], subject: str, html_body: str, text_body: Optional[str] = None, email_type: EmailType = EmailType.TEST, lead_phone: Optional[str] = None) -> bool:
        """Envía email usando Gmail SMTP y registra en log"""
        if not self.smtp_username or not self.smtp_password:
            logger.warning("No se puede enviar email: credenciales no configuradas")
            await self._log_email(email_type, to_emails, subject, False, "Credenciales no configuradas", lead_phone)
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ", ".join(to_emails)
            msg['Subject'] = subject
            
            if text_body:
                part1 = MIMEText(text_body, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(html_body, 'html')
            msg.attach(part2)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email enviado exitosamente a {to_emails}")
            await self._log_email(email_type, to_emails, subject, True, None, lead_phone)
            return True
        
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            await self._log_email(email_type, to_emails, subject, False, str(e), lead_phone)
            return False
    
    async def _log_email(self, email_type: EmailType, recipients: List[str], subject: str, success: bool, error: Optional[str], lead_phone: Optional[str]):
        """Registra envío de email en base de datos"""
        if not self.db:
            return
        
        try:
            log = EmailLog(
                email_type=email_type,
                recipient_emails=recipients,
                lead_phone=lead_phone,
                subject=subject,
                success=success,
                error_message=error
            )
            log_dict = log.model_dump()
            log_dict["sent_at"] = log.sent_at.isoformat()
            
            await self.db.email_logs.insert_one(log_dict)
        except Exception as e:
            logger.error(f"Error logging email: {str(e)}")
    
    async def send_hot_lead_notification(self, lead_data: dict) -> bool:
        """Envía notificación de lead caliente a los asesores"""
        if not self.notification_emails or not self.notification_emails[0]:
            logger.warning("No hay emails configurados para notificaciones")
            return False
        
        phone = lead_data.get('phone', 'N/A')
        name = lead_data.get('name') or 'Sin nombre'
        intent = lead_data.get('intent', 'N/A')
        zone = lead_data.get('zone', 'N/A')
        budget = lead_data.get('budget_text', 'N/A')
        property_type = lead_data.get('property_type', 'N/A')
        bedrooms = lead_data.get('bedrooms', 'N/A')
        urgency = lead_data.get('urgency', 'N/A')
        score = lead_data.get('score', 0)
        appointment = lead_data.get('appointment_datetime')
        
        subject = f"🔥 LEAD CALIENTE - Score {score}/12"
        
        text_body = f"""LEAD CALIENTE DETECTADO

Nombre: {name}
Teléfono: {phone}
Intención: {intent}
Zona: {zone}
Presupuesto: {budget}
Tipo: {property_type}
Dormitorios: {bedrooms}
Urgencia: {urgency}
Score: {score}/12
"""
        
        if appointment:
            if isinstance(appointment, str):
                appointment = datetime.fromisoformat(appointment)
            text_body += f"\nCita agendada: {appointment.strftime('%d/%m/%Y %H:%M')}hs"
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .info-row {{ margin: 15px 0; padding: 12px; background: white; border-radius: 8px; border-left: 4px solid #ef4444; }}
        .label {{ font-weight: bold; color: #6b7280; font-size: 12px; text-transform: uppercase; }}
        .value {{ color: #111827; font-size: 16px; margin-top: 4px; }}
        .score {{ background: #ef4444; color: white; padding: 8px 16px; border-radius: 20px; display: inline-block; font-weight: bold; margin-top: 10px; }}
        .appointment {{ background: #10b981; color: white; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center; }}
        .footer {{ text-align: center; margin-top: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔥 LEAD CALIENTE DETECTADO</h1>
            <div class="score">Score: {score}/12</div>
        </div>
        <div class="content">
            <div class="info-row">
                <div class="label">Nombre</div>
                <div class="value">{name}</div>
            </div>
            <div class="info-row">
                <div class="label">Teléfono</div>
                <div class="value">{phone}</div>
            </div>
            <div class="info-row">
                <div class="label">Intención</div>
                <div class="value">{intent}</div>
            </div>
            <div class="info-row">
                <div class="label">Zona</div>
                <div class="value">{zone}</div>
            </div>
            <div class="info-row">
                <div class="label">Presupuesto</div>
                <div class="value">{budget}</div>
            </div>
            <div class="info-row">
                <div class="label">Tipo de Propiedad</div>
                <div class="value">{property_type} - {bedrooms} dormitorios</div>
            </div>
            <div class="info-row">
                <div class="label">Urgencia</div>
                <div class="value">{urgency}</div>
            </div>"""
        
        if appointment:
            if isinstance(appointment, str):
                appointment = datetime.fromisoformat(appointment)
            appointment_str = appointment.strftime('%d/%m/%Y a las %H:%M')
            html_body += f"""
            <div class="appointment">
                <strong>📅 Cita Agendada</strong><br>
                {appointment_str}hs
            </div>"""
        
        html_body += f"""
            <div class="footer">
                <p>Este es un lead caliente que requiere atención inmediata.</p>
                <p><strong>InmoBot AI</strong> - Sistema de Calificación Automática</p>
            </div>
        </div>
    </div>
</body>
</html>"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.HOT_LEAD,
            lead_phone=phone
        )
    
    async def send_appointment_reminder(self, lead_data: dict, hours_before: int = 24) -> bool:
        """Envía recordatorio de cita programada"""
        if not self.notification_emails or not self.notification_emails[0]:
            return False
        
        name = lead_data.get('name') or 'Cliente'
        phone = lead_data.get('phone', 'N/A')
        appointment = lead_data.get('appointment_datetime')
        appointment_type = lead_data.get('appointment_type', 'reunión')
        
        if not appointment:
            return False
        
        if isinstance(appointment, str):
            appointment = datetime.fromisoformat(appointment)
        
        subject = f"📅 Recordatorio: Cita con {name} en {hours_before}hs"
        
        text_body = f"""RECORDATORIO DE CITA

Cliente: {name}
Teléfono: {phone}
Tipo: {appointment_type}
Fecha: {appointment.strftime('%d/%m/%Y %H:%M')}hs

La cita es en {hours_before} horas.
"""
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .appointment-box {{ background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #3b82f6; margin: 20px 0; }}
        .time {{ font-size: 24px; font-weight: bold; color: #3b82f6; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📅 RECORDATORIO DE CITA</h1>
        </div>
        <div class="content">
            <div class="appointment-box">
                <p><strong>Cliente:</strong> {name}</p>
                <p><strong>Teléfono:</strong> {phone}</p>
                <p><strong>Tipo:</strong> {appointment_type}</p>
                <p class="time">{appointment.strftime('%d/%m/%Y a las %H:%M')}hs</p>
            </div>
            <p style="text-align: center; color: #6b7280;">La cita es en <strong>{hours_before} horas</strong></p>
        </div>
    </div>
</body>
</html>"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.APPOINTMENT_REMINDER,
            lead_phone=phone
        )
    
    async def send_warm_lead_reactivation(self, lead_data: dict) -> bool:
        """Envía email para reactivar lead tibio sin actividad"""
        if not self.notification_emails or not self.notification_emails[0]:
            return False
        
        phone = lead_data.get('phone', 'N/A')
        name = lead_data.get('name') or 'Cliente'
        zone = lead_data.get('zone', '')
        property_type = lead_data.get('property_type', 'propiedad')
        
        subject = f"🟡 Lead Tibio sin actividad - {name}"
        
        text_body = f"""REACTIVACIÓN DE LEAD TIBIO

Cliente: {name}
Teléfono: {phone}
Zona: {zone}
Tipo: {property_type}

Este lead lleva 3 días sin actividad. Considera enviarle un mensaje por WhatsApp con novedades.
"""
        
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }}
        .lead-box {{ background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #f59e0b; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🟡 LEAD TIBIO - REACTIVACIÓN</h1>
        </div>
        <div class="content">
            <div class="lead-box">
                <p><strong>Cliente:</strong> {name}</p>
                <p><strong>Teléfono:</strong> {phone}</p>
                <p><strong>Zona:</strong> {zone}</p>
                <p><strong>Tipo:</strong> {property_type}</p>
            </div>
            <p style="text-align: center; color: #6b7280;">Este lead lleva <strong>3 días sin actividad</strong>. Considera contactarlo con novedades.</p>
        </div>
    </div>
</body>
</html>"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.WARM_LEAD_REACTIVATION,
            lead_phone=phone
        )
    
    async def test_email(self) -> bool:
        """Envía email de prueba para verificar configuración"""
        if not self.notification_emails or not self.notification_emails[0]:
            logger.error("No hay emails configurados para notificaciones")
            return False
        
        subject = "✅ Test InmoBot AI - Configuración exitosa"
        
        html_body = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; border-radius: 10px; }
        .content { padding: 30px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Configuración Exitosa</h1>
        </div>
        <div class="content">
            <p>¡Felicitaciones! El sistema de notificaciones por email está funcionando correctamente.</p>
            <p>Recibirás alertas automáticas cuando:</p>
            <ul>
                <li>🔥 Se detecte un lead caliente (Score ≥ 7)</li>
                <li>📅 Se agende una cita</li>
                <li>🟡 Leads tibios necesiten reactivación (3 días sin actividad)</li>
                <li>⏰ Recordatorios de citas 24hs antes</li>
            </ul>
            <p><strong>InmoBot AI</strong> - Sistema de Calificación Automática</p>
        </div>
    </div>
</body>
</html>"""
        
        text_body = """Configuración Exitosa

El sistema de notificaciones por email está funcionando correctamente.

Recibirás alertas automáticas cuando se detecten leads calientes, citas agendadas y leads tibios.

InmoBot AI - Sistema de Calificación Automática
"""
        
        return await self.send_email(
            to_emails=[email.strip() for email in self.notification_emails if email.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.TEST
        )
