import math
import requests
from django.conf import settings
from django.utils import timezone
from .models import WhatsappLog


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en metros entre dos coordenadas usando la fórmula de Haversine.

    Parámetros:
    - lat1, lon1: coordenadas del punto de origen (ej. estudiante)
    - lat2, lon2: coordenadas del punto destino (ej. empresa aliada)

    Retorna la distancia en metros (float).
    """
    R = 6_371_000  # Radio de la Tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


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
