"""Storyboard automático — eki decide tipo de escena."""
from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings

from core.course_engine.types import LessonAnalysis, LessonDraft, Scene, SceneType, Storyboard

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'

_SCENE_VALUES = {t.value for t in SceneType}

_SYSTEM = """Eres director de microlearning eki. Convierte la lección en storyboard.
Cada escena debe tener: orden (int), tipo, titulo, guion (narración o texto en pantalla),
duracion_seg (float), notas_visuales.

Tipos permitidos (exacto):
- imagen, imagen_zoom, diagrama, video_ia, texto, narracion, transicion, resumen

Reglas:
- Empieza con transicion o imagen; cierra con resumen.
- narracion = voz off (ElevenLabs); texto = solo pantalla.
- video_ia solo si el concepto lo exige (máx 1 escena).
- 5–10 escenas total; guiones cortos (WhatsApp rural).
- CRITICO: todo el contenido (guion, notas_visuales, titulo) debe ser especifico al tema de la leccion.
  NO uses definiciones genericas de agricultura ni texto de relleno ajeno al brief.
- Para tipo texto: guion = frase corta exacta del tema (max 15 palabras); notas_visuales = fondo visual concreto del cultivo/tema.
- notas_visuales debe describir QUE SE VE (cultivo, accion, lugar), no definiciones enciclopedicas.

Responde JSON: { "titulo_leccion", "objetivo", "escenas": [...] }
"""


def generar_storyboard(
    lesson: LessonDraft,
    analysis: LessonAnalysis,
    *,
    modelo: str = DEFAULT_MODEL,
    tier: str = 'economico',
    openai_client=None,
) -> Optional[Storyboard]:
    if openai_client is None:
        from core.course_engine.openai_guard import validar_openai_disponible

        validar_openai_disponible(modelo)

    payload = {
        'leccion': lesson.to_dict(),
        'analisis': analysis.to_dict(),
        'tier': tier,
        'reglas_video': (
            'Cada escena visual debe incluir guion (narración) y notas_visuales (qué mostrar). '
            'NO uses video_ia en tier economico — usa imagen_zoom en su lugar. '
            'Prioriza imagen y diagrama; zoom antes que video. '
            'Duración total objetivo ~60-90 segundos.'
        ),
    }

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': _SYSTEM},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.5,
            response_format={'type': 'json_object'},
        )
        data = json.loads(resp.choices[0].message.content or '{}')
    except Exception as exc:
        logger.exception('generar_storyboard: %s', exc)
        return None

    escenas: list[Scene] = []
    for raw in data.get('escenas') or []:
        tipo_str = str(raw.get('tipo', 'texto')).strip().lower()
        if tipo_str not in _SCENE_VALUES:
            tipo_str = 'texto'
        escenas.append(
            Scene(
                orden=int(raw.get('orden', len(escenas) + 1)),
                tipo=SceneType(tipo_str),
                titulo=str(raw.get('titulo', '')).strip(),
                guion=str(raw.get('guion', '')).strip(),
                duracion_seg=float(raw.get('duracion_seg') or 5),
                notas_visuales=str(raw.get('notas_visuales', '')).strip(),
            )
        )

    escenas.sort(key=lambda s: s.orden)
    if not escenas:
        return None

    return Storyboard(
        titulo_leccion=str(data.get('titulo_leccion') or lesson.titulo).strip(),
        objetivo=str(data.get('objetivo', '')).strip(),
        escenas=escenas,
        modelo_ia=modelo,
    )
