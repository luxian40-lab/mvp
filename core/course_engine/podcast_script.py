"""Guion podcast largo desde lección (misma fuente RAG)."""
from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings

from core.course_engine.types import LessonDraft

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'


def generar_guion_podcast(
    lesson: LessonDraft,
    *,
    minutos_objetivo: int = 2,
    modelo: str = DEFAULT_MODEL,
    openai_client=None,
) -> Optional[str]:
    """2–4 min monólogo agrícola para WhatsApp / audio."""
    if openai_client is None:
        from core.course_engine.openai_guard import validar_openai_disponible

        validar_openai_disponible(modelo)

    mins = minutos_objetivo if minutos_objetivo in (2, 3, 4) else 2
    palabras = {2: 280, 3: 420, 4: 560}.get(mins, 280)

    system = (
        'Eres locutor de microlearning agrícola eki (WhatsApp rural, español claro). '
        'Escribe un monólogo para audio/podcast basado SOLO en la lección. '
        'Tono cercano, frases cortas, sin markdown. '
        f'Objetivo ~{palabras} palabras (~{mins} min). '
        'Responde JSON: {"guion": "texto continuo"}'
    )
    payload = {
        'titulo': lesson.titulo,
        'contenido': lesson.contenido,
        'puntos_clave': lesson.puntos_clave,
    }

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.5,
            response_format={'type': 'json_object'},
        )
        data = json.loads(resp.choices[0].message.content or '{}')
        guion = str(data.get('guion', '')).strip()
        return guion or None
    except Exception as exc:
        logger.exception('generar_guion_podcast: %s', exc)
        return None
