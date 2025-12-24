"""
🔗 SERVICIO DUAL: META + TWILIO WHATSAPP

Este servicio detecta automáticamente de dónde viene el mensaje
y responde por el canal correcto (Meta o Twilio).

Mantiene TODO el código existente, solo agrega capacidades.
"""
import os
import json
import requests
import logging
from typing import Dict, Any, Optional

from twilio.rest import Client
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppDualService:
    """
    Servicio unificado para Meta WhatsApp y Twilio.
    Detecta automáticamente el proveedor y envía por el canal correcto.
    """
    
    def __init__(self):
        # Configuración Meta
        self.meta_token = os.environ.get('META_WHATSAPP_TOKEN')
        self.meta_phone_id = os.environ.get('META_PHONE_NUMBER_ID')
        self.meta_api_version = os.environ.get('META_API_VERSION', 'v19.0')
        
        # Configuración Twilio
        self.twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        self.twilio_auth = os.environ.get('TWILIO_AUTH_TOKEN')
        self.twilio_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
        
        # Proveedor preferido
        self.provider = os.environ.get('WHATSAPP_PROVIDER', 'dual')
        
        # Cliente Twilio
        if self.twilio_sid and self.twilio_auth:
            self.twilio_client = Client(self.twilio_sid, self.twilio_auth)
        else:
            self.twilio_client = None
    
    def enviar_mensaje(
        self, 
        telefono: str, 
        texto: str, 
        provider: Optional[str] = None,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envía mensaje por el proveedor especificado o el configurado.
        
        Args:
            telefono: Número destino (puede incluir o no +)
            texto: Texto del mensaje
            provider: "meta", "twilio" o None (usa configurado)
            media_url: URL de imagen/video (opcional)
            
        Returns:
            Dict con resultado del envío
        """
        # Limpiar teléfono
        telefono_limpio = telefono.replace('+', '').replace('whatsapp:', '')
        
        # Determinar proveedor a usar
        usar_provider = provider or self.provider
        
        # Si es dual, intentar Meta primero (es gratis hasta 1000)
        if usar_provider == 'dual':
            if self.meta_token and self.meta_phone_id:
                result = self._enviar_meta(telefono_limpio, texto, media_url)
                if result['success']:
                    return result
                # Si falla Meta, intentar Twilio
                logger.warning("Meta falló, intentando Twilio como backup")
                usar_provider = 'twilio'
            else:
                usar_provider = 'twilio'
        
        # Enviar por proveedor específico
        if usar_provider == 'meta':
            return self._enviar_meta(telefono_limpio, texto, media_url)
        elif usar_provider == 'twilio':
            return self._enviar_twilio(telefono_limpio, texto, media_url)
        else:
            return {
                'success': False,
                'error': f'Proveedor no válido: {usar_provider}'
            }
    
    def _enviar_meta(
        self, 
        telefono: str, 
        texto: str, 
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Envía mensaje por Meta WhatsApp Cloud API"""
        
        if not self.meta_token or not self.meta_phone_id:
            return {
                'success': False,
                'error': 'Meta WhatsApp no configurado',
                'provider': 'meta'
            }
        
        url = f"https://graph.facebook.com/{self.meta_api_version}/{self.meta_phone_id}/messages"
        
        headers = {
            'Authorization': f'Bearer {self.meta_token}',
            'Content-Type': 'application/json'
        }
        
        # Preparar payload según si hay media o no
        if media_url:
            # Detectar tipo de media
            if any(ext in media_url.lower() for ext in ['.jpg', '.jpeg', '.png']):
                media_type = 'image'
            elif any(ext in media_url.lower() for ext in ['.mp4', '.3gp']):
                media_type = 'video'
            else:
                media_type = 'document'
            
            payload = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': telefono,
                'type': media_type,
                media_type: {
                    'link': media_url,
                    'caption': texto
                }
            }
        else:
            # Solo texto
            payload = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': telefono,
                'type': 'text',
                'text': {
                    'preview_url': False,
                    'body': texto
                }
            }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'success': True,
                'provider': 'meta',
                'mensaje_id': data.get('messages', [{}])[0].get('id'),
                'response': data
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error enviando por Meta: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'provider': 'meta'
            }
    
    def _enviar_twilio(
        self, 
        telefono: str, 
        texto: str, 
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Envía mensaje por Twilio"""
        
        if not self.twilio_client:
            return {
                'success': False,
                'error': 'Twilio no configurado',
                'provider': 'twilio'
            }
        
        # Formatear teléfono para Twilio
        if not telefono.startswith('+'):
            telefono = f'+{telefono}'
        
        try:
            kwargs = {
                'body': texto,
                'from_': self.twilio_number,
                'to': f'whatsapp:{telefono}'
            }
            
            if media_url:
                kwargs['media_url'] = [media_url]
            
            message = self.twilio_client.messages.create(**kwargs)
            
            return {
                'success': True,
                'provider': 'twilio',
                'mensaje_id': message.sid,
                'status': message.status
            }
            
        except Exception as e:
            logger.error(f"Error enviando por Twilio: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'provider': 'twilio'
            }
    
    def enviar_plantilla_meta(
        self,
        telefono: str,
        template_name: str,
        language_code: str = 'es',
        components: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Envía plantilla aprobada de Meta WhatsApp.
        
        Args:
            telefono: Número destino
            template_name: Nombre de la plantilla en Meta
            language_code: Código de idioma (default: es)
            components: Lista de componentes con variables
            
        Example:
            service.enviar_plantilla_meta(
                "573001234567",
                "bienvenida_eki",
                components=[{
                    "type": "body",
                    "parameters": [{"type": "text", "text": "Juan"}]
                }]
            )
        """
        if not self.meta_token or not self.meta_phone_id:
            return {'success': False, 'error': 'Meta no configurado'}
        
        url = f"https://graph.facebook.com/{self.meta_api_version}/{self.meta_phone_id}/messages"
        
        headers = {
            'Authorization': f'Bearer {self.meta_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': telefono.replace('+', ''),
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language_code}
            }
        }
        
        if components:
            payload['template']['components'] = components
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'provider': 'meta',
                'mensaje_id': data.get('messages', [{}])[0].get('id')
            }
        except Exception as e:
            logger.error(f"Error enviando plantilla Meta: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def detectar_proveedor_mensaje(self, webhook_data: dict) -> str:
        """
        Detecta de qué proveedor viene el mensaje entrante.
        
        Args:
            webhook_data: Data del webhook
            
        Returns:
            "meta", "twilio" o "unknown"
        """
        # Meta WhatsApp tiene estructura específica
        if 'entry' in webhook_data and 'object' in webhook_data:
            if webhook_data.get('object') == 'whatsapp_business_account':
                return 'meta'
        
        # Twilio tiene estos campos
        if 'AccountSid' in webhook_data or 'MessageSid' in webhook_data:
            return 'twilio'
        
        return 'unknown'


# ============================================================================
# FUNCIONES HELPER PARA USAR EN VIEWS.PY
# ============================================================================

def enviar_whatsapp_dual(
    telefono: str, 
    texto: str, 
    media_url: Optional[str] = None,
    provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Función principal para enviar mensajes.
    Reemplaza la función enviar_whatsapp() existente.
    
    Compatible con código antiguo, solo mejora capacidades.
    
    Args:
        telefono: Número destino
        texto: Mensaje
        media_url: URL de media opcional
        provider: Forzar proveedor específico
        
    Returns:
        Dict con resultado
    """
    service = WhatsAppDualService()
    return service.enviar_mensaje(telefono, texto, provider, media_url)


def detectar_proveedor(webhook_data: dict) -> str:
    """
    Detecta de qué proveedor viene el webhook.
    
    Args:
        webhook_data: Data del POST del webhook
        
    Returns:
        "meta", "twilio" o "unknown"
    """
    service = WhatsAppDualService()
    return service.detectar_proveedor_mensaje(webhook_data)
