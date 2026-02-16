# --- Generador de presigned URL con Content-Type correcto para S3 ---

import boto3
from botocore.config import Config
from django.conf import settings


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
                'ResponseContentType': 'video/mp4'
            },
            ExpiresIn=expiration
        )
        print(f"[DEBUG Presigned URL] {response}")
        return response
    except Exception as e:
        print(f"Error: {e}")
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
            print("[ERROR] Credenciales de Twilio NO configuradas")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}
        
        # Asegurar formato whatsapp:+57... para todos los destinatarios
        if not str(telefono).startswith('whatsapp:'):
            telefono = f'whatsapp:{str(telefono).replace("whatsapp:", "").replace("+", "")}'
        
        print(f"[TEMPLATE] Enviando a '{telefono}' con Content SID: {content_sid}")
        print(f"[VARIABLES] {variables}")
        print(f"[DEPURACION] FROM: '{twilio_number}' TO: '{telefono}' (verifica espacios invisibles)")
        
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
        
        # Enviar con Content Template
        message = client.messages.create(
            from_=twilio_number,
            content_sid=content_sid,
            content_variables=variables,
            to=telefono
        )
        print(f"[DEPURACION] Enviado con FROM: '{twilio_number}' TO: '{telefono}'")
        
        # Actualizar log con éxito
        log.mensaje_id = message.sid
        log.estado = 'SENT'
        log.save()
        
        print(f"[SUCCESS] Mensaje enviado con SID: {message.sid}")
        
        return {'success': True, 'mensaje_id': message.sid, 'response': f'Sent: {message.status}'}
        
    except Exception as e:
        print(f"[ERROR] Error al enviar template: {str(e)}")
        if log:
            log.estado = 'ERROR'
            log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}


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
        from .utils import formatear_numero_whatsapp, generar_url_video_accesible

        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        twilio_number = str(formatear_numero_whatsapp('573202948806')).strip()
        print(f"[TWILIO] Account SID: {account_sid}")
        print(f"[TWILIO] Auth Token: {auth_token[:20] if auth_token else None}...")
        print(f"[TWILIO] WhatsApp Number: '{twilio_number}'")

        if not account_sid or not auth_token:
            print("[ERROR] Credenciales de Twilio NO configuradas")
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials not set'}

        # Blindar el número destinatario contra error 21212
        telefono = str(formatear_numero_whatsapp(telefono)).strip()

        # Si la media_url es de S3, generar presigned URL con Content-Type correcto
        if media_url and 'amazonaws.com' in media_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(media_url)
                # Soportar formato: bucket.s3.region.amazonaws.com/key
                # y formato: s3.region.amazonaws.com/bucket/key
                host_parts = parsed.netloc.split('.')
                if host_parts[0] == 's3':
                    # s3.region.amazonaws.com/bucket/key
                    path_parts = parsed.path.lstrip('/').split('/', 1)
                    bucket = path_parts[0]
                    key = path_parts[1] if len(path_parts) > 1 else ''
                else:
                    # bucket.s3.region.amazonaws.com/key
                    bucket = host_parts[0]
                    key = parsed.path.lstrip('/')
                
                # Detectar Content-Type según extensión
                ext = key.rsplit('.', 1)[-1].lower() if '.' in key else ''
                content_types = {
                    'mp4': 'video/mp4', 'mov': 'video/quicktime', 'avi': 'video/x-msvideo',
                    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'gif': 'image/gif', 'webp': 'image/webp',
                    'pdf': 'application/pdf',
                    'mp3': 'audio/mpeg', 'ogg': 'audio/ogg', 'wav': 'audio/wav',
                }
                response_content_type = content_types.get(ext, None)
                
                # Generar presigned URL con Content-Type
                presigned_params = {'Bucket': bucket, 'Key': key}
                if response_content_type:
                    presigned_params['ResponseContentType'] = response_content_type
                
                media_url = generar_url_firmada_s3_v4(bucket, key)
                print(f"[S3] Presigned URL generada para {ext}: {media_url[:100]}...")
            except Exception as e:
                print(f"[S3] Error generando presigned URL, usando URL original: {e}")

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
            print(f"[WARNING] No se pudo crear log preliminar: {log_err}")
            log = None

        # Preparar parámetros del mensaje
        message_params = {
            'from_': twilio_number,
            'body': texto,
            'to': telefono
        }

        # Agregar media_url si se proporcionó (video, imagen, PDF, etc.)
        if media_url:
            clean_url = str(media_url).strip()
            message_params['media_url'] = [clean_url]
            print(f"[MEDIA] Enviando con multimedia: {clean_url}")

        # Enviar mensaje (con o sin media)
        message = client.messages.create(**message_params)
        print(f"[DEPURACION] Enviado con FROM: '{twilio_number}' TO: '{telefono}'")

        if log:
            try:
                log.mensaje_id = message.sid
                log.estado = 'SENT'
                log.save()
            except Exception as log_err:
                print(f"[WARNING] No se pudo actualizar log: {log_err}")

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
