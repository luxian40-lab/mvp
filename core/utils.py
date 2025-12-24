import requests
from django.conf import settings
from django.utils import timezone
from .models import WhatsappLog


def enviar_whatsapp(telefono: str, texto: str, url_imagen: str = None) -> dict:
    """Enviar mensaje por WhatsApp Cloud API usando `requests` y registrar el intento.

    Parámetros:
    - telefono: número en formato internacional, p.ej. '57310...'
    - texto: cuerpo del mensaje
    - url_imagen: URL de la imagen a enviar (opcional)

    Retorna dict con keys: success(bool), mensaje_id (str|None), response (dict|str).
    """
    token = getattr(settings, 'WHATSAPP_TOKEN', None)
    phone_id = getattr(settings, 'WHATSAPP_PHONE_ID', None)
    api_version = getattr(settings, 'WHATSAPP_API_VERSION', 'v19.0')

    if not token or not phone_id:
        # No configurado
        return {'success': False, 'mensaje_id': None, 'response': 'Credentials not set'}

    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Si hay imagen, enviamos un mensaje tipo 'image' con caption
    if url_imagen:
        payload = {
            'messaging_product': 'whatsapp',
            'to': telefono,
            'type': 'image',
            'image': {
                'link': url_imagen,
                'caption': texto
            }
        }
    else:
        # Mensaje de texto simple
        payload = {
            'messaging_product': 'whatsapp',
            'to': telefono,
            'type': 'text',
            'text': {'body': texto}
        }

    # Guardamos un log preliminar (estado=PENDING)
    log = WhatsappLog.objects.create(
        telefono=telefono,
        mensaje=texto,
        mensaje_id=None,
        estado='PENDING',
        fecha=timezone.now()
    )

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        try:
            data = resp.json()
        except Exception:
            data = {'raw': resp.text}

        if resp.status_code in (200, 201) and 'messages' in data:
            mensaje_id = data['messages'][0].get('id')
            log.mensaje_id = mensaje_id
            log.estado = 'SENT'
            log.save()
            return {'success': True, 'mensaje_id': mensaje_id, 'response': data}
        else:
            # Error desde la API
            err = data.get('error', data)
            log.estado = 'ERROR'
            log.save()
            return {'success': False, 'mensaje_id': None, 'response': err}

    except Exception as e:
        # Error de conexión u otra excepción
        log.estado = 'ERROR'
        log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}


def enviar_sms_twilio(telefono: str, texto: str) -> dict:
    """Enviar SMS usando Twilio.
    
    Parámetros:
    - telefono: número en formato internacional, p.ej. '+573001234567'
    - texto: cuerpo del mensaje
    
    Retorna dict con keys: success(bool), mensaje_id (str|None), response (dict|str).
    """
    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)
        
        if not all([account_sid, auth_token, from_number]):
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}
        
        # Asegurar formato correcto del teléfono
        if not telefono.startswith('+'):
            telefono = f'+{telefono}'
        
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=texto,
            from_=from_number,
            to=telefono
        )
        
        return {
            'success': True,
            'mensaje_id': message.sid,
            'response': {
                'status': message.status,
                'sid': message.sid,
                'date_created': str(message.date_created)
            }
        }
        
    except Exception as e:
        return {'success': False, 'mensaje_id': None, 'response': str(e)}


def enviar_whatsapp_twilio(telefono: str, texto: str, url_imagen: str = None) -> dict:
    """Enviar WhatsApp usando Twilio.
    
    Parámetros:
    - telefono: número en formato internacional, p.ej. '+573001234567'
    - texto: cuerpo del mensaje
    - url_imagen: URL de la imagen a enviar (opcional)
    
    Retorna dict con keys: success(bool), mensaje_id (str|None), response (dict|str).
    """
    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        from_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
        
        if not all([account_sid, auth_token, from_number]):
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio WhatsApp credentials not set'}
        
        # Asegurar formato correcto del teléfono para WhatsApp
        if not telefono.startswith('+'):
            telefono = f'+{telefono}'
        if not telefono.startswith('whatsapp:'):
            telefono = f'whatsapp:{telefono}'
        
        client = Client(account_sid, auth_token)
        
        # Crear mensaje con o sin imagen
        if url_imagen:
            message = client.messages.create(
                body=texto,
                from_=from_number,
                to=telefono,
                media_url=[url_imagen]
            )
        else:
            message = client.messages.create(
                body=texto,
                from_=from_number,
                to=telefono
            )
        
        # Guardar log
        WhatsappLog.objects.create(
            telefono=telefono.replace('whatsapp:', ''),
            mensaje=texto,
            mensaje_id=message.sid,
            estado='SENT' if message.status != 'failed' else 'ERROR',
            fecha=timezone.now()
        )
        
        return {
            'success': True,
            'mensaje_id': message.sid,
            'response': {
                'status': message.status,
                'sid': message.sid,
                'date_created': str(message.date_created)
            }
        }
        
    except Exception as e:
        # Guardar log de error
        WhatsappLog.objects.create(
            telefono=telefono.replace('whatsapp:', '').replace('+', ''),
            mensaje=texto,
            mensaje_id=None,
            estado='ERROR',
            fecha=timezone.now()
        )
        return {'success': False, 'mensaje_id': None, 'response': str(e)}
