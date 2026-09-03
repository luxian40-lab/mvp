"""Storyboard por segundos — escena + tarjeta infográfica en un solo MP4."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'
_TIPOS_SEGMENTO = frozenset({'escena', 'tarjeta', 'escena_cierre'})


@dataclass
class SegmentoStoryboard:
    orden: int
    tipo: str
    duracion_seg: float
    guion: str
    subtitulo: str
    escena_visual: str = ''
    tarjeta_titulo: str = ''
    tarjeta_puntos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'orden': self.orden,
            'tipo': self.tipo,
            'duracion_seg': self.duracion_seg,
            'guion': self.guion,
            'subtitulo': self.subtitulo,
            'escena_visual': self.escena_visual,
            'tarjeta_titulo': self.tarjeta_titulo,
            'tarjeta_puntos': list(self.tarjeta_puntos),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SegmentoStoryboard:
        tipo = str(data.get('tipo', 'escena')).strip().lower()
        if tipo not in _TIPOS_SEGMENTO:
            tipo = 'escena'
        puntos = [str(p).strip() for p in (data.get('tarjeta_puntos') or []) if str(p).strip()]
        return cls(
            orden=int(data.get('orden', 1)),
            tipo=tipo,
            duracion_seg=float(data.get('duracion_seg') or 4),
            guion=str(data.get('guion', '')).strip(),
            subtitulo=str(data.get('subtitulo', '')).strip(),
            escena_visual=str(data.get('escena_visual', '')).strip(),
            tarjeta_titulo=str(data.get('tarjeta_titulo', '')).strip(),
            tarjeta_puntos=puntos[:5],
        )


@dataclass
class VideoLeccionPlan:
    titulo: str
    objetivo: str
    segmentos: list[SegmentoStoryboard]
    guion_completo: str
    categoria_visual: str = 'finanzas'
    duracion_objetivo_seg: float = 14.0
    modelo_ia: str = DEFAULT_MODEL

    def to_dict(self) -> dict[str, Any]:
        return {
            'titulo': self.titulo,
            'objetivo': self.objetivo,
            'guion_completo': self.guion_completo,
            'categoria_visual': self.categoria_visual,
            'duracion_objetivo_seg': self.duracion_objetivo_seg,
            'modelo_ia': self.modelo_ia,
            'segmentos': [s.to_dict() for s in self.segmentos],
        }

    @classmethod
    def from_dict(cls, data: dict) -> VideoLeccionPlan:
        segs = [SegmentoStoryboard.from_dict(s) for s in data.get('segmentos') or []]
        segs.sort(key=lambda x: x.orden)
        return cls(
            titulo=str(data.get('titulo', '')).strip(),
            objetivo=str(data.get('objetivo', '')).strip(),
            segmentos=segs,
            guion_completo=str(data.get('guion_completo', '')).strip(),
            categoria_visual=str(data.get('categoria_visual', 'finanzas')).strip(),
            duracion_objetivo_seg=float(data.get('duracion_objetivo_seg') or 14),
            modelo_ia=str(data.get('modelo_ia', DEFAULT_MODEL)),
        )


def _limpiar_json(raw: str) -> str:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _fallback_error1() -> VideoLeccionPlan:
    """Piloto determinístico — error 1 del manual de rentabilidad."""
    segs = [
        SegmentoStoryboard(
            1,
            'escena',
            4.0,
            'Sin reportes entre socios, el flujo de efectivo puede esconder una quiebra técnica.',
            'No rendir cuentas entre los socios',
            escena_visual=(
                'Dos socios jóvenes en oficina rural revisando cuaderno de gastos '
                'e ingresos en mesa de madera, calculadora y facturas'
            ),
        ),
        SegmentoStoryboard(
            2,
            'tarjeta',
            6.0,
            'Compartan ingresos y gastos cada mes. Un reporte común evita sorpresas y permite decidir a tiempo.',
            'Reportes claros entre socios',
            tarjeta_titulo='Error #1: Sin cuentas claras',
            tarjeta_puntos=[
                'Reporte mensual de ingresos y gastos',
                'Todos los socios ven los mismos números',
                'Decisiones con datos, no con intuición',
            ],
        ),
        SegmentoStoryboard(
            3,
            'escena_cierre',
            4.0,
            'Mida para decidir. La rentabilidad empieza con transparencia entre socios.',
            'Transparencia = rentabilidad',
            escena_visual=(
                'Socio rural cerrando cuaderno de finanzas con gesto de acuerdo, '
                'luz natural en bodega u oficina de finca'
            ),
        ),
    ]
    guion = ' '.join(s.guion for s in segs)
    return VideoLeccionPlan(
        titulo='Error 1: No rendir cuentas entre socios',
        objetivo='Entender por qué la transparencia financiera protege la rentabilidad',
        segmentos=segs,
        guion_completo=guion,
        categoria_visual='finanzas',
        duracion_objetivo_seg=14.0,
    )


def _system_prompt(target_sec: float) -> str:
    return f"""Eres experto en diseño instruccional para entornos virtuales de aprendizaje,
especialista en OVAs (objetos virtuales de aprendizaje), Microlearning, ABR (aprendizaje
basado en retos) y andragogía aplicada a poblaciones rurales. Diseñas un OVA de video
para eki (estilo Platzi en UN solo MP4).
NO diseñes mensajes de WhatsApp ni bloques de texto sueltos.

