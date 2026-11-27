"""G4: LLM del turno en cola `llm` con respuesta diferida.

Flag off: completar_chat síncrono (comportamiento actual).
Flag on: encola la llamada y quien envía manda la respuesta al terminar.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

MARCA_RESPUESTA_DIFERIDA = '[EKI_LLM_DIFERIDO]'


def respuesta_diferida_activa() -> bool:
    return bool(getattr(settings, 'EKI_LLM_RESPUESTA_DIFERIDA', False))


def es_respuesta_diferida(texto: str | None) -> bool:
    return (texto or '') == MARCA_RESPUESTA_DIFERIDA


def completar_chat_o_diferir(
    client,
    modelo: str,
    messages: list,
    max_out: int,
    *,
    telefono: str,
    agente: str,
    from_number: str = '',
    temperature: float | None = None,
    post_asesor: bool = False,
    body: str = '',
    derivado: bool = False,
    agente_secundario: str = '',
) -> str:
    """Igual que completar_chat; con el flag on encola y devuelve la marca."""
    from core.agentes.openai_compat import completar_chat

    if not respuesta_diferida_activa():
        return completar_chat(client, modelo, messages, max_out, temperature)

    from core.tasks import ejecutar_llm_turno_whatsapp_async

    payload: dict[str, Any] = {
        'modelo': modelo,
        'messages': messages,
        'max_out': max_out,
        'temperature': temperature,
        'telefono': telefono,
        'agente': agente,
        'from_number': from_number or '',
        'post_asesor': bool(post_asesor),
        'body': body or '',
        'derivado': bool(derivado),
        'agente_secundario': agente_secundario or '',
    }
    ejecutar_llm_turno_whatsapp_async.delay(**payload)
    logger.info('llm_diferido_encolado telefono=***%s agente=%s', (telefono or '')[-4:], agente)
    return MARCA_RESPUESTA_DIFERIDA