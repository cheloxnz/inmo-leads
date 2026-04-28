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

    async def generate_landing_copy(self, business_description: str) -> Dict:
        """Genera copy para landing dinamica desde una descripcion del negocio.

        Retorna: {
            "business_tagline": "...",
            "features": [{"icon": "home|calendar|message|shield|bot", "title": "...", "desc": "..."}, ...3],
            "steps": [{"title": "...", "desc": "..."}, ...3]
        }
        """
        if not self.client:
            return {
                "business_tagline": "Atencion 24/7 con IA por WhatsApp",
                "features": [],
                "steps": [],
                "ai_enabled": False
            }

        system_message = """Eres un experto en marketing digital y copywriting.
Dada una descripcion breve de un negocio, generas copy persuasivo para su landing page.
Responde SOLO con un JSON valido (sin texto extra) con esta estructura exacta:
{
  "business_tagline": "Frase corta de 5-10 palabras",
  "features": [
    {"icon": "home|calendar|message|shield|bot", "title": "Titulo corto", "desc": "Descripcion de hasta 100 chars"},
    {"icon": "...", "title": "...", "desc": "..."},
    {"icon": "...", "title": "...", "desc": "..."}
  ],
  "steps": [
    {"title": "Paso 1 corto", "desc": "Descripcion de hasta 80 chars"},
    {"title": "Paso 2 corto", "desc": "Descripcion de hasta 80 chars"},
    {"title": "Paso 3 corto", "desc": "Descripcion de hasta 80 chars"}
  ]
}
Iconos validos: home, calendar, message, shield, bot.
Escribi en ESPANOL rioplatense (vos en lugar de tu)."""

        user_prompt = f"Descripcion del negocio: \"{business_description}\"\n\nGenera el JSON:"

        try:
            response = await self._send_message(system_message, user_prompt)
            import json
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                return {"business_tagline": "", "features": [], "steps": [], "ai_enabled": True, "error": "no JSON"}
            parsed = json.loads(match.group(0))
            valid_icons = {"home", "calendar", "message", "shield", "bot"}
            features = parsed.get("features", [])[:3]
            for f in features:
                if f.get("icon") not in valid_icons:
                    f["icon"] = "bot"
            steps = parsed.get("steps", [])[:3]
            return {
                "business_tagline": (parsed.get("business_tagline") or "")[:120],
                "features": features,
                "steps": steps,
                "ai_enabled": True
            }
        except Exception as e:
            logger.error(f"Error en generate_landing_copy: {e}")
            return {"business_tagline": "", "features": [], "steps": [], "ai_enabled": True, "error": str(e)}

    async def recommend_products(self, user_message: str, products: list, lead_context: Dict = None, max_results: int = 3) -> list:
        """
        Dado un mensaje del usuario y la lista de productos del tenant,
        retorna los product_ids mas relevantes ordenados por relevancia.
        Si LLM no esta habilitado o hay error, retorna los primeros N productos activos.
        """
        if not products:
            return []

        if not self.client:
            return [p.get("product_id") for p in products[:max_results] if p.get("product_id")]

        # Construye lista compacta de productos
        lines = []
        for p in products[:30]:  # tope para prompt
            pid = p.get("product_id", "")
            name = p.get("name", "")
            desc = (p.get("description") or "")[:80]
            price = p.get("price") or ""
            cat = p.get("category") or ""
            lines.append(f"- id={pid} | {name} | cat={cat} | precio={price} | {desc}")

        ctx = ""
        if lead_context:
            ctx_parts = [f"{k}={v}" for k, v in lead_context.items() if v]
            ctx = " Contexto del lead: " + ", ".join(ctx_parts)

        system_message = f"""Eres un asistente de ventas. Dado un mensaje del cliente y un catalogo de productos, elige los {max_results} productos mas relevantes.
Responde SOLO con un JSON array de strings con los product_id seleccionados, ordenados de mas a menos relevante.
Ejemplo de respuesta valida: ["id1","id2","id3"]
Si ningun producto es relevante, responde: []"""

        user_prompt = f"""Mensaje del cliente: "{user_message}"{ctx}

Catalogo disponible:
{chr(10).join(lines)}

Devuelve JSON array de hasta {max_results} product_id relevantes:"""

        try:
            response = await self._send_message(system_message, user_prompt)
            import json
            import re
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if not match:
                return [p.get("product_id") for p in products[:max_results] if p.get("product_id")]
            ids = json.loads(match.group(0))
            valid_ids = {p.get("product_id") for p in products if p.get("product_id")}
            return [i for i in ids if i in valid_ids][:max_results]
        except Exception as e:
            logger.error(f"Error en recommend_products: {e}")
            return [p.get("product_id") for p in products[:max_results] if p.get("product_id")]


def create_llm_for_tenant(tenant: dict = None) -> LLMService:
    """
    Crea un LLMService con la key del tenant si la tiene,
    sino usa la key de la plataforma (.env).
    """
    if tenant and tenant.get("openai_api_key"):
        return LLMService(api_key=tenant["openai_api_key"])
    return LLMService()
