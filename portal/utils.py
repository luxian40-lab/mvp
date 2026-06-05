import re

from django.conf import settings
from django.utils import timezone
from django.utils.text import get_valid_filename

LOGO_TIPOS_PERMITIDOS = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
LOGO_MAX_BYTES = 5 * 1024 * 1024


def limpiar_numero_whatsapp(numero):
    return re.sub(r'\D', '', str(numero or ''))


def guardar_logo_organizacion(uploaded_file, cliente_id: int) -> str:
    """Guarda el logo en el storage activo (S3 en producción) y devuelve URL pública."""
    from django.core.files.storage import default_storage

    content_type = getattr(uploaded_file, 'content_type', '') or ''
    if content_type and content_type not in LOGO_TIPOS_PERMITIDOS:
        raise ValueError('Solo se permiten imágenes JPG, PNG, WebP o GIF.')
    if uploaded_file.size > LOGO_MAX_BYTES:
        raise ValueError('La imagen no puede superar 5 MB.')

    now = timezone.now()
    filename = get_valid_filename(uploaded_file.name)
    path = f'portal/logos/{now:%Y/%m}/cliente_{cliente_id}_{now:%Y%m%d%H%M%S}_{filename}'
    saved_path = default_storage.save(path, uploaded_file)
    return default_storage.url(saved_path)


def enviar_whatsapp_respuesta(telefono_destino, mensaje):
    """
    Envía un mensaje WhatsApp usando las credenciales Twilio del proyecto.
    telefono_destino debe estar en formato: 573XXXXXXXXX.
    """
    try:
        from twilio.rest import Client

        whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', None) or getattr(
            settings,
            'TWILIO_WHATSAPP_NUMBER',
            '',
        )
        whatsapp_from = str(whatsapp_from).replace('whatsapp:', '').strip()

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=f'whatsapp:{whatsapp_from}',
            to=f'whatsapp:+{limpiar_numero_whatsapp(telefono_destino)}',
            body=mensaje,
        )
        return True
    except Exception as e:
        print(f'Error enviando WhatsApp: {e}')
        return False
