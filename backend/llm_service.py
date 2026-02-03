import os
import logging
from emergentintegrations.llm.chat import LlmChat, UserMessage
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY")
        self.model_provider = "openai"
        self.model_name = "gpt-4o"
    
    async def classify_intent(self, user_message: str) -> Dict:
        """Clasifica la intención del usuario: comprar, alquilar, inversión"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id="intent_classification",
            system_message="""Eres un clasificador de intenciones inmobiliarias. 
            El usuario te dirá algo sobre propiedades. Debes clasificar su intención en una de estas categorías:
            - comprar: quiere comprar una propiedad
            - alquilar: quiere alquilar una propiedad
            - inversion: busca invertir en propiedades
            - sin_definir: no está claro o está explorando opciones
            
            Responde SOLO con la categoría en minúsculas, sin explicaciones."""
        ).with_model(self.model_provider, self.model_name)
        
        message = UserMessage(text=user_message)
        response = await chat.send_message(message)
        
        intent = response.strip().lower()
        return {"intent": intent, "confidence": "high"}
    
    async def extract_zone(self, user_message: str) -> Optional[str]:
        """Extrae la zona/barrio mencionada por el usuario"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id="zone_extraction",
            system_message="""Eres un extractor de zonas y barrios de Buenos Aires, Argentina.
            El usuario mencionará una zona, barrio o ubicación. Extrae y normaliza el nombre.
            Si no mencionan ninguna zona, responde: NINGUNA
            Ejemplos:
            - "en palermo" -> Palermo
            - "zona norte" -> Zona Norte
            - "belgrano o nuñez" -> Belgrano/Núñez
            Responde SOLO con el nombre de la zona normalizado."""
        ).with_model(self.model_provider, self.model_name)
        
        message = UserMessage(text=user_message)
        response = await chat.send_message(message)
        
        if "NINGUNA" in response.upper():
            return None
        return response.strip()
    
    async def extract_budget(self, user_message: str) -> Optional[str]:
        """Extrae el presupuesto mencionado"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id="budget_extraction",
            system_message="""Eres un extractor de presupuestos inmobiliarios.
            El usuario mencionará un monto o rango de presupuesto. Extrae y normaliza.
            Si no mencionan presupuesto, responde: NINGUNO
            Ejemplos:
            - "hasta 200 mil dolares" -> USD 200.000
            - "entre 100 y 150k" -> USD 100.000-150.000
            - "500 lucas" -> USD 500.000
            Responde SOLO con el presupuesto normalizado."""
        ).with_model(self.model_provider, self.model_name)
        
        message = UserMessage(text=user_message)
        response = await chat.send_message(message)
        
        if "NINGUNO" in response.upper():
            return None
        return response.strip()
    
    async def parse_free_text_response(self, user_message: str, context: str) -> Dict:
        """Parsea respuestas en lenguaje libre del usuario según el contexto"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id="free_text_parser",
            system_message=f"""Eres un asistente que interpreta respuestas de usuarios en lenguaje natural.
            Contexto: {context}
            
            Extrae la información relevante y devuelve un JSON con los datos estructurados.
            Si no puedes extraer información clara, indica 'unclear': true"""
        ).with_model(self.model_provider, self.model_name)
        
        message = UserMessage(text=user_message)
        response = await chat.send_message(message)
        
        try:
            import json
            return json.loads(response)
        except:
            return {"parsed": response, "unclear": False}
    
    async def validate_response(self, user_message: str, expected_type: str) -> Dict:
        """Valida si la respuesta del usuario es apropiada para lo que se preguntó"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id="response_validator",
            system_message=f"""Eres un validador de respuestas.
            Se esperaba una respuesta de tipo: {expected_type}
            
            Analiza si el mensaje del usuario es una respuesta válida.
            Responde con JSON: {{"valid": true/false, "reason": "explicación"}}"""
        ).with_model(self.model_provider, self.model_name)
        
        message = UserMessage(text=user_message)
        response = await chat.send_message(message)
        
        try:
            import json
            return json.loads(response)
        except:
            return {"valid": True, "reason": "Procesando respuesta"}