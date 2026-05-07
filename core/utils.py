# --- Generador de presigned URL con Content-Type correcto para S3 ---

import boto3
import logging
from botocore.config import Config
from django.conf import settings

logger = logging.getLogger(__name__)


def generar_url_firmada_s3_v4(bucket_name, object_name, expiration=3600):
    """
    Genera URL firmada forzando Signature Version 4 (AWS4-HMAC-SHA256).
    Esto arregla el error XML "Authorization mechanism not supported".
    """
    mi_config = Config(
        signature_version='s3v4',
        region_name='us-east-2'  # ¡OJO! Pon aquí la región REAL de tu bucket
    )
    s3_client = boto3.client('s3',
        aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
        aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
        config=mi_config
    )
    try:
        response = s3_client.generate_presigned_url('get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_name,
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=expiration
        )
        logger.debug(f"[Presigned URL] {response}")
        return response
    except Exception as e:
        logger.error(f"Error generando presigned URL: {e}")
        return None
import boto3
from botocore.exceptions import NoCredentialsError

# --- Vacuna definitiva contra el error 21212 ---
def formatear_numero_whatsapp(numero):
    """
    Recibe CUALQUIER formato de número y lo devuelve
    listo para que Twilio no tire el error 21212.
    """
    if not numero:
        return None
    numero = str(numero).strip()
    if numero.startswith('whatsapp:'):
        return numero
    if not numero.startswith('+'):
        numero = f"+{numero}"
    return f"whatsapp:{numero}"

# --- Generador de presigned URLs para S3 (solución 63019) ---
def generar_url_video_accesible(bucket_name, object_name, expiration=3600, aws_access_key=None, aws_secret_key=None, region_name='us-east-1'):
    """
    Genera una URL temporal que Twilio SÍ puede leer.
    expiration: Tiempo en segundos (1 hora es suficiente para que Twilio lo descargue)
    """
    s3_client = boto3.client('s3',
        aws_access_key_id=aws_access_key or getattr(settings, 'AWS_ACCESS_KEY_ID', None),
        aws_secret_access_key=aws_secret_key or getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
        region_name=region_name
    )
    try:
        response = s3_client.generate_presigned_url('get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration
        )
        return response # Esta es la URL que le pasas a media_url en Twilio
    except NoCredentialsError:
        return None
import requests
from django.conf import settings
from django.utils import timezone
from .models import WhatsappLog


def enviar_whatsapp_twilio_content_template(telefono: str, content_sid: str, variables: dict) -> dict:
    """
    Enviar mensaje usando Twilio Content Template (aprobado por WhatsApp).
    
    Parámetros:
    - telefono: número en formato internacional, p.ej. '+573001234567'
    - content_sid: Content SID del template aprobado (ej: 'HX123abc...')
    - variables: dict con las variables del template (ej: {'1': 'Juan', '2': 'Mensaje'})
    
    Retorna dict con keys: success(bool), mensaje_id (str|None), response (str).
    """
    log = None
    
    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        # HARD-CODED para pruebas: usar siempre el número WhatsApp correcto
        twilio_number = 'whatsapp:+573202948806'
        
        if not account_sid or not auth_token:
            logger.error("Credenciales de Twilio NO configuradas")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}
        
        # Asegurar formato whatsapp:+57... para todos los destinatarios
        telefono_limpio = str(telefono).replace('whatsapp:', '').strip()
        if not telefono_limpio.startswith('+'):
            telefono_limpio = f'+{telefono_limpio}'
        telefono = f'whatsapp:{telefono_limpio}'
        
        logger.info(f"[TEMPLATE] Enviando a '{telefono}' con Content SID: {content_sid}")
        logger.debug(f"[VARIABLES] {variables}")
        logger.debug(f"FROM: '{twilio_number}' TO: '{telefono}'")
        
        # Crear cliente Twilio
        client = Client(account_sid, auth_token)
        
        # Construir mensaje de log legible
        mensaje_log = f"Template {content_sid}: {variables.get('2', 'Sin mensaje')}"
        
        # Guardar log preliminar
        log = WhatsappLog.objects.create(
            telefono=telefono.replace('whatsapp:', '').replace('+', ''),
            mensaje=mensaje_log,
            estado='PENDING',
            tipo='SENT',
            fecha=timezone.now()
        )
        
        # Enviar con Content Template (content_variables DEBE ser JSON string)
        import json
        msg_params = {
            'from_': twilio_number,
            'content_sid': content_sid,
            'to': telefono,
        }
        if variables:
            msg_params['content_variables'] = json.dumps(variables)

        try:
            message = client.messages.create(**msg_params)
        except Exception as send_err:
            err_txt = str(send_err)
            # Fallback para templates sin placeholders.
            if variables and 'Content Variables parameter is invalid' in err_txt:
                logger.warning(
                    f"Template {content_sid} rechazó variables; reintentando sin content_variables. "
                    f"Destino: {telefono}"
                )
                msg_params.pop('content_variables', None)
                message = client.messages.create(**msg_params)
            else:
                raise
        logger.info(f"Template enviado FROM: '{twilio_number}' TO: '{telefono}'")
        
        # Actualizar log con éxito
        log.mensaje_id = message.sid
        log.estado = 'SENT'
        log.save()
        
        logger.info(f"Template enviado OK SID: {message.sid}")
        
        return {'success': True, 'mensaje_id': message.sid, 'response': f'Sent: {message.status}'}
        
    except Exception as e:
        logger.error(f"Error al enviar template: {str(e)}")
        if log:
            log.estado = 'ERROR'
            log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}


