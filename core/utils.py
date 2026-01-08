import requests
from django.conf import settings
from django.utils import timezone
from .models import WhatsappLog


def enviar_whatsapp_twilio(telefono: str, texto: str, mensaje_id_referencia: str = None, media_url: str = None, texto_log: str = None) -> dict:
    """Enviar mensaje por Twilio WhatsApp API.

    Parámetros:
    - telefono: número en formato internacional, p.ej. '+573001234567'
    - texto: cuerpo del mensaje a enviar
    - mensaje_id_referencia: ID del mensaje al que se responde (opcional)
    - media_url: URL del video o imagen (opcional)
    - texto_log: texto alternativo para guardar en log (para preservar marcadores internos)

    Retorna dict con keys: success(bool), mensaje_id (str|None), response (str).
    """
    log = None  # Inicializar log como None
    
    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        twilio_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
        
        print(f"[TWILIO] Account SID: {account_sid}")
        print(f"[TWILIO] Auth Token: {auth_token[:20] if auth_token else None}...")
        print(f"[TWILIO] WhatsApp Number: {twilio_number}")
        
        if not account_sid or not auth_token:
            print("[ERROR] Credenciales de Twilio NO configuradas")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}
        
        # Asegurar formato whatsapp:+57...
        if not telefono.startswith('whatsapp:'):
            if not telefono.startswith('+'):
                telefono = f'+{telefono}'
            telefono = f'whatsapp:{telefono}'
        
        # Crear cliente Twilio
        client = Client(account_sid, auth_token)
        
        # Guardar log preliminar - usar texto_log si existe, sino usar texto
        mensaje_para_log = texto_log if texto_log else texto
        log = WhatsappLog.objects.create(
            telefono=telefono.replace('whatsapp:', ''),
            mensaje=mensaje_para_log,
            mensaje_id=mensaje_id_referencia,
            estado='PENDING',
            tipo='SENT',
            fecha=timezone.now()
        )
        
        # Preparar parámetros del mensaje
        message_params = {
            'from_': twilio_number,
            'body': texto,
            'to': telefono
        }
        
        # Agregar media_url si hay video
        if media_url:
            message_params['media_url'] = [media_url]
            print(f"[VIDEO] Enviando video: {media_url}")
        
        # Enviar mensaje (con o sin video)
        message = client.messages.create(**message_params)
        
        # Actualizar log
        log.mensaje_id = message.sid
        log.estado = 'SENT'
        log.save()
        
        print(f"[SUCCESS] TWILIO: Mensaje enviado a {telefono} - SID: {message.sid}")
        
        return {'success': True, 'mensaje_id': message.sid, 'response': 'Message sent'}
        
    except Exception as e:
        print(f"[ERROR] Error enviando por Twilio: {str(e)}")
        if log:  # Solo actualizar si el log existe
            log.estado = 'ERROR'
            log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}


def enviar_whatsapp(telefono: str, texto: str, mensaje_id_referencia: str = None) -> dict:
    """Enviar mensaje por WhatsApp Cloud API usando `requests` y registrar el intento.

    Parámetros:
    - telefono: número en formato internacional, p.ej. '57310...'
    - texto: cuerpo del mensaje
    - mensaje_id_referencia: ID del mensaje al que se responde (opcional)

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
    payload = {
        'messaging_product': 'whatsapp',
        'to': telefono,
        'type': 'text',
        'text': {'body': texto}
    }

    # Guardamos un log preliminar (estado=PENDING, tipo=SENT para salida)
    log = WhatsappLog.objects.create(
        telefono=telefono,
        mensaje=texto,
        mensaje_id=mensaje_id_referencia,  # Referencia al mensaje original
        estado='PENDING',
        tipo='SENT',
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
