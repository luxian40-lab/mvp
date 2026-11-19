"""Salida del turno de curso: Meta si el canal es Meta; Twilio solo fuera de ese turno.

El producto vive en Cloud API. Twilio no es canal de lección ni de Formador.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_MEDIA = re.compile(r'\[MEDIA:(.*?)\]')


def enviar_respuesta_turno(
    telefono: str,
    texto: str,
    *,
    media_url: str | None = None,
    agente: str = 'curso',
) -> dict:
    """Una respuesta del motor. En Meta no abre el Client de Twilio.

    Sale por el Sender de la línea (claim/outbox cuando el flag está on).
    """
    from core.views.twilio_transporte import turno_sale_por_meta

    if turno_sale_por_meta():
        from core.lineas.envio import enviar_respuesta_linea

        return enviar_respuesta_linea(
            telefono,
            texto or '',
            media_url=media_url,
            agente=agente or 'curso',
        )
    from core.utils import enviar_whatsapp_twilio

    return enviar_whatsapp_twilio(
        telefono,
        texto or '',
        media_url=media_url,
        canal_evento='whatsapp',
        agente_evento=agente or 'curso',
    )


def entregar_en_turno(
    msg_from: str,
    telefono_limpio: str,
    texto: str,
    *,
    agente: str = 'curso',
    registro: str = 'segmentos',
) -> dict:
    """Texto simple o [MULTI_MSG]/[MEDIA:] por el canal del turno."""
    original = texto or ''
    if original.startswith('[MULTI_MSG]'):
        from core.lineas.entrega import enviar_marcado

        enviar_marcado(msg_from, telefono_limpio, original, registro=registro)
        return {'success': True, 'mensaje_id': None, 'response': 'marcado'}

    media_url = None
    cuerpo = original
    hallada = _MEDIA.search(cuerpo)
    if hallada:
        media_url = (hallada.group(1) or '').strip() or None
        cuerpo = cuerpo.replace(hallada.group(0), '').strip()
    return enviar_respuesta_turno(
        msg_from,
        cuerpo,
        media_url=media_url,
        agente=agente,
    )
