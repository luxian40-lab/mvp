"""Secuencia interactiva WA — bloques estilo Platzi + micro_video desde RAG + brief."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'

# Tipos alineados a clase Platzi: resumen → sección (pregunta) → texto → definición → micro_video
_TIPOS_BLOQUE = frozenset({
    'resumen',
    'seccion',
    'texto',
    'definicion',
    'lista',
    'micro_video',
    'cierre',
    # legacy
    'resumen_final',
})


@dataclass
class BloqueInteractivo:
    orden: int
    tipo: str
    titulo: str
    guion: str
    escena_visual: str = ''
    duracion_seg: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'orden': self.orden,
            'tipo': self.tipo,
            'titulo': self.titulo,
            'guion': self.guion,
            'escena_visual': self.escena_visual,
            'duracion_seg': self.duracion_seg,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BloqueInteractivo:
        tipo = str(data.get('tipo', 'texto')).strip().lower()
        if tipo == 'resumen_final':
            tipo = 'cierre'
        if tipo not in _TIPOS_BLOQUE:
            tipo = 'texto'
        return cls(
            orden=int(data.get('orden', 1)),
            tipo=tipo,
            titulo=str(data.get('titulo', '')).strip(),
            guion=str(data.get('guion', '')).strip(),
            escena_visual=str(data.get('escena_visual', '')).strip(),
            duracion_seg=float(data.get('duracion_seg') or 10),
        )


@dataclass
class SecuenciaInteractiva:
    titulo_leccion: str
    objetivo: str
    bloques: list[BloqueInteractivo]
    modelo_ia: str = DEFAULT_MODEL
    rag_usado: bool = False
    formato: str = 'platzi'

    def to_dict(self) -> dict[str, Any]:
        return {
            'titulo_leccion': self.titulo_leccion,
            'objetivo': self.objetivo,
            'modelo_ia': self.modelo_ia,
            'rag_usado': self.rag_usado,
            'formato': self.formato,
            'bloques': [b.to_dict() for b in self.bloques],
        }

    @classmethod
    def from_dict(cls, data: dict) -> SecuenciaInteractiva:
        bloques = [BloqueInteractivo.from_dict(b) for b in data.get('bloques') or []]
        bloques.sort(key=lambda x: x.orden)
        return cls(
            titulo_leccion=str(data.get('titulo_leccion', '')).strip(),
            objetivo=str(data.get('objetivo', '')).strip(),
            bloques=bloques,
            modelo_ia=str(data.get('modelo_ia', DEFAULT_MODEL)),
            rag_usado=bool(data.get('rag_usado')),
            formato=str(data.get('formato', 'platzi')),
        )


def _limpiar_json(raw: str) -> str:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _system_prompt(*, max_bloques: int, max_micro_videos: int) -> str:
    return f"""Eres director pedagógico eki. Diseña una CLASE interactiva estilo Platzi
(referencia: lección con Resumen, secciones en forma de pregunta, definiciones en cita,
listas y micro-videos cortos intercalados — NO un video largo único).

Destino: WhatsApp (Colombia rural). Cada bloque = un mensaje o un clip corto.

Tipos de bloque (campo "tipo"):
- "resumen": párrafo ejecutivo (qué aprenderá y por qué importa). titulo vacío o corto.
- "seccion": encabezado = PREGUNTA (ej. "¿Qué es la rentabilidad?"). guion = 1 frase puente opcional.
- "texto": narración breve (2-3 oraciones máx).
- "definicion": cita clave del material. titulo = etiqueta corta; guion = definición en 1-2 frases.
- "lista": viñetas o numeración en guion (usa "• " o "1. "). titulo = encabezado lista.
- "micro_video": clip 8-12s DESPUÉS de explicar el concepto. guion = narración voz; escena_visual concreta.
- "cierre": reflexión + invita a escribir *listo*.

