"""
Procesamiento de mensajes de audio de WhatsApp
- Descarga de audio desde Twilio/Meta
- Transcripción con OpenAI Whisper
- Procesamiento con IA
"""

import os
import requests
import logging
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Procesa mensajes de audio de WhatsApp"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.audio_folder = os.path.join(settings.MEDIA_ROOT, 'audios_whatsapp')
        
        # Crear carpeta si no existe
        if not os.path.exists(self.audio_folder):
            os.makedirs(self.audio_folder)
            logger.info(f"📁 Carpeta de audios creada: {self.audio_folder}")
    
    def descargar_audio_twilio(self, media_url, media_sid):
        """
        Descarga audio desde Twilio
        
        Args:
            media_url: URL del media desde Twilio
            media_sid: SID del media (identificador único)
        
        Returns:
            str: Ruta del archivo descargado o None si falla
        """
        try:
            logger.info(f"📥 Descargando audio de Twilio: {media_sid}")
            
            # Autenticación Twilio
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            
            # Descargar archivo
            response = requests.get(
                media_url,
                auth=(account_sid, auth_token),
                timeout=30
            )
            
            if response.status_code == 200:
                # Guardar archivo
                file_path = os.path.join(self.audio_folder, f"{media_sid}.ogg")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"✅ Audio descargado: {file_path} ({len(response.content)} bytes)")
                return file_path
            else:
                logger.error(f"❌ Error descargando audio: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error descargando audio de Twilio: {e}")
            return None
    
    def descargar_audio_meta(self, audio_id):
        """
        Descarga audio desde Meta WhatsApp Business API
        
        Args:
            audio_id: ID del audio en Meta
        
        Returns:
            str: Ruta del archivo descargado o None si falla
        """
        try:
            logger.info(f"📥 Descargando audio de Meta: {audio_id}")
            
            # Paso 1: Obtener URL del audio
            headers = {
                'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}'
            }
            
            url_info = f"https://graph.facebook.com/v19.0/{audio_id}"
            response = requests.get(url_info, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"❌ Error obteniendo info del audio: {response.status_code}")
                return None
            
            data = response.json()
            audio_url = data.get('url')
            
            if not audio_url:
                logger.error("❌ No se encontró URL del audio")
                return None
            
            # Paso 2: Descargar el audio
            response = requests.get(audio_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Guardar archivo
                file_path = os.path.join(self.audio_folder, f"{audio_id}.ogg")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"✅ Audio descargado: {file_path} ({len(response.content)} bytes)")
                return file_path
            else:
                logger.error(f"❌ Error descargando audio: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error descargando audio de Meta: {e}")
            return None
    
    def transcribir_audio(self, file_path):
        """
        Transcribe audio usando OpenAI Whisper
        
        Args:
            file_path: Ruta del archivo de audio
        
        Returns:
            str: Texto transcrito o None si falla
        """
        try:
            logger.info(f"🎤 Transcribiendo audio: {file_path}")
            
            # Validar que el archivo existe
            if not os.path.exists(file_path):
                logger.error(f"❌ Archivo no encontrado: {file_path}")
                return None
            
            # Transcribir con Whisper
            with open(file_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="es"  # Español colombiano
                )
            
            texto = transcript.text.strip()
            logger.info(f"✅ Audio transcrito: {texto[:100]}...")
            
            return texto
            
        except Exception as e:
            logger.error(f"❌ Error transcribiendo audio: {e}")
            return None
    
    def procesar_audio_completo(self, media_info, proveedor='twilio'):
        """
        Proceso completo: descargar + transcribir
        
        Args:
            media_info: Información del media (depende del proveedor)
                - Twilio: dict con 'media_url' y 'media_sid'
                - Meta: str con audio_id
            proveedor: 'twilio' o 'meta'
        
        Returns:
            dict: {
                'success': bool,
                'texto': str o None,
                'audio_path': str o None,
                'error': str o None
            }
        """
        try:
            # 1. Descargar audio
            if proveedor == 'twilio':
                audio_path = self.descargar_audio_twilio(
                    media_info['media_url'],
                    media_info['media_sid']
                )
            else:  # meta
                audio_path = self.descargar_audio_meta(media_info)
            
            if not audio_path:
                return {
                    'success': False,
                    'texto': None,
                    'audio_path': None,
                    'error': 'No se pudo descargar el audio'
                }
            
            # 2. Transcribir audio
            texto = self.transcribir_audio(audio_path)
            
            if not texto:
                return {
                    'success': False,
                    'texto': None,
                    'audio_path': audio_path,
                    'error': 'No se pudo transcribir el audio'
                }
            
            # 3. Éxito
            return {
                'success': True,
                'texto': texto,
                'audio_path': audio_path,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"❌ Error procesando audio: {e}")
            return {
                'success': False,
                'texto': None,
                'audio_path': None,
                'error': str(e)
            }


# Función helper para uso rápido
def procesar_audio_whatsapp(media_info, proveedor='twilio'):
    """
    Wrapper sencillo para procesar audio de WhatsApp
    
    Usage:
        resultado = procesar_audio_whatsapp(
            {'media_url': url, 'media_sid': sid},
            proveedor='twilio'
        )
        if resultado['success']:
            texto_transcrito = resultado['texto']
    """
    processor = AudioProcessor()
    return processor.procesar_audio_completo(media_info, proveedor)
