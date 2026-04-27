import os
import logging
from openai import AsyncOpenAI
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """
    Servicio de IA multi-tenant.
    Usa la key de la plataforma por defecto, o la key propia del tenant si la tiene.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = "gpt-4o"
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.enabled = bool(self.client)

        if not self.api_key:
            logger.warning("OPENAI_API_KEY no configurada - LLM deshabilitado")

    async def _send_message(self, system_message: str, user_message: str) -> str:
        if not self.client:
            return "Error: API key no configurada"

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error en OpenAI: {e}")
            return f"Error: {str(e)}"

    async def classify_intent(self, user_message: str, intents: list = None) -> Dict:
        """Clasifica intencion del usuario (generico, configurable por template)"""
        intent_list = intents or ["comprar", "alquilar", "vender", "inversion", "consulta"]
        intents_str = ", ".join(intent_list)

        system_message = f"""Eres un clasificador de intenciones.
        Clasifica el mensaje del usuario en una de estas categorias: {intents_str}, sin_definir.
        Responde SOLO con la categoria en minusculas, sin explicaciones."""

        response = await self._send_message(system_message, user_message)
        intent = response.strip().lower().replace(" ", "_")
        return {"intent": intent, "confidence": "high"}

    async def extract_field(self, user_message: str, ai_prompt: str) -> Optional[str]:
        """Extrae un campo usando un prompt custom del template"""
        system_message = f"""{ai_prompt}
        Responde SOLO con el valor extraido. Si no puedes extraer nada, responde: NINGUNO"""

        response = await self._send_message(system_message, user_message)

        if "NINGUNO" in response.upper() or "NO MENCION" in response.upper():
            return None
        return response.strip()

    async def generate_smart_response(self, user_message: str, lead_context: Dict = None) -> str:
        """Genera respuesta inteligente para consultas generales"""
        context_info = ""
        if lead_context:
            context_parts = [f"- {k}: {v}" for k, v in lead_context.items() if v]
            context_info = f"\nInformacion del cliente:\n" + "\n".join(context_parts)

        system_message = f"""Eres un asistente virtual profesional.
        Tu rol es ayudar a clientes con sus consultas de forma amable y concisa.
        {context_info}

        REGLAS:
        1. Responde de forma amable y profesional en espanol
        2. Se conciso (maximo 3-4 oraciones)
        3. Si no sabes algo especifico, ofrece conectar con un asesor
        4. No inventes datos
        5. Si la consulta es muy especifica, sugiere agendar una cita"""

        response = await self._send_message(system_message, user_message)
        return response.strip()

    async def parse_free_text_response(self, user_message: str, context: str) -> Dict:
        """Parsea respuestas en lenguaje libre"""
        system_message = f"""Eres un asistente que interpreta respuestas de usuarios.
        Contexto: {context}
        Extrae la informacion relevante. Responde con el dato extraido de forma limpia."""

        response = await self._send_message(system_message, user_message)
        return {"parsed": response.strip(), "unclear": False}


def create_llm_for_tenant(tenant: dict = None) -> LLMService:
    """
    Crea un LLMService con la key del tenant si la tiene,
    sino usa la key de la plataforma (.env).
    """
    if tenant and tenant.get("openai_api_key"):
        return LLMService(api_key=tenant["openai_api_key"])
    return LLMService()