Ritmo Platzi OBLIGATORIO (repetir por concepto):
  resumen → seccion → texto → definicion → micro_video → (siguiente seccion…)

Reglas:
1. Empieza con "resumen".
2. Usa exactamente {max_micro_videos} bloques "micro_video" distribuidos en TODA la lección
   (uno por concepto/sección importante, no amontonados al inicio).
3. Tras cada "definicion" importante incluye "micro_video" (si quedan cupos).
4. Si el material tiene N errores/puntos (ej. 6 errores): bloque "lista" o seccion+texto por grupo
   y al menos 1 micro_video cada 1-2 errores.
5. Máximo {max_bloques} bloques totales.
6. Solo información del brief/RAG; no inventes cifras.
7. Finanzas/gestión → escena_visual: oficina rural, cuadernos, socios. NO cosecha salvo tema agro.
8. guion texto/lista/resumen: máx 800 caracteres. micro_video guion: máx 120 palabras narración.
9. Cierra con "cierre".

Responde JSON:
{{"titulo_leccion","objetivo","formato":"platzi","bloques":[{{"orden","tipo","titulo","guion","escena_visual","duracion_seg"}}]}}
"""


def _truncar_guion(bloque: BloqueInteractivo) -> None:
    if bloque.tipo == 'micro_video':
        bloque.duracion_seg = max(6.0, min(15.0, float(bloque.duracion_seg or 10)))
        return
    limite = 800 if bloque.tipo in ('lista', 'resumen', 'texto', 'definicion', 'seccion') else 400
    if len(bloque.guion) > limite:
        bloque.guion = bloque.guion[: limite - 1].rstrip() + '…'


def generar_secuencia_interactiva(
    brief: str,
    rag_context: str = '',
    *,
    modelo: str = DEFAULT_MODEL,
    max_bloques: int = 18,
    max_micro_videos: int = 6,
    openai_client=None,
) -> Optional[SecuenciaInteractiva]:
    """Planifica secuencia estilo Platzi desde brief largo + RAG."""
    brief = (brief or '').strip()
    if not brief:
        return None

    max_bloques = max(5, min(24, int(max_bloques)))
    max_micro_videos = max(1, min(8, int(max_micro_videos)))

    user_parts = [f'Brief / material de la lección:\n{brief[:14000]}']
    if rag_context.strip():
        user_parts.append(f'\nContexto RAG (documentos del curso):\n{rag_context[:6000]}')
    user_parts.append(
        f'\nGenera la clase formato Platzi (máx {max_bloques} bloques, '
        f'exactamente hasta {max_micro_videos} micro_video repartidos en la lección).'
    )

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {
                    'role': 'system',
                    'content': _system_prompt(max_bloques=max_bloques, max_micro_videos=max_micro_videos),
                },
                {'role': 'user', 'content': '\n'.join(user_parts)},
            ],
            temperature=0.4,
            max_tokens=4000,
            response_format={'type': 'json_object'},
        )
        data = json.loads(_limpiar_json(resp.choices[0].message.content or '{}'))
    except Exception as exc:
        logger.exception('generar_secuencia_interactiva: %s', exc)
        return None

    bloques: list[BloqueInteractivo] = []
    micro_count = 0
    for raw in data.get('bloques') or []:
        b = BloqueInteractivo.from_dict(raw)
        if b.tipo == 'micro_video':
            if micro_count >= max_micro_videos:
                continue
            micro_count += 1
        _truncar_guion(b)
        bloques.append(b)

    bloques.sort(key=lambda x: x.orden)
    if not bloques:
        return None

    return SecuenciaInteractiva(
        titulo_leccion=str(data.get('titulo_leccion') or brief[:80]).strip(),
        objetivo=str(data.get('objetivo', '')).strip(),
        bloques=bloques[:max_bloques],
        modelo_ia=modelo,
        rag_usado=bool(rag_context.strip()),
        formato=str(data.get('formato', 'platzi')),
    )
