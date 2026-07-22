"""Visión Nat: leer foto de cultivo (Twilio) y devolver hipótesis prudentes."""
from __future__ import annotations

import base64
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_PROMPT_VISION = (
    "Usted es agrónoma de campo en Colombia. Observe la imagen del cultivo "
    "y oriente al productor SIN cerrar un diagnóstico.\n\n"
    "Reglas:\n"
    "- Empiece SIEMPRE por lo visible (fruta, hoja, tallo, color, orificios, "
    "podredumbre, excretas, moho, manchas). Sea concreto.\n"
    "- Luego liste 2 a 4 POSIBLES causas basadas en lo que se ve. "
    "Puede nombrar sospechas típicas de campo (ej. larva barrenadora, tizón, "
    "pudrición secundaria) siempre como hipótesis, nunca como certeza.\n"
    "- Nunca diga 'es X' ni 'definitivamente'. Use 'puede ser', 'compatible con', "
    "'conviene descartar'.\n"
    "- La decisión de manejo es del productor; usted solo informa.\n"
    "- Trate de usted. Lenguaje claro de campo. 8–14 líneas máximo.\n\n"
    "Formato exacto:\n"
    "*Lo que se observa:* …\n"
    "*Posibles causas:*\n"
    "1) …\n"
    "2) …\n"
    "3) … (si aplica)\n"
    "*Qué conviene verificar en finca:* …\n"
    "*Importante:* esta orientación no reemplaza una visita técnica; "
    "usted decide con lo que ve en su cultivo."
)


def _mime_imagen(media_type: str) -> str:
    raw = (media_type or '').split(';')[0].strip().lower()
    if raw in ('image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'):
        return 'image/jpeg' if raw == 'image/jpg' else raw
    if 'png' in raw:
        return 'image/png'
    if 'webp' in raw:
        return 'image/webp'
    return 'image/jpeg'


def url_vision_desde_twilio(media_url: str, media_type: str) -> str:
    """
    Twilio MediaUrl exige auth básica; OpenAI no puede abrirla directa.
    Descarga y devuelve data URL base64 para el modelo de visión.
    """
    if not media_url:
        return ''
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '') or ''
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '') or ''
    try:
        import requests

        kwargs = {'timeout': 25}
        if account_sid and auth_token:
            kwargs['auth'] = (account_sid, auth_token)
        resp = requests.get(media_url, **kwargs)
        resp.raise_for_status()
        raw = resp.content or b''
        if not raw:
            return ''
        # Límite práctico (~4 MB) para no saturar el completion
        if len(raw) > 4 * 1024 * 1024:
            logger.warning('Nat visión: imagen demasiado grande (%s bytes)', len(raw))
            return ''
        mime = _mime_imagen(media_type or resp.headers.get('Content-Type', ''))
        b64 = base64.b64encode(raw).decode('ascii')
        return f'data:{mime};base64,{b64}'
    except Exception as exc:
        logger.warning('Nat visión: no se pudo descargar media Twilio: %s', exc)
        return ''


def diagnosticar_imagen_cultivo(media_url: str, media_type: str, cliente=None) -> str:
    """Diagnóstico preliminar por visión: hipótesis, nunca veredicto cerrado."""
    if not media_url or not (media_type or '').startswith('image'):
        return ''

    from core.ai_capabilities import resolver_ai_capability

    if not resolver_ai_capability('diagnostico_agro', cliente=cliente):
        return (
            "Recibí su foto. El análisis visual automático no está habilitado "
            "para su organización; describa los síntomas y el cultivo, por favor."
        )

    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return "Recibí su foto. El análisis visual no está disponible en este momento."

    vision_url = url_vision_desde_twilio(media_url, media_type)
    if not vision_url:
        # Fallback: intentar URL directa (útil en tests / URLs públicas)
        vision_url = media_url

    try:
        from openai import OpenAI
        from core.openai_compat import chat_completion_token_kwargs

        client = OpenAI(api_key=api_key)
        vision_model = getattr(settings, 'BOT_COMERCIAL_VISION_MODEL', 'gpt-4o-mini')
        resp = client.chat.completions.create(
            model=vision_model,
            messages=[
                {'role': 'system', 'content': _PROMPT_VISION},
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': (
                                'Analice esta foto del cultivo. '
                                'Dé posibles causas y qué verificar; no cierre diagnóstico.'
                            ),
                        },
                        {'type': 'image_url', 'image_url': {'url': vision_url}},
                    ],
                },
            ],
            **chat_completion_token_kwargs(vision_model, 420, 0.2),
        )
        return (resp.choices[0].message.content or '').strip()
    except Exception as exc:
        logger.warning('Nat visión no disponible: %s', exc)
        return (
            "Recibí su foto, pero no pude completar el análisis visual ahora. "
            "Describa los síntomas y el cultivo, por favor."
        )