El video dura ~{target_sec:.0f} segundos con voz continua y subtítulos quemados abajo.
Estructura OBLIGATORIA (3 segmentos):
1. "escena" (~3-4s): plantea el RETO real que enfrenta el productor (ABR), no una
   introducción genérica. Foto documental con contexto (finanzas = oficina/cuadernos/socios).
2. "tarjeta" (~5-7s): lámina infográfica con título + 2-4 puntos accionables (campo
   tarjeta_puntos). Cada punto = algo que el adulto puede APLICAR, no una definición.
3. "escena_cierre" (~3-4s): misma línea visual; cierra con la transferencia al trabajo
   real ("qué hace distinto mañana"), no con una moraleja abstracta.

Principios de diseño instruccional (obligatorios):
- Microlearning: UN solo objetivo de aprendizaje observable por video. Si el brief trae
  varios temas, elige el más accionable y descarta el resto.
- "objetivo" = objetivo de aprendizaje en verbo observable (identificar, calcular,
  registrar, comparar). Nunca "conocer" ni "entender".
- Andragogía: el aprendiz es un adulto con experiencia y decisiones a su cargo. Habla de
  tú/usted con respeto, conecta con lo que YA sabe y hace. Nunca lo infantilices ni le
  des órdenes vacías.
- Población rural: lenguaje concreto y cotidiano del campo. Sin tecnicismos, anglicismos
  ni jerga corporativa. Ejemplos con cultivos, jornales, cosecha, insumos, cuadernos.
- ABR: el reto es el hilo conductor — problema real primero, herramienta después.

Reglas de forma:
- guion_completo = concatenación natural de los guion de cada segmento (narración TTS, ~35-55 palabras).
- subtitulo = misma frase que guion (voz y texto en pantalla van juntos).
- Finanzas/gestión → escena_visual: oficina rural, cuadernos, socios. NO cosecha salvo tema agro.
- Solo información del brief; no inventes cifras.

JSON:
{{"titulo","objetivo","categoria_visual":"finanzas|agro|otro","duracion_objetivo_seg":{target_sec:.0f},
"guion_completo","segmentos":[{{"orden","tipo","duracion_seg","guion","subtitulo",
"escena_visual","tarjeta_titulo","tarjeta_puntos":[]}}]}}
"""


def planificar_video_leccion(
    brief: str,
    rag_context: str = '',
    *,
    foco: str = '',
    target_sec: float = 14.0,
    modelo: str = DEFAULT_MODEL,
    openai_client=None,
) -> Optional[VideoLeccionPlan]:
    """Planifica un video único (escena → tarjeta → cierre) desde brief."""
    brief = (brief or '').strip()
    if not brief:
        return None

    target_sec = max(10.0, min(20.0, float(target_sec)))
    foco_txt = (foco or '').strip()
    user_parts = [f'Brief / material:\n{brief[:12000]}']
    if rag_context.strip():
        user_parts.append(f'\nContexto RAG:\n{rag_context[:5000]}')
    if foco_txt:
        user_parts.append(f'\nEnfócate en este punto del material:\n{foco_txt[:2000]}')
    user_parts.append(f'\nGenera storyboard para UN video de {target_sec:.0f}s.')

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': _system_prompt(target_sec)},
                {'role': 'user', 'content': '\n'.join(user_parts)},
            ],
            temperature=0.35,
            max_tokens=1800,
            response_format={'type': 'json_object'},
        )
        data = json.loads(_limpiar_json(resp.choices[0].message.content or '{}'))
    except Exception as exc:
        logger.warning('planificar_video_leccion fallback: %s', exc)
        if 'error 1' in foco_txt.lower() or 'no rendir cuentas' in brief.lower():
            return _fallback_error1()
        return _fallback_error1()

    segs = [SegmentoStoryboard.from_dict(s) for s in data.get('segmentos') or []]
    segs.sort(key=lambda x: x.orden)
    if len(segs) < 2:
        return _fallback_error1()

    # Asegurar al menos una tarjeta
    if not any(s.tipo == 'tarjeta' for s in segs):
        return _fallback_error1()

    guion = str(data.get('guion_completo', '')).strip()
    if not guion:
        guion = ' '.join(s.guion for s in segs if s.guion)

    cat = str(data.get('categoria_visual', 'finanzas')).lower().strip()
    if cat not in ('finanzas', 'agro', 'otro'):
        cat = 'finanzas'

    return VideoLeccionPlan(
        titulo=str(data.get('titulo') or foco_txt or brief[:80]).strip(),
        objetivo=str(data.get('objetivo', '')).strip(),
        segmentos=segs[:4],
        guion_completo=guion,
        categoria_visual=cat,
        duracion_objetivo_seg=target_sec,
        modelo_ia=modelo,
    )


def repartir_duracion_por_audio(
    plan: VideoLeccionPlan,
    audio_duracion_seg: float,
) -> list[tuple[SegmentoStoryboard, float, float]]:
    """
    Reparte la duración real del audio entre segmentos proporcionalmente
    a duracion_seg planificada.

    Returns:
        lista de (segmento, inicio_seg, duracion_seg)
    """
    total_plan = sum(max(0.5, s.duracion_seg) for s in plan.segmentos) or 1.0
    audio_dur = max(1.0, float(audio_duracion_seg))
    resultado: list[tuple[SegmentoStoryboard, float, float]] = []
    cursor = 0.0
    for i, seg in enumerate(plan.segmentos):
        if i == len(plan.segmentos) - 1:
            dur = max(0.5, audio_dur - cursor)
        else:
            dur = max(0.5, audio_dur * (seg.duracion_seg / total_plan))
        resultado.append((seg, cursor, dur))
        cursor += dur
    return resultado
