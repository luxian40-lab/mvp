"""
Utilidades para integración con Meta WhatsApp Business API
Específicamente para gestión de plantillas (templates)
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def enviar_plantilla_a_meta(nombre_plantilla, contenido, categoria='MARKETING', idioma='es'):
    """
    Envía una plantilla a Meta para aprobación.
    
    Args:
        nombre_plantilla: Nombre interno de la plantilla (sin espacios, minúsculas, guiones bajos)
        contenido: Texto de la plantilla
        categoria: MARKETING, UTILITY, o AUTHENTICATION
        idioma: Código de idioma (es, en, etc.)
    
    Returns:
        dict con 'success' (bool), 'template_id' (str), 'status' (str), 'message' (str)
    """
    
    # Validar configuración
    waba_id = settings.WHATSAPP_BUSINESS_ACCOUNT_ID
    access_token = settings.WHATSAPP_TOKEN
    
    if not waba_id or not access_token:
        logger.error("❌ WHATSAPP_BUSINESS_ACCOUNT_ID o WHATSAPP_TOKEN no configurados")
        return {
            'success': False,
            'template_id': None,
            'status': 'ERROR',
            'message': 'Credenciales de Meta no configuradas. Configura WHATSAPP_BUSINESS_ACCOUNT_ID y WHATSAPP_TOKEN'
        }
    
    # Sanitizar nombre de plantilla (Meta requiere formato específico)
    nombre_sanitizado = nombre_plantilla.lower().replace(' ', '_').replace('-', '_')
    nombre_sanitizado = ''.join(c for c in nombre_sanitizado if c.isalnum() or c == '_')
    
    # Construir URL del endpoint
    url = f"https://graph.facebook.com/v19.0/{waba_id}/message_templates"
    
    # Construir payload
    payload = {
        "name": nombre_sanitizado,
        "language": idioma,
        "category": categoria,
        "components": [
            {
                "type": "BODY",
                "text": contenido
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"📤 Enviando plantilla '{nombre_sanitizado}' a Meta para revisión...")
        logger.debug(f"URL: {url}")
        logger.debug(f"Payload: {payload}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response_data = response.json()
        
        logger.debug(f"Respuesta Meta: {response_data}")
        
        if response.status_code == 200 and response_data.get('id'):
            template_id = response_data.get('id')
            status = response_data.get('status', 'PENDING')
            
            logger.info(f"✅ Plantilla enviada exitosamente - ID: {template_id}, Estado: {status}")
            
            return {
                'success': True,
                'template_id': template_id,
                'status': status,
                'message': f'Plantilla enviada a Meta para revisión. ID: {template_id}',
                'nombre_meta': nombre_sanitizado
            }
        else:
            error_message = response_data.get('error', {}).get('message', 'Error desconocido')
            error_code = response_data.get('error', {}).get('code', 'N/A')
            
            logger.error(f"❌ Error de Meta API: {error_message} (Código: {error_code})")
            
            return {
                'success': False,
                'template_id': None,
                'status': 'ERROR',
                'message': f'Error de Meta: {error_message}',
                'error_code': error_code
            }
    
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout al conectar con Meta API")
        return {
            'success': False,
            'template_id': None,
            'status': 'ERROR',
            'message': 'Timeout al conectar con Meta API'
        }
    
    except Exception as e:
        logger.error(f"❌ Excepción al enviar plantilla a Meta: {str(e)}")
        return {
            'success': False,
            'template_id': None,
            'status': 'ERROR',
            'message': f'Error: {str(e)}'
        }


def verificar_estado_plantilla_meta(template_id):
    """
    Verifica el estado de una plantilla en Meta.
    
    Args:
        template_id: ID de la plantilla en Meta
    
    Returns:
        dict con 'success', 'status', 'quality_score', etc.
    """
    
    access_token = settings.WHATSAPP_TOKEN
    
    if not access_token:
        return {'success': False, 'message': 'Token no configurado'}
    
    url = f"https://graph.facebook.com/v19.0/{template_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            return {
                'success': True,
                'status': data.get('status', 'UNKNOWN'),
                'quality_score': data.get('quality_score', {}),
                'name': data.get('name', ''),
                'language': data.get('language', '')
            }
        else:
            return {
                'success': False,
                'message': data.get('error', {}).get('message', 'Error desconocido')
            }
    
    except Exception as e:
        logger.error(f"Error verificando plantilla: {str(e)}")
        return {'success': False, 'message': str(e)}
