import os
import uuid
import logging
from openai import AsyncOpenAI
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """
    Servicio de IA multi-tenant.
    
    Soporta DOS backends:
    1. **OpenAI directo** (con OPENAI_API_KEY): usa AsyncOpenAI nativo.
    2. **Emergent Universal Key** (con EMERGENT_LLM_KEY): usa emergentintegrations.LlmChat
       que enruta a OpenAI/Anthropic/Gemini con un key único.
    
    El sistema decide automáticamente qué backend usar según las env vars
    disponibles, prefiriendo OPENAI_API_KEY (margen propio del tenant) sobre
    EMERGENT_LLM_KEY (universal de Emergent).
    """

    def __init__(self, api_key: str = None):
        explicit_or_openai = api_key or os.getenv("OPENAI_API_KEY") or ""
        emergent_key = os.getenv("EMERGENT_LLM_KEY") or ""

        # Default model
        self.model_name = "gpt-4o"

        if explicit_or_openai:
            # Backend 1: OpenAI nativo
            self.api_key = explicit_or_openai
            self.client = AsyncOpenAI(api_key=self.api_key)
            self._backend = "openai"
            self.enabled = True
        elif emergent_key:
            # Backend 2: Emergent Universal Key vía emergentintegrations
            self.api_key = emergent_key
            self.client = "emergent"  # marker
            self._backend = "emergent"
            self.enabled = True
            logger.info("LLMService: usando EMERGENT_LLM_KEY (universal)")
        else:
            self.api_key = ""
            self.client = None
            self._backend = "none"
            self.enabled = False
            logger.warning("OPENAI_API_KEY/EMERGENT_LLM_KEY no configuradas - LLM deshabilitado")

    async def _send_message(self, system_message: str, user_message: str) -> str:
        if not self.enabled:
            return "Error: API key no configurada"

        if self._backend == "openai":
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.7,
                    max_tokens=500,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Error en OpenAI: {e}")
                return f"Error: {str(e)}"

        # Backend Emergent: usa emergentintegrations.LlmChat
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"oneshot-{uuid.uuid4().hex[:12]}",
                system_message=system_message,
            ).with_model("openai", self.model_name)
            response = await chat.send_message(UserMessage(text=user_message))
            return str(response or "")
        except Exception as e:
            logger.error(f"Error en Emergent LLM: {e}")
            return f"Error: {str(e)}"

    async def send_message(self, system_message: str, user_message: str, max_tokens: int = 500) -> str:
        """API publica: envia un mensaje al LLM. Levanta RuntimeError si no hay client.

        max_tokens override permite responses mas largos (ej. flow trees)."""
        if not self.enabled:
            raise RuntimeError("LLM no configurado (api_key faltante)")

        if self._backend == "openai":
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.4,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"Error en OpenAI (send_message): {e}")
                raise

        # Backend Emergent
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"oneshot-{uuid.uuid4().hex[:12]}",
                system_message=system_message,
            ).with_model("openai", self.model_name)
            response = await chat.send_message(UserMessage(text=user_message))
            return str(response or "")
        except Exception as e:
            logger.error(f"Error en Emergent LLM (send_message): {e}")
            raise

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

    async def extract_zone(self, user_message: str) -> Optional[str]:
        """Extrae zona/barrio del mensaje. Sin LLM, devuelve el texto directamente."""
        if not self.enabled:
            return user_message.strip() if user_message.strip() else None
        system_message = """Extrae el nombre de la zona, barrio o ciudad del mensaje.
        Responde SOLO con el nombre de la zona. Si no puedes extraer nada, responde: NINGUNO"""
        response = await self._send_message(system_message, user_message)
        if "NINGUNO" in response.upper():
            return None
        return response.strip()

    async def extract_budget(self, user_message: str) -> Optional[str]:
        """Extrae presupuesto del mensaje. Sin LLM, devuelve el texto directamente."""
        if not self.enabled:
            return user_message.strip() if user_message.strip() else None
        system_message = """Extrae el presupuesto o rango de precio del mensaje.
        Responde SOLO con el valor o rango. Si no puedes extraer nada, responde: NINGUNO"""
        response = await self._send_message(system_message, user_message)
        if "NINGUNO" in response.upper():
            return None
        return response.strip()

    async def generate_smart_response(self, user_message: str, lead_context: Dict = None) -> str:
        """Genera respuesta inteligente para consultas generales"""
        context_info = ""
        if lead_context:
            context_parts = [f"- {k}: {v}" for k, v in lead_context.items() if v]
            context_info = "\nInformacion del cliente:\n" + "\n".join(context_parts)

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

    async def generate_contextual_response(
        self,
        user_message: str,
        business_context: str = "",
        lead_context: Dict = None,
        history: list = None,
        bot_tone: str = "neutro",
    ) -> str:
        """Respuesta del bot enriquecida con DATOS VERIFICADOS del negocio +
        memoria de la conversación + tono configurable.

        - business_context: texto pre-armado por business_profile_service
        - lead_context: dict con name, intent, zone, budget, etc.
        - history: lista de últimos N mensajes [{from, text}] para continuidad
        - bot_tone: neutro|casual|formal|vendedor
        """
        tone_map = {
            "casual": "tono casual y cercano, como charlando con un amigo",
            "formal": "tono formal, serio y respetuoso (usted)",
            "vendedor": "tono entusiasta y vendedor, destaca beneficios",
            "neutro": "tono profesional, amable y conciso",
        }
        tone = tone_map.get((bot_tone or "neutro").lower(), tone_map["neutro"])

        lead_info = ""
        if lead_context:
            parts = [f"- {k}: {v}" for k, v in lead_context.items() if v]
            if parts:
                lead_info = "\n=== INFO DEL CLIENTE ===\n" + "\n".join(parts) + "\n"

        history_text = ""
        if history:
            recent = history[-6:]  # últimos 3 turnos
            lines = []
            for msg in recent:
                who = "Cliente" if msg.get("from") == "customer" else "Bot"
                txt = (msg.get("text") or "").strip()
                if txt:
                    lines.append(f"{who}: {txt[:200]}")
            if lines:
                history_text = "\n=== HISTORIAL RECIENTE ===\n" + "\n".join(lines) + "\n"

        system_message = (
            f"Sos un asistente virtual del negocio. Hablás en español rioplatense, {tone}.\n\n"
            f"{business_context}"
            f"{lead_info}"
            f"{history_text}"
            "\nREGLAS ESTRICTAS:\n"
            "1. Responde MAX 3-4 oraciones, sin floreo.\n"
            "2. Si la respuesta está en INFO DEL NEGOCIO, usala literalmente.\n"
            "3. Si NO está, decí: 'No tengo esa info exacta, te paso con un humano'.\n"
            "4. NO INVENTES horarios, precios, políticas, productos, ubicaciones.\n"
            "5. Si pregunta por algo listado en 'NO ofrecemos', decí claramente que no.\n"
            "6. Si hay historial, mantené coherencia (no preguntes algo ya respondido).\n"
        )

        response = await self._send_message(system_message, user_message)
        return response.strip()

    async def detect_sentiment(self, user_message: str, history: list = None) -> str:
        """Clasifica el sentimiento del cliente: 'normal' | 'frustrated' | 'positive'.

        Optimización de costo:
        - Heurística rápida primero (sin llamar al LLM): detecta señales obvias
          de frustración o positividad por keywords + caps + signos. Si NINGUNA
          señal está presente, asumimos 'normal' y NO llamamos al LLM.
        - Solo llama al LLM cuando hay señales ambiguas que merecen clasificación
          fina (ej. acumulación de molestia sutil, sarcasmo).

        Esto reduce ~80% de las calls LLM en mensajes neutros típicos.
        """
        if not self.client:
            return "normal"

        msg = (user_message or "").strip()
        if not msg:
            return "normal"

        # ===== Heurísticas rápidas (sin LLM) =====
        msg_lower = msg.lower()

        # Frustración explícita
        FRUSTRATION_KEYWORDS = [
            "ya pregunté", "ya te pregunté", "ya pregunte", "ya dije",
            "que desastre", "qué desastre", "no puede ser",
            "estoy harto", "estoy harta", "harto de", "harta de",
            "no entendés", "no entiende nada", "no servís", "no servis",
            "una porquería", "una porqueria", "es una mierda",
            "voy a quejarme", "me voy", "no me ayudás", "no me ayudas",
            "perdiendo el tiempo", "tomame el pelo", "tomarme el pelo",
        ]
        # Positividad explícita
        POSITIVE_KEYWORDS = [
            "gracias", "muchas gracias", "buena atención", "buena atencion",
            "excelente", "genial", "perfecto", "buenisimo", "buenísimo",
            "te felicito", "muy amable", "lo mejor", "súper", "super bien",
        ]

        # Caps ratio: >50% mayúsculas y mensaje >10 chars = grito
        letters = [c for c in msg if c.isalpha()]
        caps_ratio = (
            sum(1 for c in letters if c.isupper()) / len(letters)
            if letters else 0
        )
        many_exclaims = msg.count("!") >= 3 or msg.count("¡") >= 2

        has_frustration_kw = any(kw in msg_lower for kw in FRUSTRATION_KEYWORDS)
        has_positive_kw = any(kw in msg_lower for kw in POSITIVE_KEYWORDS)
        is_shouting = caps_ratio > 0.5 and len(letters) > 10

        # Decisión rápida sin LLM:
        # 1. Frustración explícita (keyword O caps+exclam) → frustrated directo
        if has_frustration_kw or (is_shouting and many_exclaims):
            return "frustrated"
        # 2. Positividad explícita y NINGUNA señal negativa → positive directo
        if has_positive_kw and not has_frustration_kw and not is_shouting:
            return "positive"
        # 3. Mensaje corto y neutro (<60 chars, sin signos) → normal directo (skip LLM)
        if len(msg) < 60 and not many_exclaims and not is_shouting:
            return "normal"

        # ===== Caso ambiguo: SÍ llamamos al LLM =====
        history_text = ""
        if history:
            recent = history[-8:]
            lines = []
            for m in recent:
                who = "Cliente" if m.get("from") == "customer" else "Bot"
                txt = (m.get("text") or "").strip()[:150]
                if txt:
                    lines.append(f"{who}: {txt}")
            if lines:
                history_text = "\nHistorial reciente:\n" + "\n".join(lines)

        system_message = (
            "Sos un clasificador de sentimiento de clientes en chats de WhatsApp. "
            "Tu tarea: clasificar el último mensaje del cliente en UNA de tres categorías:\n"
            "- 'frustrated': el cliente está molesto, enojado, repite preguntas, "
            "usa mayúsculas agresivas, dice 'ya pregunté', insulta, amenaza con irse, "
            "o muestra impaciencia evidente.\n"
            "- 'positive': el cliente está contento, agradece, expresa entusiasmo "
            "o satisfacción.\n"
            "- 'normal': cualquier otro caso (consulta neutra, pregunta informativa, etc.).\n"
            f"{history_text}\n"
            "Responde SOLO con una palabra: frustrated, positive o normal."
        )

        try:
            resp = await self._send_message(system_message, user_message)
            label = (resp or "normal").strip().lower().split()[0]
            if label in ("frustrated", "positive", "normal"):
                return label
            return "normal"
        except Exception as e:
            logger.warning(f"[detect_sentiment] failed: {e}")
            return "normal"

    async def explain_substitute_value(
        self,
        original_product: dict,
        alternative_product: dict,
        lead_context: Dict = None,
    ) -> str:
        """Genera 1 razón concreta de venta para una alternativa.

        Compara features entre el producto pedido (agotado) y la alternativa,
        considerando el perfil del lead. Retorna 1 frase corta tipo:
        - 'Mismo barrio, $20.000 más barato y 1 ambiente extra'
        - 'Tecnología más nueva (M3 vs M2), $100 más caro pero 30% más rápido'
        - '40% más barato y entregamos hoy mismo'

        Si falla la API, retorna string vacío (caller usa fallback genérico).
        """
        if not self.client:
            return ""

        def _fmt(p: dict) -> str:
            name = p.get("name", "")
            price = p.get("price")
            cur = p.get("currency", "USD")
            cat = p.get("category", "")
            desc = (p.get("description") or "")[:200]
            attrs = []
            if price:
                attrs.append(f"${price} {cur}")
            if cat:
                attrs.append(f"categoría: {cat}")
            if desc:
                attrs.append(f"desc: {desc}")
            return f"{name} ({'; '.join(attrs)})"

        lead_info = ""
        if lead_context:
            parts = [f"{k}={v}" for k, v in lead_context.items() if v]
            if parts:
                lead_info = "\nPerfil del cliente: " + ", ".join(parts)

        system_message = (
            "Sos un vendedor experto. Te paso un producto AGOTADO que pidió un "
            "cliente y una ALTERNATIVA disponible. Tu tarea: escribir UNA SOLA "
            "frase corta (máximo 18 palabras) explicando por qué la alternativa "
            "es buena para ESTE cliente, comparando precio, features o categoría.\n\n"
            "REGLAS:\n"
            "1. Frase concreta, no genérica. Si los precios son distintos, mencionalos.\n"
            "2. Si hay features en la descripción, citalas.\n"
            "3. NO uses comillas ni emojis. Castellano rioplatense neutro.\n"
            "4. Si no podés comparar, decí: 'tiene características similares y está disponible ahora'."
        )
        user_message = (
            f"Producto agotado: {_fmt(original_product)}\n"
            f"Alternativa disponible: {_fmt(alternative_product)}{lead_info}\n\n"
            "Tu frase:"
        )

        try:
            resp = await self._send_message(system_message, user_message)
            line = (resp or "").strip().strip('"').strip("'")
            return line[:200] if line else ""
        except Exception as e:
            logger.warning(f"[explain_substitute_value] failed: {e}")
            return ""

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
                # Truncar para evitar UI rota
                if f.get("title"):
                    f["title"] = str(f["title"])[:50]
                if f.get("desc"):
                    f["desc"] = str(f["desc"])[:120]
            steps = parsed.get("steps", [])[:3]
            for s in steps:
                if s.get("title"):
                    s["title"] = str(s["title"])[:50]
                if s.get("desc"):
                    s["desc"] = str(s["desc"])[:120]
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

    async def answer_catalog_question(
        self,
        user_message: str,
        products: list,
        lead_context: Dict = None,
        max_results: int = 4,
    ) -> Optional[str]:
        """Búsqueda semántica del catálogo + redacción de respuesta lista para WhatsApp.

        Útil para preguntas tipo:
        - "qué celular Samsung tienen con buena cámara debajo de $800?"
        - "necesito un dpto en Palermo de 2 ambientes"
        - "tienen algo para regalar a mi mamá económico?"

        El LLM filtra el catálogo respetando los criterios del cliente y
        devuelve un mensaje formateado en castellano con:
        - 2-4 productos relevantes con precios
        - 1 razón corta por qué cada uno cumple lo pedido
        - Pregunta de cierre invitando a profundizar

        Si NO hay productos que cumplan, retorna un mensaje honesto pidiendo
        más detalles o sugiriendo alternativas. Si LLM falla, retorna None
        (caller usa fallback genérico).
        """
        if not self.enabled or not products:
            return None

        # Compactamos el catálogo (tope para el prompt)
        catalog_lines = []
        for p in products[:40]:
            pid = p.get("product_id", "")
            name = p.get("name", "")
            desc = (p.get("description") or "")[:120]
            price = p.get("price") or "?"
            cur = p.get("currency", "USD")
            cat = p.get("category") or ""
            stock = p.get("stock_quantity")
            stock_txt = "stock OK" if (stock is None or stock > 0) else "AGOTADO"
            catalog_lines.append(
                f"- {name} | id={pid} | cat={cat} | ${price} {cur} | {stock_txt} | {desc}"
            )

        ctx = ""
        if lead_context:
            ctx_parts = [f"{k}={v}" for k, v in lead_context.items() if v]
            if ctx_parts:
                ctx = "\nContexto del cliente: " + ", ".join(ctx_parts)

        system_message = (
            "Sos un asistente de ventas experto. Te paso una pregunta del cliente "
            "y un catálogo de productos. Tu tarea: responder con UN mensaje listo "
            "para enviar por WhatsApp, en castellano rioplatense, neutro y conciso.\n\n"
            "REGLAS:\n"
            f"1. Listá hasta {max_results} productos del catálogo que cumplan los "
            "criterios del cliente (precio, features, categoría).\n"
            "2. Por cada producto: nombre + precio + 1 razón corta (max 12 palabras) "
            "explicando por qué cumple lo pedido.\n"
            "3. Si un producto está AGOTADO, ignoralo. Solo recomendá los que tienen stock.\n"
            "4. Si NINGÚN producto cumple los criterios, decí honestamente que no "
            "tenemos algo así y pedí 1-2 detalles para ofrecer alternativas. "
            "NO inventes productos.\n"
            "5. Cerrá con una pregunta corta tipo '¿Cuál te interesa?' o "
            "'¿Querés que te cuente más de alguno?'.\n"
            "6. Format: usá *negrita* para nombres, listas con números (1. 2. 3.).\n"
            "7. Máximo 600 caracteres total.\n"
            "8. NO uses comillas alrededor del mensaje.\n"
        )

        user_prompt = (
            f"Pregunta del cliente: \"{user_message}\"{ctx}\n\n"
            f"Catálogo disponible:\n" + "\n".join(catalog_lines) + "\n\n"
            "Mensaje para WhatsApp:"
        )

        try:
            response = await self._send_message(system_message, user_prompt)
            text = (response or "").strip().strip('"').strip("'")
            return text or None
        except Exception as e:
            logger.warning(f"[answer_catalog_question] failed: {e}")
            return None


def create_llm_for_tenant(tenant: dict = None) -> LLMService:
    """
    Crea un LLMService con la key del tenant si la tiene,
    sino usa la key de la plataforma (.env).
    """
    if tenant and tenant.get("openai_api_key"):
        return LLMService(api_key=tenant["openai_api_key"])
    return LLMService()
