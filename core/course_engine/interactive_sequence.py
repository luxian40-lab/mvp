"""Secuencia interactiva WA — bloques texto + micro_video desde RAG + brief."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'gpt-4o-mini'

_TIPOS_BLOQUE = frozenset({'texto', 'micro_video', 'resumen'})


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

    def to_dict(self) -> dict[str, Any]:
        return {
            'titulo_leccion': self.titulo_leccion,
            'objetivo': self.objetivo,
            'modelo_ia': self.modelo_ia,
            'rag_usado': self.rag_usado,
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
        )


def _limpiar_json(raw: str) -> str:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _system_prompt(*, max_bloques: int, max_micro_videos: int) -> str:
    return f"""Eres director de microlearning interactivo eki para WhatsApp (Colombia rural).

Convierte la lección (brief + contexto RAG) en una SECUENCIA de bloques — NO un video único plano.

Tipos de bloque (campo "tipo"):
- "texto": mensaje WhatsApp (guion = texto que lee el estudiante; máx 320 caracteres).
- "micro_video": clip corto 8-12s (guion = narración voz; escena_visual = foto documental concreta).
- "resumen": cierre breve en texto + invita a escribir *listo*.

Reglas:
1. Empieza con "texto" gancho (pregunta o dato del material).
2. Alterna texto ↔ micro_video en conceptos clave (ritmo interactivo, no monólogo).
3. Si el material lista errores/puntos numerados (ej. 6 errores), dedica al menos un bloque
   "texto" por error y opcionalmente "micro_video" en los más importantes.
4. Máximo {max_micro_videos} bloques "micro_video" en total.
5. Máximo {max_bloques} bloques en total.
6. Usa SOLO información del brief y RAG; no inventes cifras.
7. Finanzas/rentabilidad/gestión → escena_visual con oficina rural, cuadernos, socios, calculadora.
   NO cosecha/campo salvo que el tema sea explícitamente agrícola.
8. escena_visual solo en micro_video; vacío en texto/resumen.

Responde JSON:
{{"titulo_leccion","objetivo","bloques":[{{"orden","tipo","titulo","guion","escena_visual","duracion_seg"}}]}}
"""


def generar_secuencia_interactiva(
    brief: str,
    rag_context: str = '',
    *,
    modelo: str = DEFAULT_MODEL,
    max_bloques: int = 12,
    max_micro_videos: int = 6,
    openai_client=None,
) -> Optional[SecuenciaInteractiva]:
    """Planifica secuencia desde brief largo + RAG (sin APIs de imagen/video)."""
    brief = (brief or '').strip()
    if not brief:
        return None

    max_bloques = max(3, min(20, int(max_bloques)))
    max_micro_videos = max(1, min(8, int(max_micro_videos)))

    user_parts = [f'Brief / material de la lección:\n{brief[:14000]}']
    if rag_context.strip():
        user_parts.append(f'\nContexto RAG (documentos del curso):\n{rag_context[:6000]}')
    user_parts.append(
        f'\nGenera la secuencia interactiva (máx {max_bloques} bloques, '
        f'máx {max_micro_videos} micro_video).'
    )

    try:
        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        resp = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {'role': 'system', 'content': _system_prompt(max_bloques=max_bloques, max_micro_videos=max_micro_videos)},
                {'role': 'user', 'content': '\n'.join(user_parts)},
            ],
            temperature=0.45,
            max_tokens=2500,
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
            b.duracion_seg = max(6.0, min(15.0, float(b.duracion_seg or 10)))
        elif b.tipo == 'texto':
            if len(b.guion) > 320:
                b.guion = b.guion[:317].rstrip() + '…'
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
    )
