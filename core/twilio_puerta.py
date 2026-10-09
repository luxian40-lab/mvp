"""Twilio solo entrega el código de *aula*. El curso entra por Meta."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

TEXTO_CERRADO = (
    'Este número solo entrega el código del aula. '
    'Escribe *aula* para recibirlo. El curso sigue en la línea de eki en Meta.'
)
TEXTO_SIN_ESTUDIANTE = (
    'No encontramos ese número en eki. '
    'Escribe *aula* desde el WhatsApp con el que te inscribiste.'
)
TEXTO_CODIGO_FALLO = 'No pude generar el código. Escribe *aula* otra vez.'


def _hay_mensaje(post_data) -> bool:
    if (post_data.get('Body') or '').strip():
        return True
    try:
        if int(post_data.get('NumMedia') or 0) > 0:
            return True
    except (TypeError, ValueError):
        return False
    return bool(
        post_data.get('ButtonPayload')
        or post_data.get('ButtonText')
        or post_data.get('ListId')
        or post_data.get('ListTitle')
    )


def _enviar_twilio(post_data, texto: str, agente: str) -> None:
    destino = (post_data.get('From') or '').strip()
    if not destino or not texto:
        return
    from core.utils import enviar_whatsapp_twilio

    enviar_whatsapp_twilio(destino, texto, agente_evento=agente)


def _enviar_codigo_twilio(post_data) -> None:
    from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp
    from core.nati import normalizar_telefono_whatsapp
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(normalizar_telefono_whatsapp(post_data.get('From', '')))
    if est is None:
        _enviar_twilio(post_data, TEXTO_SIN_ESTUDIANTE, 'aula_twilio')
        return
    try:
        texto = emitir_acceso_desde_whatsapp(est)
    except Exception:
        logger.exception('aula_twilio_emit_fail')
        _enviar_twilio(post_data, TEXTO_CODIGO_FALLO, 'aula_twilio')
        return
    _enviar_twilio(post_data, texto, 'aula_twilio')


def aplicar_puerta_twilio(post_data) -> str:
    """'seguir' solo para callbacks de estado. 'aula' y 'cerrado' no entran al curso."""
    data = post_data or {}
    from core.views.twilio_transporte import _es_status_callback_twilio

    if _es_status_callback_twilio(data):
        return 'seguir'
    from aprende.acceso_whatsapp import mensaje_pide_acceso_aula
    from core.habeas_respuestas import texto_desde_webhook_twilio

    body = texto_desde_webhook_twilio(data, data.get('Body', '') or '')
    if mensaje_pide_acceso_aula(body):
        _enviar_codigo_twilio(data)
        return 'aula'
    if _hay_mensaje(data):
        _enviar_twilio(data, TEXTO_CERRADO, 'twilio_cerrado')
    return 'cerrado'


def responder_aula_meta(post_data) -> bool:
    """True si era *aula* y el código salió por Meta. Sin estudiante, el menú sigue."""
    data = post_data or {}
    from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp, mensaje_pide_acceso_aula
    from core.habeas_respuestas import texto_desde_webhook_twilio

    body = texto_desde_webhook_twilio(data, data.get('Body', '') or '')
    if not mensaje_pide_acceso_aula(body):
        return False
    from core.nati import normalizar_telefono_whatsapp
    from core.utils_telefono import estudiante_por_telefono

    est = estudiante_por_telefono(normalizar_telefono_whatsapp(data.get('From', '')))
    if est is None:
        return False
    try:
        texto = emitir_acceso_desde_whatsapp(est)
    except Exception:
        logger.exception('aula_meta_emit_fail')
        return False
    from core.sandbox_canal import enviar_meta

    enviar_meta(
        data.get('From', ''),
        texto,
        canal_evento='aprende',
        agente_evento='aula_meta',
    )
    return True
