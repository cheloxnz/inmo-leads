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
    """
    WhatsApp Cloud API Service - Multi-tenant.
    Puede instanciarse con credenciales por defecto (.env) o por tenant.
    """

    def __init__(self, db: AsyncIOMotorDatabase, access_token: str = None, phone_number_id: str = None):
        self.phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.access_token = access_token or os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.app_secret = os.getenv("APP_SECRET")
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.db = db
        self._update_endpoint()

    def _update_endpoint(self):
        """Actualiza endpoint y headers basado en las credenciales actuales"""
        self.endpoint = f"{self.base_url}/{self.phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def verify_signature(self, body: bytes, signature: str) -> bool:
        if not self.app_secret:
            return True
        expected_signature = hmac.new(
            self.app_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    async def is_within_conversation_window(self, customer_phone: str) -> bool:
        window = await self.db.conversation_windows.find_one({"customer_phone": customer_phone})
        if not window:
            return False
        window_expires = datetime.fromisoformat(window["window_expires_at"])
        return datetime.utcnow() < window_expires

    async def record_customer_message(self, customer_phone: str):
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

    def send_text_message(self, recipient_phone: str, message_text: str, preview_url: bool = False) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {"preview_url": preview_url, "body": message_text}
        }
        return self._send_request(payload)

    def send_interactive_buttons(self, recipient_phone: str, body_text: str, buttons: List[Dict], header_text: Optional[str] = None, footer_text: Optional[str] = None) -> Dict:
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

    def send_location(self, recipient_phone: str, latitude: float, longitude: float, name: str = "", address: str = "") -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "location",
            "location": {"latitude": latitude, "longitude": longitude, "name": name, "address": address}
        }
        return self._send_request(payload)

    def send_list_message(self, recipient_phone: str, body_text: str, button_text: str, sections: List[Dict], header_text: Optional[str] = None, footer_text: Optional[str] = None) -> Dict:
        interactive = {
            "type": "list",
            "body": {"text": body_text},
            "action": {"button": button_text, "sections": sections}
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
        components = []
        if parameters:
            components.append({"type": "body", "parameters": parameters})

        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        return self._send_request(payload)

    def _send_request(self, payload: Dict) -> Dict:
        if not self.access_token or not self.phone_number_id:
            logger.warning("WhatsApp no configurado: falta token o phone_number_id")
            return {"success": False, "error": "WhatsApp no configurado"}

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            response_data = response.json()

            if response.status_code == 200:
                logger.info(f"Mensaje enviado exitosamente")
                return {"success": True, "data": response_data}
            else:
                error_message = response_data.get("error", {}).get("message", "Error desconocido")
                error_code = response_data.get("error", {}).get("code")
                logger.error(f"Error API {error_code}: {error_message}")
                return {"success": False, "error": error_message, "code": error_code}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request falló: {str(e)}")
            return {"success": False, "error": str(e)}


def create_wa_service_for_tenant(db: AsyncIOMotorDatabase, tenant: dict) -> WhatsAppService:
    """
    Crea un WhatsAppService con las credenciales del tenant.
    Si el tenant no tiene credenciales, usa las del .env (fallback).
    """
    access_token = tenant.get("whatsapp_access_token", "") if tenant else ""
    phone_number_id = tenant.get("whatsapp_phone_number_id", "") if tenant else ""

    if access_token and phone_number_id:
        return WhatsAppService(db, access_token=access_token, phone_number_id=phone_number_id)
    
    # Fallback to default .env credentials
    return WhatsAppService(db)
