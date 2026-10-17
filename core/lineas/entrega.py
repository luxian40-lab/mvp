"""Entrega del curso: un solo lector de marcas, dos registros distintos.

Confirmación anota cada segmento. La selección de curso anota una vez al final.
Eso no se unifica: los tests de cada camino dependen de esa diferencia.
"""
from __future__ import annotations

import re
import time

from django.conf import settings


def enviar_marcado(msg_from: str, telefono_limpio: str, texto: str, *, registro: str) -> None:
    """Envía texto con [MULTI_MSG], [SEP], [DELAY], [SEND_TEMPLATE] y [MEDIA:].

    registro='segmentos' — log por segmento; el texto sin marcas sale en un create.
    registro='cierre' — un log al final; el texto sin marcas también se segmenta.
    """
    from core.models import WhatsappLog
    from core.views.twilio_transporte import _enviar_mensaje_twilio_segmentado

    from twilio.rest import Client as TwilioClient

    original = texto or ''
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
    client_tw = TwilioClient(account_sid, auth_token)
    destino = f'whatsapp:{msg_from}' if not str(msg_from).startswith('whatsapp:') else msg_from
    origen = str(twilio_number).strip()
    destino = str(destino).strip()

    if original.startswith('[MULTI_MSG]'):
        partes = original.replace('[MULTI_MSG]', '', 1).split('[SEP]')
        for parte in partes:
            parte_texto = (parte or '').strip()
            if not parte_texto:
                continue
            delay_m = re.match(r'^\[DELAY:(\d+)\]$', parte_texto)
            if delay_m:
                time.sleep(int(delay_m.group(1)))
                continue
            if parte_texto.startswith('[SEND_TEMPLATE:'):
                tmpl_m = re.match(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]', parte_texto)
                if tmpl_m:
                    from core.whatsapp_service import enviar_template_twilio

                    tel_limpio_t = str(msg_from).replace('whatsapp:', '').replace('+', '')
                    enviar_template_twilio(tel_limpio_t, tmpl_m.group(1))
                time.sleep(0.5)
                continue
            parte_media = None
            media_m = re.search(r'\[MEDIA:(.*?)\]', parte_texto)
            if media_m:
                parte_media = (media_m.group(1) or '').strip()
                parte_texto = parte_texto.replace(media_m.group(0), '').strip()
            enviados = _enviar_mensaje_twilio_segmentado(
                client=client_tw,
                from_number=origen,
                to_number=destino,
                body=parte_texto,
                media_url=parte_media,
            )
            time.sleep(0.5)
            if registro == 'segmentos':
                from core.twilio_media import mensaje_log_con_media

                for seg_i, (msg_sent, texto_env) in enumerate(enviados, start=1):
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=mensaje_log_con_media(
                            texto_env or parte_texto,
                            parte_media if seg_i == 1 else None,
                        )[:1500],
                        mensaje_id=getattr(msg_sent, 'sid', None),
                        tipo='SENT',
                    )
        if registro == 'cierre':
            WhatsappLog.objects.create(
                telefono=telefono_limpio, mensaje=original[:500], tipo='SENT',
            )
        return

    if registro == 'cierre':
        parte_texto = original
        parte_media = None
        media_m = re.search(r'\[MEDIA:(.*?)\]', parte_texto)
        if media_m:
            parte_media = (media_m.group(1) or '').strip()
            parte_texto = parte_texto.replace(media_m.group(0), '').strip()
        _enviar_mensaje_twilio_segmentado(
            client=client_tw,
            from_number=origen,
            to_number=destino,
            body=parte_texto,
            media_url=parte_media,
        )
        WhatsappLog.objects.create(
            telefono=telefono_limpio, mensaje=original[:500], tipo='SENT',
        )
        return

    client_tw.messages.create(body=original, from_=origen, to=destino)
    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=original, tipo='SENT')
