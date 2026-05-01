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
        if self.db is None:
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
    
    async def send_new_referral_commission(
        self,
        to_email: str,
        referrer_business_name: str,
        referred_business_name: str,
        amount_per_month_usd: float,
        active_count: int,
        active_credit_capped_usd: float,
        plan_price_usd: float,
        is_capped: bool,
    ) -> bool:
        """Notifica al referrer que ganó una nueva comisión recurrente."""
        if not to_email:
            return False
        subject = f"🎉 Conseguiste un nuevo referido — ${amount_per_month_usd:.0f}/mes ganados"
        cap_note = (
            f"<p style='margin-top:14px;color:#047857;'><strong>¡Tu suscripción es gratis!</strong> "
            f"Llegaste al tope del plan (${plan_price_usd:.0f}/mes). El descuento se aplica al 100%.</p>"
            if is_capped else ""
        )
        text_body = (
            f"¡Hola {referrer_business_name}!\n\n"
            f"Conseguiste un nuevo referido: {referred_business_name}.\n"
            f"Te genera ${amount_per_month_usd:.0f}/mes de descuento durante 12 meses.\n\n"
            f"Tu crédito activo este mes: -${active_credit_capped_usd:.0f} ({active_count} referidos activos).\n"
            f"Se descontará automáticamente en tu próxima factura.\n\n"
            f"Compartí tu link de referido para sumar más:\n"
            f"https://inmobot-preview.preview.emergentagent.com/signup\n\n"
            f"InmoBot AI"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; line-height:1.55; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:600px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#10b981 0%,#059669 100%); color:#fff; padding:32px 28px; text-align:center; }}
  .header h1 {{ margin:0; font-size:22px; }}
  .header .amount {{ font-size:42px; font-weight:800; margin-top:6px; letter-spacing:-0.02em; }}
  .header .subtitle {{ opacity:0.92; font-size:14px; margin-top:6px; }}
  .content {{ padding:28px; }}
  .stats {{ display:flex; gap:12px; margin:18px 0; flex-wrap:wrap; }}
  .stat {{ flex:1 1 140px; background:#ecfdf5; border:1px solid #6ee7b7; border-radius:10px; padding:14px; }}
  .stat .lbl {{ font-size:11px; color:#047857; text-transform:uppercase; letter-spacing:0.05em; font-weight:600; }}
  .stat .val {{ font-size:24px; font-weight:700; color:#065f46; margin-top:4px; }}
  .footer {{ padding:18px 28px; color:#6b7280; font-size:12px; text-align:center; border-top:1px solid #e5e7eb; }}
</style></head>
<body>
  <div class='container'>
    <div class='header'>
      <h1>🎉 Conseguiste un nuevo referido</h1>
      <div class='amount'>+${amount_per_month_usd:.0f}/mes</div>
      <div class='subtitle'>durante los próximos 12 meses</div>
    </div>
    <div class='content'>
      <p>¡Hola <strong>{referrer_business_name}</strong>!</p>
      <p><strong>{referred_business_name}</strong> se sumó a InmoBot con tu link de referido y ya está pagando su suscripción 🚀</p>
      <div class='stats'>
        <div class='stat'><div class='lbl'>Crédito activo</div><div class='val'>-${active_credit_capped_usd:.0f}</div></div>
        <div class='stat'><div class='lbl'>Referidos activos</div><div class='val'>{active_count}</div></div>
      </div>
      <p style='color:#6b7280; font-size:14px;'>El descuento se aplica automáticamente en tu próxima factura. No tenés que hacer nada.</p>
      {cap_note}
    </div>
    <div class='footer'>
      Querés ganar más? Compartí tu link de referido desde el panel de Facturación.<br>
      InmoBot AI · Programa de referidos
    </div>
  </div>
</body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.NEW_REFERRAL_COMMISSION,
        )

    async def send_trial_ending_soon(
        self,
        to_email: str,
        business_name: str,
        days_left: int,
        upgrade_url: str,
    ) -> bool:
        """Aviso al admin cuando faltan pocos días al trial."""
        if not to_email:
            return False
        subject = f"⏰ Tu trial de InmoBot termina en {days_left} {'día' if days_left==1 else 'días'}"
        text_body = (
            f"Hola {business_name},\n\n"
            f"Tu período de prueba gratuita termina en {days_left} días.\n"
            f"Suscribite ahora para no perder tu bot, leads y configuración:\n{upgrade_url}\n\n"
            f"InmoBot AI"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><style>
  body {{ font-family: -apple-system, Arial, sans-serif; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:560px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%); color:#fff; padding:28px; text-align:center; }}
  .content {{ padding:28px; line-height:1.55; }}
  .cta {{ display:inline-block; padding:12px 22px; background:#6366f1; color:#fff; text-decoration:none; border-radius:8px; font-weight:600; margin-top:14px; }}
</style></head>
<body><div class='container'>
  <div class='header'><h1 style='margin:0;font-size:22px;'>⏰ Tu trial termina pronto</h1></div>
  <div class='content'>
    <p>Hola <strong>{business_name}</strong>,</p>
    <p>Tu período de prueba gratuita termina en <strong>{days_left} {'día' if days_left==1 else 'días'}</strong>.</p>
    <p>No pierdas el bot que construiste, los leads que ya generaste ni tu configuración. Activá tu plan en 1 minuto:</p>
    <p style='text-align:center;'><a class='cta' href='{upgrade_url}'>Suscribirme ahora</a></p>
    <p style='color:#6b7280;font-size:13px;margin-top:24px;'>Si tenés dudas, respondé este mail y te ayudamos.</p>
  </div>
</div></body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.TRIAL_ENDING_SOON,
        )

    async def send_trial_halfway(
        self,
        to_email: str,
        business_name: str,
        days_left: int,
        upgrade_url: str,
    ) -> bool:
        """Check-in a mitad del trial (día 3 de 7). Más engagement que upsell."""
        if not to_email:
            return False
        subject = f"👋 ¿Cómo va tu experiencia con InmoBot, {business_name}?"
        text_body = (
            f"Hola {business_name},\n\n"
            f"Ya pasaste la mitad de tu trial. Te quedan {days_left} días.\n"
            f"Si ya configuraste WhatsApp y tenés leads entrando, vas perfecto.\n"
            f"Si aún no conectaste tu número, te recomendamos hacerlo hoy — "
            f"podés empezar a recibir mensajes en 5 minutos.\n\n"
            f"Activar tu plan: {upgrade_url}\n\n"
            f"¿Dudas? Respondé este email.\n\n— Equipo InmoBot"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>
  body {{ font-family:-apple-system,Arial,sans-serif; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:560px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; padding:28px; text-align:center; }}
  .content {{ padding:28px; line-height:1.6; color:#374151; font-size:14px; }}
  .tip {{ background:#f9fafb; border-left:3px solid #8b5cf6; padding:12px 16px; margin:16px 0; border-radius:4px; }}
  .cta {{ display:inline-block; padding:12px 22px; background:#6366f1; color:#fff !important; text-decoration:none; border-radius:8px; font-weight:600; }}
</style></head>
<body><div class='container'>
  <div class='header'><h1 style='margin:0;font-size:22px;'>Mitad de tu trial — ¿cómo va?</h1></div>
  <div class='content'>
    <p>Hola <strong>{business_name}</strong>,</p>
    <p>Ya pasaste la mitad de tu período de prueba. Te quedan <strong>{days_left} días</strong>.</p>
    <div class='tip'><strong>💡 Tip del día:</strong> Los clientes que cierran con InmoBot normalmente configuran su bot en las primeras 48 hs. Si aún no lo hiciste, te recomendamos hacerlo hoy.</div>
    <p>Activar tu plan en 1 minuto para que no se te corte nada cuando termine el trial:</p>
    <p style='text-align:center;margin:18px 0;'><a class='cta' href='{upgrade_url}'>Activar mi plan →</a></p>
    <p style='color:#6b7280;font-size:13px;'>¿Alguna duda? Respondé este email y te ayudamos.</p>
  </div>
</div></body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.TRIAL_ENDING_SOON,
        )

    async def send_trial_expired(
        self,
        to_email: str,
        business_name: str,
        upgrade_url: str,
    ) -> bool:
        """Email de trial expirado — última oportunidad antes de perder datos."""
        if not to_email:
            return False
        subject = f"🔒 Tu trial terminó — reactivá {business_name} antes de 30 días"
        text_body = (
            f"Hola {business_name},\n\n"
            f"Tu trial gratuito terminó.\n"
            f"Tus datos (leads, configuración, flujos) están guardados 30 días más.\n"
            f"Si reactivás antes de ese plazo, todo vuelve a funcionar al instante.\n"
            f"Pasados los 30 días se eliminan permanentemente.\n\n"
            f"Reactivar: {upgrade_url}\n\n"
            f"— Equipo InmoBot"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>
  body {{ font-family:-apple-system,Arial,sans-serif; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:560px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#ef4444,#dc2626); color:#fff; padding:28px; text-align:center; }}
  .content {{ padding:28px; line-height:1.6; color:#374151; font-size:14px; }}
  .warn {{ background:#fef2f2; border:1px solid #fee2e2; color:#991b1b; padding:14px 16px; border-radius:8px; margin:16px 0; font-size:13.5px; }}
  .cta {{ display:inline-block; padding:14px 26px; background:#dc2626; color:#fff !important; text-decoration:none; border-radius:10px; font-weight:700; }}
</style></head>
<body><div class='container'>
  <div class='header'><h1 style='margin:0;font-size:22px;'>🔒 Tu trial terminó</h1></div>
  <div class='content'>
    <p>Hola <strong>{business_name}</strong>,</p>
    <p>Tu período de prueba gratuito de 7 días finalizó. El bot está pausado y no procesa nuevos mensajes.</p>
    <div class='warn'>
      <strong>Importante:</strong> Tus datos (leads, configuración, flujos) quedan guardados <strong>30 días</strong>.
      Después se eliminan permanentemente.
    </div>
    <p>Si reactivás antes de que se cumpla el plazo, <strong>todo vuelve a funcionar en segundos</strong> — no perdés nada.</p>
    <p style='text-align:center;margin:20px 0;'><a class='cta' href='{upgrade_url}'>Reactivar mi cuenta →</a></p>
    <p style='color:#6b7280;font-size:13px;'>Si pensás que esto es un error, respondé este email y lo revisamos.</p>
  </div>
</div></body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.TRIAL_ENDING_SOON,
        )

    async def send_weekly_digest(
        self,
        to_email: str,
        business_name: str,
        stats: dict,
    ) -> bool:
        """Resumen semanal para retención.

        stats: {leads_new, leads_total, conversions, ai_messages, days,
                referral_credit_capped_usd, referral_active_count}
        """
        if not to_email:
            return False
        days = stats.get("days", 7)
        subject = f"📊 Tu resumen semanal de InmoBot — {business_name}"
        leads_new = stats.get("leads_new", 0)
        leads_total = stats.get("leads_total", 0)
        conversions = stats.get("conversions", 0)
        ai_msgs = stats.get("ai_messages", 0)
        savings = stats.get("referral_credit_capped_usd", 0)
        ref_active = stats.get("referral_active_count", 0)
        unmet_top = stats.get("unmet_top", []) or []
        text_body = (
            f"Resumen últimos {days} días para {business_name}:\n"
            f"- Leads nuevos: {leads_new}\n"
            f"- Conversiones: {conversions}\n"
            f"- Mensajes IA: {ai_msgs}\n"
            f"- Ahorro por referidos este mes: ${savings:.0f} ({ref_active} activos)\n"
        )
        if unmet_top:
            text_body += "\nProductos más pedidos pero AGOTADOS (reponé estos para activar avisos automáticos):\n"
            for i, u in enumerate(unmet_top, 1):
                text_body += f"  {i}. {u['name']} — {u['leads_count']} lead(s) esperando\n"

        # Sección HTML opcional para top productos
        unmet_html = ""
        if unmet_top:
            rows_html = ""
            for i, u in enumerate(unmet_top, 1):
                rows_html += (
                    f"<tr>"
                    f"<td style='padding:8px 10px;font-weight:700;color:#dc2626;width:24px;'>#{i}</td>"
                    f"<td style='padding:8px 10px;'><strong>{u['name']}</strong></td>"
                    f"<td style='padding:8px 10px;text-align:right;color:#6366f1;font-weight:700;'>"
                    f"{u['leads_count']} esperando</td>"
                    f"</tr>"
                )
            unmet_html = (
                "<div style='padding:0 28px 18px;'>"
                "<div style='background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:14px 16px;'>"
                "<div style='font-size:11px;color:#c2410c;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;'>"
                "🔥 Demanda Insatisfecha</div>"
                "<div style='font-size:13px;color:#7c2d12;margin:4px 0 12px;'>"
                "Estos productos están agotados pero leads los siguen pidiendo. "
                "Reponé el stock y InmoBot avisará automáticamente a los leads que esperaban.</div>"
                f"<table style='width:100%;border-collapse:collapse;font-size:13px;'>{rows_html}</table>"
                "</div></div>"
            )
        html_body = f"""<!DOCTYPE html>
<html><head><style>
  body {{ font-family:-apple-system,Arial,sans-serif; color:#111827; background:#f3f4f6; margin:0; }}
  .container {{ max-width:600px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%); color:#fff; padding:24px 28px; text-align:left; }}
  .stats {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:18px 28px; }}
  .stat {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:14px; }}
  .stat .lbl {{ font-size:11px; color:#6b7280; text-transform:uppercase; letter-spacing:0.05em; font-weight:600; }}
  .stat .val {{ font-size:22px; font-weight:700; color:#111827; margin-top:4px; }}
  .footer {{ padding:18px 28px; color:#6b7280; font-size:12px; }}
</style></head>
<body><div class='container'>
  <div class='header'><h1 style='margin:0;font-size:20px;'>📊 Tu resumen semanal</h1>
    <div style='opacity:0.9;font-size:13px;margin-top:4px;'>Últimos {days} días · {business_name}</div></div>
  <div class='stats'>
    <div class='stat'><div class='lbl'>Leads nuevos</div><div class='val'>{leads_new}</div></div>
    <div class='stat'><div class='lbl'>Conversiones</div><div class='val'>{conversions}</div></div>
    <div class='stat'><div class='lbl'>Mensajes IA</div><div class='val'>{ai_msgs}</div></div>
    <div class='stat'><div class='lbl'>Total leads</div><div class='val'>{leads_total}</div></div>
    <div class='stat' style='grid-column:1/-1; background:#ecfdf5; border-color:#6ee7b7;'>
      <div class='lbl' style='color:#047857;'>Ahorro por referidos este mes</div>
      <div class='val' style='color:#065f46;'>${savings:.0f} <span style='font-size:13px; color:#047857; font-weight:500;'>({ref_active} activos)</span></div>
    </div>
  </div>
  {unmet_html}
  <div class='footer'>Querés ver más? Iniciá sesión en tu dashboard de InmoBot.</div>
</div></body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.WEEKLY_DIGEST,
        )

    async def send_welcome_tenant(
        self,
        to_email: str,
        business_name: str,
        tenant_id: str,
        admin_name: Optional[str] = None,
    ) -> bool:
        """Email de bienvenida cuando un nuevo tenant se registra.

        Incluye CTA al dashboard, próximos pasos sugeridos (configurar WhatsApp,
        editar landing) y datos de soporte. Best-effort: no rompe el onboarding
        si SMTP no está configurado.
        """
        if not to_email:
            return False
        if not self.smtp_username or not self.smtp_password:
            logger.info(
                f"Welcome email skipped (SMTP no config) for tenant={tenant_id}"
            )
            return False

        first_name = (admin_name or business_name or "").split()[0] or "Hola"
        subject = f"🎉 Bienvenido a InmoBot, {business_name}"
        dashboard_url = "https://app.inmobot.com/dashboard"
        landing_url = f"https://app.inmobot.com/inicio/{tenant_id}"
        text_body = (
            f"Hola {first_name},\n\n"
            f"Tu workspace de InmoBot ya está listo para {business_name}.\n\n"
            f"Próximos pasos:\n"
            f"1. Configurá tu cuenta de WhatsApp Business → /config\n"
            f"2. Personalizá tu landing pública → {landing_url}\n"
            f"3. Probá el bot enviando un mensaje a tu WhatsApp\n\n"
            f"Tenés 7 días gratis. Cualquier cosa, contestá este email.\n\n"
            f"— Equipo InmoBot"
        )
        html_body = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>
  body {{ font-family:-apple-system,Arial,sans-serif; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:600px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); }}
  .header {{ background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#ec4899 100%); color:#fff; padding:32px 28px; text-align:left; }}
  .header h1 {{ margin:0; font-size:24px; font-weight:700; }}
  .header p {{ margin:6px 0 0 0; opacity:0.95; font-size:14px; }}
  .body {{ padding:28px; }}
  .greeting {{ font-size:16px; line-height:1.5; color:#111827; }}
  .steps {{ background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:16px 20px; margin:20px 0; }}
  .step {{ display:flex; align-items:flex-start; gap:12px; padding:10px 0; border-bottom:1px solid #f3f4f6; }}
  .step:last-child {{ border-bottom:none; }}
  .step .num {{ width:28px; height:28px; flex-shrink:0; background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:13px; }}
  .step .desc {{ flex:1; font-size:14px; color:#374151; line-height:1.4; }}
  .step .desc strong {{ color:#111827; display:block; margin-bottom:2px; }}
  .cta {{ display:inline-block; background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff !important; padding:14px 28px; border-radius:10px; text-decoration:none; font-weight:600; font-size:15px; margin-top:8px; }}
  .footer {{ padding:20px 28px; color:#6b7280; font-size:12px; border-top:1px solid #f3f4f6; }}
  .trial-badge {{ background:#fef3c7; border:1px solid #fde68a; color:#92400e; padding:8px 14px; border-radius:8px; font-size:13px; font-weight:600; display:inline-block; margin:14px 0; }}
</style></head>
<body><div class='container'>
  <div class='header'>
    <h1>🎉 ¡Bienvenido a InmoBot!</h1>
    <p>Tu bot de WhatsApp con IA para <strong>{business_name}</strong> está listo</p>
  </div>
  <div class='body'>
    <div class='greeting'>Hola <strong>{first_name}</strong>,</div>
    <p style='font-size:14px; line-height:1.6; color:#374151; margin:14px 0;'>
      Acabás de crear tu workspace en InmoBot. En menos de 5 minutos podés tener
      tu bot respondiendo mensajes de WhatsApp 24/7 con IA.
    </p>
    <div class='trial-badge'>✨ Tu prueba gratis de 7 días empieza ahora</div>
    <div class='steps'>
      <div class='step'>
        <div class='num'>1</div>
        <div class='desc'>
          <strong>Conectá WhatsApp Business</strong>
          Pegá tu Phone Number ID y Access Token desde Meta Business Suite.
        </div>
      </div>
      <div class='step'>
        <div class='num'>2</div>
        <div class='desc'>
          <strong>Personalizá tu landing pública</strong>
          Logo, colores, copy generado con IA — todo desde el editor visual.
          Tu landing está en <a href='{landing_url}' style='color:#6366f1;'>{landing_url}</a>.
        </div>
      </div>
      <div class='step'>
        <div class='num'>3</div>
        <div class='desc'>
          <strong>Probá el bot</strong>
          Mandá un mensaje a tu número de WhatsApp y mirá cómo responde solo.
        </div>
      </div>
    </div>
    <div style='text-align:center;'>
      <a href='{dashboard_url}' class='cta'>Ir al dashboard →</a>
    </div>
    <p style='font-size:13px; color:#6b7280; margin-top:24px; line-height:1.6;'>
      ¿Necesitás una mano? Contestá este email y te respondemos en menos de 4 hs hábiles.
      También podés revisar nuestra documentación en
      <a href='https://app.inmobot.com/inicio' style='color:#6366f1;'>app.inmobot.com</a>.
    </p>
  </div>
  <div class='footer'>
    Recibís este email porque te registraste en InmoBot con {to_email}.<br>
    InmoBot — Bot de WhatsApp con IA para tu negocio.
  </div>
</div></body></html>"""
        return await self.send_email(
            to_emails=[to_email], subject=subject,
            html_body=html_body, text_body=text_body,
            email_type=EmailType.WELCOME_TENANT,
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



    async def send_upsell_unmet_demand(
        self,
        to_email: str,
        business_name: str,
        demand: dict,
    ) -> bool:
        """Email de upsell automático cuando un tenant Pro tiene mucha demanda
        insatisfecha → invita a upgrade a Enterprise.

        demand: {leads_count, value_usd, top_products: [{name, leads_count, price}]}
        """
        if not to_email:
            return False
        leads_count = demand.get("leads_count", 0)
        value_usd = demand.get("value_usd", 0)
        top = demand.get("top_products", []) or []

        subject = (
            f"📊 {business_name}: detectamos ${value_usd:,.0f} en demanda no atendida esta semana"
        )

        rows_html = ""
        rows_text = ""
        for i, p in enumerate(top[:5], 1):
            value = p["leads_count"] * (p.get("price") or 0)
            rows_html += (
                f"<tr>"
                f"<td style='padding:10px;font-weight:700;color:#dc2626;width:30px;'>#{i}</td>"
                f"<td style='padding:10px;'><strong>{p['name']}</strong></td>"
                f"<td style='padding:10px;text-align:right;color:#374151;'>"
                f"{p['leads_count']} leads</td>"
                f"<td style='padding:10px;text-align:right;color:#dc2626;font-weight:700;'>"
                f"${value:,.0f}</td>"
                f"</tr>"
            )
            rows_text += (
                f"  {i}. {p['name']} — {p['leads_count']} leads × ${p.get('price', 0)} = ${value:,.0f}\n"
            )

        text_body = (
            f"Hola,\n\n"
            f"Tu InmoBot detectó algo importante esta semana en {business_name}:\n\n"
            f"➤ {leads_count} clientes preguntaron por productos AGOTADOS\n"
            f"➤ Eso representa ${value_usd:,.0f} USD en demanda real que pasó por tu WhatsApp\n\n"
            f"Top productos pedidos pero sin stock:\n"
            f"{rows_text}\n"
            f"InmoBot ya está guardando esos leads en una lista de espera y les avisará "
            f"automáticamente cuando repongas. Pero hay algo más:\n\n"
            f"Tu plan actual (Pro) no incluye reportes diarios ni alertas por WhatsApp "
            f"de demanda insatisfecha. El plan Enterprise sí.\n\n"
            f"Plan Enterprise:\n"
            f"  • Reportes diarios automáticos\n"
            f"  • Alertas WhatsApp cuando un producto cruza un umbral de demanda\n"
            f"  • 10,000 conversaciones IA/mes (vs 2,000)\n"
            f"  • 50 usuarios (vs 10)\n"
            f"  • API completa + Soporte 24/7\n"
            f"  • Tu propia OpenAI key (opcional)\n\n"
            f"$249/mes — paga sólo lo que vale 1 venta cerrada con esos {leads_count} leads.\n\n"
            f"¿Querés probarlo? Respondé este email y te activamos el upgrade hoy mismo.\n\n"
            f"— Equipo InmoBot"
        )

        html_body = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>
  body {{ font-family:-apple-system,Arial,sans-serif; color:#111827; background:#f3f4f6; margin:0; padding:0; }}
  .container {{ max-width:620px; margin:24px auto; background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.08); }}
  .header {{ background:linear-gradient(135deg,#dc2626 0%,#f97316 100%); color:#fff; padding:28px; text-align:left; }}
  .header h1 {{ margin:0; font-size:22px; font-weight:700; }}
  .header p {{ margin:8px 0 0 0; opacity:0.95; font-size:13px; }}
  .body {{ padding:24px 28px; }}
  .alert-box {{ background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:18px 20px; margin:0 0 18px; }}
  .alert-num {{ font-size:32px; font-weight:800; color:#dc2626; line-height:1; }}
  .alert-lbl {{ font-size:13px; color:#7f1d1d; margin-top:4px; font-weight:500; }}
  .grid {{ display:flex; gap:12px; margin:14px 0; }}
  .grid-cell {{ flex:1; background:#fff7ed; border:1px solid #fed7aa; border-radius:10px; padding:14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; margin:14px 0; border:1px solid #e5e7eb; border-radius:8px; overflow:hidden; }}
  table th {{ background:#f9fafb; text-align:left; padding:10px; font-size:11px; text-transform:uppercase; color:#6b7280; letter-spacing:0.05em; font-weight:600; border-bottom:1px solid #e5e7eb; }}
  table th.r {{ text-align:right; }}
  table tr {{ border-bottom:1px solid #f3f4f6; }}
  table tr:last-child {{ border-bottom:none; }}
  .pitch {{ background:#eef2ff; border:1px solid #c7d2fe; border-radius:10px; padding:18px 20px; margin:18px 0; }}
  .pitch h3 {{ margin:0 0 10px; font-size:16px; color:#3730a3; }}
  .pitch ul {{ margin:8px 0 0; padding-left:20px; font-size:13px; color:#4338ca; line-height:1.7; }}
  .price {{ font-size:24px; font-weight:800; color:#1e1b4b; margin:14px 0 4px; }}
  .price-sub {{ font-size:12px; color:#6b7280; }}
  .cta {{ display:inline-block; background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff !important; padding:14px 28px; border-radius:10px; text-decoration:none; font-weight:600; font-size:15px; margin-top:14px; }}
  .footer {{ padding:18px 28px; color:#6b7280; font-size:12px; border-top:1px solid #f3f4f6; }}
</style></head>
<body><div class='container'>
  <div class='header'>
    <h1>📊 Detectamos ${value_usd:,.0f} en demanda no atendida</h1>
    <p>Reporte automático de InmoBot · {business_name}</p>
  </div>
  <div class='body'>
    <p style='font-size:14px; line-height:1.6; color:#374151; margin:0 0 14px;'>
      Esta semana, <strong>{leads_count} clientes</strong> te preguntaron por
      productos que estaban agotados. Eso es plata real que pasó por tu WhatsApp:
    </p>
    <div class='grid'>
      <div class='grid-cell'>
        <div class='alert-num'>{leads_count}</div>
        <div class='alert-lbl'>leads esperando</div>
      </div>
      <div class='grid-cell'>
        <div class='alert-num'>${value_usd:,.0f}</div>
        <div class='alert-lbl'>USD en demanda</div>
      </div>
    </div>

    <h3 style='font-size:14px; color:#111827; margin:18px 0 8px;'>Top productos pedidos sin stock</h3>
    <table>
      <thead><tr><th></th><th>Producto</th><th class='r'>Pedidos</th><th class='r'>Valor</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>

    <p style='font-size:13px; line-height:1.6; color:#374151;'>
      Buena noticia: InmoBot ya guardó esos leads en una lista de espera y les
      avisará automáticamente cuando repongas stock. Pero estás dejando pasar
      una oportunidad mayor 👇
    </p>

    <div class='pitch'>
      <h3>🚀 Plan Enterprise: pensado para volumen como el tuyo</h3>
      <ul>
        <li><strong>Reportes diarios</strong> de demanda insatisfecha</li>
        <li><strong>Alertas WhatsApp</strong> al admin cuando un producto cruza un umbral</li>
        <li><strong>10,000 conversaciones IA/mes</strong> (vs 2,000 en Pro)</li>
        <li><strong>50 usuarios + API completa + Soporte 24/7</strong></li>
        <li>Tu propia OpenAI key (opcional, sin markup)</li>
      </ul>
      <div class='price'>$249 USD / mes</div>
      <div class='price-sub'>Lo recuperás con 1 venta cerrada de los {leads_count} leads que ya tenés en lista.</div>
    </div>

    <p style='font-size:13px; line-height:1.6; color:#374151;'>
      ¿Querés probarlo? <strong>Respondé este email</strong> y te activamos el
      upgrade hoy mismo (sin cambios de plataforma, todo continúa funcionando).
    </p>
  </div>
  <div class='footer'>
    Email automático generado a partir de tus datos reales en InmoBot.
    Si no querés recibir estos avisos, contestá "no thanks" y los pausamos.
  </div>
</div></body></html>"""

        return await self.send_email(
            to_emails=[to_email],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            email_type=EmailType.UPSELL_UNMET_DEMAND,
        )
