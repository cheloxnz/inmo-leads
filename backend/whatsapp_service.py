import os
import requests
import logging
import hmac
import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        # Token forzado para producción
        self.access_token = "EAAMSvSefVHQBQv05eAfa5NrQ8IA7HFG1miZBzbmBbjXbfmUJaxL0ZCiEiGlxpeKUvud9RgON9YNZALekz2wt13XuvOGBwO7xTb0tvOhMOhT46n4GvdUddaTOWZAvxlRf1RUiCDwiqOn6xs1WjiHzHul21A55idj6vxZCK2HAllYlMYQpZBXfSmgRApLRHUBvTAsgZDZD"
        self.app_secret = os.getenv("APP_SECRET")
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.endpoint = f"{self.base_url}/{self.phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        self.db = db
    
    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verifica la firma HMAC-SHA256 del webhook"""
        if not self.app_secret:
            logger.warning("APP_SECRET no configurado, omitiendo verificación de firma")
            return True
        
        expected_signature = hmac.new(
            self.app_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    async def is_within_conversation_window(self, customer_phone: str) -> bool:
        """Verifica si el cliente está dentro de la ventana de 24h"""
        window = await self.db.conversation_windows.find_one({"customer_phone": customer_phone})
        
        if not window:
            return False
        
        window_expires = datetime.fromisoformat(window["window_expires_at"])
        return datetime.utcnow() < window_expires
    
    async def record_customer_message(self, customer_phone: str):
        """Registra mensaje del cliente, abriendo ventana de 24h"""
        now = datetime.utcnow()
        window_expires = now + timedelta(hours=24)
        
        await self.db.conversation_windows.update_one(
            {"customer_phone": customer_phone},
            {
                "$set": {
                    "last_message_timestamp": now.isoformat(),
                    "window_expires_at": window_expires.isoformat(),
                    "is_within_window": True
                }
            },
            upsert=True
        )
        
        logger.info(f"Ventana de 24h abierta para {customer_phone}")
    
    def send_text_message(self, recipient_phone: str, message_text: str, preview_url: bool = False) -> Dict:
        """Envía mensaje de texto simple"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": message_text
            }
        }
        
        return self._send_request(payload)
    
    def send_interactive_buttons(self, recipient_phone: str, body_text: str, buttons: List[Dict], header_text: Optional[str] = None, footer_text: Optional[str] = None) -> Dict:
        """Envía mensaje interactivo con botones de respuesta rápida"""
        interactive = {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": buttons}
        }
        
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        
        if footer_text:
            interactive["footer"] = {"text": footer_text}
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": interactive
        }
        
        return self._send_request(payload)
    
    def send_list_message(self, recipient_phone: str, body_text: str, button_text: str, sections: List[Dict], header_text: Optional[str] = None, footer_text: Optional[str] = None) -> Dict:
        """Envía mensaje con lista interactiva"""
        interactive = {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
        
        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        
        if footer_text:
            interactive["footer"] = {"text": footer_text}
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "interactive",
            "interactive": interactive
        }
        
        return self._send_request(payload)
    
    def send_template_message(self, recipient_phone: str, template_name: str, language_code: str = "es", parameters: Optional[List[Dict]] = None) -> Dict:
        """Envía template pre-aprobado (fuera de ventana 24h)"""
        components = []
        if parameters:
            components.append({
                "type": "body",
                "parameters": parameters
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                },
                "components": components
            }
        }
        
        return self._send_request(payload)
    
    def _send_request(self, payload: Dict) -> Dict:
        """Envía request HTTP a WhatsApp API"""
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            response_data = response.json()
            
            if response.status_code == 200:
                logger.info(f"Mensaje enviado exitosamente: {response_data}")
                return {"success": True, "data": response_data}
            else:
                error_message = response_data.get("error", {}).get("message", "Error desconocido")
                error_code = response_data.get("error", {}).get("code")
                logger.error(f"Error API {error_code}: {error_message}")
                return {"success": False, "error": error_message, "code": error_code}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request falló: {str(e)}")
            return {"success": False, "error": str(e)}