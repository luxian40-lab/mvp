"""Salida del turno de curso: Meta si el canal es Meta; Twilio solo fuera de ese turno.

El producto vive en Cloud API. Twilio no es canal de lección ni de Formador.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def enviar_respuesta_turno(
    telefono: str,
    texto: str,
    *,
    media_url: str | None = None,
    agente: str = 'curso',
) -> dict:
    """Una respuesta del motor. En Meta no abre el Client de Twilio."""
    from core.views.twilio_transporte import turno_sale_por_meta

    if turno_sale_por_meta():
        from core.sandbox_canal import enviar_meta

        return enviar_meta(
            telefono,
            texto or '',
            media_url=media_url,
            canal_evento='whatsapp_sandbox',
            agente_evento=agente or 'curso',
        )
    from core.utils import enviar_whatsapp_twilio

    return enviar_whatsapp_twilio(
        telefono,
        texto or '',
        media_url=media_url,
        canal_evento='whatsapp',
        agente_evento=agente or 'curso',
    )
