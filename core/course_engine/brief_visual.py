"""Planifica guion + escena visual alineados al contenido (micro-realista)."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'

_CATEGORIAS = frozenset({'finanzas', 'agro', 'otro'})


@dataclass
class ClipMicroPlan:
    titulo_corto: str
    guion_narracion: str
    escena_visual: str
    categoria_visual: str = 'otro'

    def to_dict(self) -> dict[str, str]:
        return {
            'titulo_corto': self.titulo_corto,
            'guion_narracion': self.guion_narracion,
            'escena_visual': self.escena_visual,
            'categoria_visual': self.categoria_visual,
        }


def _max_palabras_narracion(target_sec: float) -> int:
    if target_sec <= 11:
        return 40
    if target_sec <= 16:
        return 55
    return min(80, max(45, int(target_sec * 2.4)))


def _limpiar_json(raw: str) -> str:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _fallback_plan(brief: str, target_sec: float) -> ClipMicroPlan:
    """Sin IA: recorte simple (peor calidad visual)."""
    texto = re.sub(r'\s+', ' ', brief.strip())
    titulo = texto[:80].split('.')[0].strip() or 'Lección eki'
    max_w = _max_palabras_narracion(target_sec)
    words = texto.split()
    guion = ' '.join(words[:max_w])
    if guion and not guion.endswith('.'):
        guion += '.'
    from core.course_engine.visual_style import inferir_categoria_visual

    cat = inferir_categoria_visual(texto)
    escena = (
        'Emprendedor rural en escritorio revisando cuaderno de costos y calculadora, '
        'bodega o finca al fondo'
        if cat == 'finanzas'
        else f'Escena educativa coherente con: {titulo}'
    )
    return ClipMicroPlan(
        titulo_corto=titulo[:80],
        guion_narracion=guion,
        escena_visual=escena,
        categoria_visual=cat,
    )


def planificar_clip_micro(
    brief: str,
    *,
    target_sec: float = 15.0,
    modelo: str = DEFAULT_MODEL,
    openai_client=None,
) -> ClipMicroPlan:
    """
    A partir de brief corto o capítulo largo, devuelve narración TTS + escena visual
    coherente (finanzas ≠ cosecha).
    """
    brief = (brief or '').strip()
    if not brief:
        raise ValueError('Brief vacío')

    max_palabras = _max_palabras_narracion(target_sec)
    system = (
        'Eres director de video educativo de eki para emprendedores rurales en Colombia. '
        'El video debe ser coherente: si el texto habla de finanzas, rentabilidad, costos, '
        'cobranza o gestión empresarial, la escena visual debe mostrar oficina rural, '
        'cuadernos, calculadora, facturas o reuniones de socios — NUNCA cosecha o campo '
        'salvo que el texto sea explícitamente agrícola.'
    )
    user = f"""Contenido de la lección:
---
{brief[:12000]}
---

Duración objetivo del video: {target_sec:.0f} segundos.
Máximo {max_palabras} palabras en guion_narracion.

Responde SOLO JSON:
{{
  "titulo_corto": "título breve de la lección",
  "guion_narracion": "narración en español sencillo, directa, con cifras o ideas del texto",
  "escena_visual": "descripción de UNA foto documental concreta (quién, qué objetos, dónde)",
  "categoria_visual": "finanzas|agro|otro"
}}"""

    try:
        if openai_client is None:
            from django.conf import settings
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            temperature=0.35,
            max_tokens=700,
            response_format={'type': 'json_object'},
        )
        raw = resp.choices[0].message.content or ''
        data: dict[str, Any] = json.loads(_limpiar_json(raw))
    except Exception as exc:
        logger.warning('planificar_clip_micro fallback: %s', exc)
        return _fallback_plan(brief, target_sec)

    cat = str(data.get('categoria_visual', 'otro')).lower().strip()
    if cat not in _CATEGORIAS:
        cat = 'otro'

    guion = str(data.get('guion_narracion', '')).strip()
    words = guion.split()
    if len(words) > max_palabras:
        guion = ' '.join(words[:max_palabras]).rstrip(',;:') + '.'

    plan = ClipMicroPlan(
        titulo_corto=str(data.get('titulo_corto', '')).strip()[:120] or 'Lección eki',
        guion_narracion=guion or _fallback_plan(brief, target_sec).guion_narracion,
        escena_visual=str(data.get('escena_visual', '')).strip(),
        categoria_visual=cat,
    )
    if not plan.escena_visual:
        plan.escena_visual = _fallback_plan(brief, target_sec).escena_visual
    return plan