def enviar_whatsapp_twilio(
    telefono: str,
    texto: str,
    mensaje_id_referencia: str = None,
    media_url: str = None,
    texto_log: str = None,
    from_number: str = None,
) -> dict:
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
        from .response_templates import dividir_contenido_seguro

        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        default_from = getattr(settings, 'TWILIO_PHONE_NUMBER', '573202948806')
        from_candidate = from_number if from_number else default_from
        twilio_number = str(formatear_numero_whatsapp(from_candidate)).strip()
        logger.info(f"[TWILIO] Account SID: {'...' + account_sid[-4:] if account_sid else None}")
        logger.info(f"[TWILIO] Auth Token: {'configured' if auth_token else 'MISSING'}")
        logger.info(f"[TWILIO] WhatsApp Number: '{twilio_number}'")

        if not account_sid or not auth_token:
            logger.error("Credenciales de Twilio NO configuradas")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}

        # Blindar el número destinatario contra error 21212
        telefono = str(formatear_numero_whatsapp(telefono)).strip()

        # S3 URLs: usar URL pública directa (bucket tiene ACL public-read)
        # NO generar presigned URL — causa 63019 por redirect de región
        if media_url and 'amazonaws.com' in media_url:
            # Asegurar que la URL use el endpoint regional correcto (sin redirects)
            if '.s3.amazonaws.com/' in media_url and '.s3.us-east-2.amazonaws.com/' not in media_url:
                media_url = media_url.replace('.s3.amazonaws.com/', '.s3.us-east-2.amazonaws.com/')
            logger.info(f"[S3] URL pública directa: {media_url[:100]}...")

        # Crear cliente Twilio
        client = Client(account_sid, auth_token)

        # Guardar log preliminar - usar texto_log si existe, sino usar texto
        mensaje_para_log = texto_log if texto_log else texto
        try:
            log = WhatsappLog.objects.create(
                telefono=telefono.replace('whatsapp:', '').replace('+', ''),
                mensaje=mensaje_para_log,
                mensaje_id=mensaje_id_referencia,
                estado='PENDING',
                tipo='SENT',
                fecha=timezone.now()
            )
        except Exception as log_err:
            logger.warning(f"No se pudo crear log preliminar: {log_err}")
            log = None

        # Preparar parámetros del mensaje
        max_chars = int(getattr(settings, 'TWILIO_MAX_BODY_CHARS', 1500) or 1500)
        # Límite operativo seguro de Twilio WhatsApp: 1600 chars.
        if max_chars < 200 or max_chars > 1590:
            max_chars = 1500

        texto = str(texto or '').strip()
        chunks = dividir_contenido_seguro(texto, max_chars=max_chars) if texto else ['']

        if not chunks and not media_url:
            return {'success': False, 'mensaje_id': None, 'response': 'Empty body and no media'}

        sent_messages = []
        clean_url = str(media_url).strip() if media_url else None
        if clean_url:
            logger.info(f"[MEDIA] Enviando con multimedia: {clean_url}")

        _caption_solo_media = (
            '📎 Aquí tienes el material (video, audio o archivo).\n'
            'Cuando lo revises, escribe *listo* para continuar.'
        )

        status_cb = str(getattr(settings, 'TWILIO_STATUS_CALLBACK_URL', '') or '').strip()

        for idx, chunk in enumerate(chunks):
            chunk_eff = (chunk or '').strip()
            if not chunk_eff and clean_url and idx == 0:
                chunk_eff = _caption_solo_media
            message_params = {
                'from_': twilio_number,
                'body': chunk_eff if chunk_eff else (' ' if clean_url else ''),
                'to': telefono,
            }
            if status_cb:
                message_params['status_callback'] = status_cb

            # Si hay multimedia, enviarla solo en el primer fragmento.
            if clean_url and idx == 0:
                message_params['media_url'] = [clean_url]

            try:
                message = client.messages.create(**message_params)
            except Exception as media_err:
                err_str = str(media_err)
                # Error 63019 = Twilio no pudo descargar el media.
                if '63019' in err_str and clean_url and idx == 0:
                    message_params.pop('media_url', None)
                    extra = f"\n\n📎 Archivo: {clean_url}"
                    body_with_fallback = (message_params.get('body') or '').strip()
                    message_params['body'] = f"{body_with_fallback}{extra}".strip()
                    message = client.messages.create(**message_params)
                else:
                    raise

            sent_messages.append(message)

        message = sent_messages[-1]
        logger.info(f"Enviado FROM: '{twilio_number}' TO: '{telefono}' ({len(sent_messages)} segmento(s))")

        if log:
            try:
                log.mensaje_id = message.sid
                log.estado = 'SENT'
                log.save()
            except Exception as log_err:
                logger.warning(f"No se pudo actualizar log: {log_err}")

        logger.info(f"TWILIO: Mensaje enviado a {telefono} - SID: {message.sid}")

        return {'success': True, 'mensaje_id': message.sid, 'response': 'Message sent'}
        
    except Exception as e:
        logger.error(f"Error enviando por Twilio: {str(e)}")
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
