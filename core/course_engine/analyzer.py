"""Analizador pedagógico de la lección (pre-storyboard)."""
from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings

from core.course_engine.types import LessonAnalysis, LessonDraft

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'


def analizar_leccion(
    lesson: LessonDraft,
    *,
    modelo: str = DEFAULT_MODEL,
    openai_client=None,
) -> Optional[LessonAnalysis]:
    if openai_client is None:
        from core.course_engine.openai_guard import validar_openai_disponible

        validar_openai_disponible(modelo)

    system = (
        'Analiza la lección para video microlearning WhatsApp (≤3 min ideal). '
        'JSON: audiencia, duracion_estimada_min (int), conceptos (lista), '
        'riesgos_pedagogicos (lista), recomendacion_formato (string).'
    )
    user = json.dumps(lesson.to_dict(), ensure_ascii=False)

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            temperature=0.3,
            response_format={'type': 'json_object'},
        )
        data = json.loads(resp.choices[0].message.content or '{}')
    except Exception as exc:
        logger.exception('analizar_leccion: %s', exc)
        return None

    return LessonAnalysis(
        audiencia=str(data.get('audiencia', 'Estudiantes rurales')).strip(),
        duracion_estimada_min=int(data.get('duracion_estimada_min') or 3),
        conceptos=[str(c) for c in (data.get('conceptos') or [])],
        riesgos_pedagogicos=[str(r) for r in (data.get('riesgos_pedagogicos') or [])],
        recomendacion_formato=str(data.get('recomendacion_formato', 'mixto')).strip(),
    )
