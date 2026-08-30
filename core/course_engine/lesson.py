"""Generación de lección con OpenAI + contexto RAG."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from django.conf import settings

from core.course_engine.types import LessonDraft

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'

_LESSON_SCHEMA = {
    'titulo': 'string',
    'contenido': 'string markdown breve',
    'puntos_clave': ['string', '...'],
}


def generar_leccion(
    brief: str,
    rag_context: str,
    *,
    modelo: str = DEFAULT_MODEL,
    openai_client=None,
) -> Optional[LessonDraft]:
    """Brief + RAG → borrador de lección."""
    if openai_client is None:
        from core.course_engine.openai_guard import validar_openai_disponible

        validar_openai_disponible(modelo)
    brief = (brief or '').strip()
    if not brief:
        return None

    system = (
        'Eres diseñador instruccional de eki (WhatsApp rural, español claro). '
        'Genera UNA lección corta basada en el brief y la base documental. '
        'Responde SOLO JSON válido con keys: titulo, contenido, puntos_clave (lista).'
    )
    user_parts = [f'Brief del cliente:\n{brief}']
    if rag_context:
        user_parts.append(f'Base documental (RAG empresa/curso):\n{rag_context[:8000]}')
    else:
        user_parts.append('(Sin contexto RAG — usa solo el brief; sé conservador.)')

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': '\n\n'.join(user_parts)},
            ],
            temperature=0.4,
            response_format={'type': 'json_object'},
        )
        raw = resp.choices[0].message.content or '{}'
        data = json.loads(raw)
    except Exception as exc:
        logger.exception('generar_leccion OpenAI: %s', exc)
        return None

    return LessonDraft(
        titulo=str(data.get('titulo', 'Lección')).strip(),
        contenido=str(data.get('contenido', '')).strip(),
        puntos_clave=[str(p).strip() for p in (data.get('puntos_clave') or []) if str(p).strip()],
        rag_chars=len(rag_context or ''),
    )
