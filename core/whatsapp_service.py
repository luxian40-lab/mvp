
def enviar_video_whatsapp(to, video_url):
    pass

# Función general para enviar cualquier tipo de archivo de ArchivoModulo por WhatsApp
from twilio.rest import Client
from django.conf import settings
from .models_extras import ArchivoModulo
from .models import WhatsappLog
from django.utils import timezone

def enviar_archivo_modulo_whatsapp(telefono, archivo_modulo, texto_extra=None):
    """
    Envía cualquier archivo de ArchivoModulo por WhatsApp usando Twilio.
    Args:
        telefono (str): Número destino en formato internacional (ej: +573001234567)
        archivo_modulo (ArchivoModulo): Instancia de ArchivoModulo
        texto_extra (str): Texto adicional a enviar junto con el archivo (opcional)
    Returns:
        dict: {'success': bool, 'mensaje_id': str|None, 'response': str}
    """
    url_envio = archivo_modulo.get_url_para_envio()
    if not url_envio:
        return {'success': False, 'mensaje_id': None, 'response': 'No hay URL pública para el archivo'}

    # Descripción según tipo
    tipo = archivo_modulo.get_tipo_display() if hasattr(archivo_modulo, 'get_tipo_display') else archivo_modulo.tipo
    titulo = archivo_modulo.titulo or ''
    descripcion = f"{tipo}: {titulo}"
    if texto_extra:
        descripcion = f"{descripcion}\n{texto_extra}"

    # Preparar log preliminar
    log = WhatsappLog.objects.create(
        telefono=telefono.replace('whatsapp:', '').replace('+', ''),
        mensaje=descripcion,
        estado='PENDING',
        tipo='SENT',
        fecha=timezone.now()
    )

    try:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        whatsapp_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
        if not all([account_sid, auth_token, whatsapp_number]):
            raise ValueError("Faltan credenciales de Twilio en settings.py")

        # Formato correcto para Twilio
        to = telefono
        if not to.startswith('whatsapp:'):
            if not to.startswith('+'):
                to = f'+{to}'
            to = f'whatsapp:{to}'

        # Formatear número FROM correctamente (evitar doble whatsapp:)
        from_number = str(whatsapp_number).strip()
        if not from_number.startswith('whatsapp:'):
            if not from_number.startswith('+'):
                from_number = f'+{from_number}'
            from_number = f'whatsapp:{from_number}'

        client = Client(account_sid, auth_token)
        # Agregar status_callback para rastreo
        status_callback_url = getattr(settings, 'TWILIO_STATUS_CALLBACK', None)
        message_params = {
            'from_': from_number,
            'to': to,
            'body': descripcion,
            'media_url': [url_envio]
        }
        if status_callback_url:
            message_params['status_callback'] = status_callback_url

        message = client.messages.create(**message_params)
        log.mensaje_id = message.sid
        log.estado = 'SENT'
        log.error_detalle = ''
        log.save()
        return {'success': True, 'mensaje_id': message.sid, 'response': 'Enviado'}
    except Exception as e:
        log.estado = 'ERROR'
        log.error_detalle = str(e)
        log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}
