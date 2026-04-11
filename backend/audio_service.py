"""
Servicio de transcripción de audio usando OpenAI Whisper
"""
import logging
import os
import tempfile
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AudioTranscriptionService:
    """Servicio para transcribir mensajes de voz de WhatsApp"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY no configurada - transcripción deshabilitada")
    
    async def download_audio(self, media_url: str, access_token: str) -> bytes:
        """Descarga el archivo de audio desde WhatsApp"""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            # Primero obtener la URL real del media
            response = await client.get(media_url, headers=headers)
            if response.status_code != 200:
                logger.error(f"Error obteniendo URL del media: {response.status_code}")
                return None
            
            media_data = response.json()
            download_url = media_data.get("url")
            
            if not download_url:
                logger.error("No se encontró URL de descarga en la respuesta")
                return None
            
            # Descargar el archivo
            audio_response = await client.get(download_url, headers=headers)
            if audio_response.status_code != 200:
                logger.error(f"Error descargando audio: {audio_response.status_code}")
                return None
            
            return audio_response.content
    
    async def transcribe(self, audio_data: bytes, filename: str = "audio.ogg") -> str:
        """Transcribe audio usando Whisper"""
        if not self.client:
            logger.error("API key no disponible para transcripción")
            return None
        
        try:
            # Guardar audio temporalmente
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                with open(temp_path, "rb") as audio_file:
                    response = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="es"
                    )
                
                transcribed_text = response.text
                logger.info(f"Audio transcrito: '{transcribed_text[:100]}...'")
                return transcribed_text
                
            finally:
                # Limpiar archivo temporal
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Error en transcripción: {str(e)}")
            return None
    
    async def transcribe_whatsapp_audio(self, media_id: str, access_token: str) -> str:
        """Proceso completo: descarga y transcribe audio de WhatsApp"""
        try:
            # URL del media de WhatsApp
            media_url = f"https://graph.facebook.com/v17.0/{media_id}"
            
            # Descargar audio
            audio_data = await self.download_audio(media_url, access_token)
            if not audio_data:
                return None
            
            # Transcribir
            return await self.transcribe(audio_data)
            
        except Exception as e:
            logger.error(f"Error procesando audio de WhatsApp: {str(e)}")
            return None
