"""
Sistema de envío de plantillas aprobadas de WhatsApp via Twilio
"""
from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)


def enviar_plantilla_twilio(telefono: str, content_sid: str, variables: dict = None) -> dict:
    """
    Envía una plantilla aprobada de WhatsApp via Twilio.
    
    Args:
        telefono: Número en formato +57... (sin whatsapp:)
        content_sid: SID de la plantilla aprobada (ej: HX1234...)
        variables: Diccionario con variables de la plantilla (ej: {'1': 'Juan', '2': 'Plátano'})
    
    Returns:
        dict: {'success': bool, 'mensaje_id': str, 'response': str}
    
    Ejemplo:
        enviar_plantilla_twilio(
            telefono='+573001234567',
            content_sid='HXa1b2c3d4...',
            variables={'1': 'Juan', '2': 'Plátano Hartón'}
        )
    """
    try:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN')
        twilio_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', 'whatsapp:+573202948806')
        
        if not account_sid or not auth_token:
            return {'success': False, 'mensaje_id': None, 'response': 'Credenciales no configuradas'}
        
        # Crear cliente
        client = Client(account_sid, auth_token)
        
        # Asegurar formato whatsapp:+57...
        if not telefono.startswith('whatsapp:'):
            if not telefono.startswith('+'):
                telefono = f'+{telefono}'
            telefono = f'whatsapp:{telefono}'
        
        # Preparar parámetros del mensaje
        message_params = {
            'from_': twilio_number,
            'to': telefono,
            'content_sid': content_sid
        }
        
        # Agregar variables si existen
        if variables:
            # Twilio espera formato: ContentVariables={"1": "valor1", "2": "valor2"}
            import json
            message_params['content_variables'] = json.dumps(variables)
        
        # Enviar mensaje con plantilla
        message = client.messages.create(**message_params)
        
        logger.info(f"✅ Plantilla enviada a {telefono} - SID: {message.sid}")
        
        return {
            'success': True,
            'mensaje_id': message.sid,
            'response': 'Template sent',
            'status': message.status
        }
        
    except Exception as e:
        logger.error(f"❌ Error enviando plantilla: {str(e)}")
        return {
            'success': False,
            'mensaje_id': None,
            'response': str(e)
        }


def enviar_campana_con_plantilla(campana_id: int) -> dict:
    """
    Envía una campaña usando plantilla aprobada a todos los destinatarios.
    
    Args:
        campana_id: ID de la campaña
    
    Returns:
        dict: Estadísticas del envío
    """
    from .models import Campana, Linea
    
    try:
        campana = Campana.objects.get(id=campana_id)
        plantilla = campana.plantilla
        
        # Verificar que tenga Content SID (plantilla aprobada)
        if not plantilla.twilio_template_sid:
            return {
                'success': False,
                'error': 'La plantilla no tiene Content SID de Twilio configurado'
            }
        
        destinatarios = campana.destinatarios.all()
        if not destinatarios.exists():
            return {
                'success': False,
                'error': 'No hay destinatarios en la campaña'
            }
        
        enviados = 0
        fallidos = 0
        
        for estudiante in destinatarios:
            # Preparar variables de la plantilla
            variables = {
                '1': estudiante.nombre or 'Estudiante',
                '2': campana.nombre
            }
            
            # Enviar plantilla
            resultado = enviar_plantilla_twilio(
                telefono=estudiante.telefono,
                content_sid=plantilla.twilio_template_sid,
                variables=variables
            )
            
            # Crear línea de envío
            Linea.objects.create(
                campana=campana,
                destinatario=estudiante,
                estado='ENVIADO' if resultado['success'] else 'ERROR',
                mensaje_id=resultado.get('mensaje_id'),
                respuesta_api=resultado.get('response', '')[:500]
            )
            
            if resultado['success']:
                enviados += 1
            else:
                fallidos += 1
        
        return {
            'success': True,
            'total': destinatarios.count(),
            'enviados': enviados,
            'fallidos': fallidos
        }
        
    except Exception as e:
        logger.error(f"❌ Error en campaña: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
