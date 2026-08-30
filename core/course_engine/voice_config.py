"""Voz y tier Course Engine — curso → modulo (override)."""
from __future__ import annotations

import json
from typing import Any, Optional

from django.conf import settings

TIER_ECONOMICO = 'economico'
TIER_ESTANDAR = 'estandar'
TIER_PREMIUM = 'premium'

TIER_CHOICES = (
    (TIER_ECONOMICO, 'Economico (~20-30 s, sin Runway)'),
    (TIER_ESTANDAR, 'Estandar (~25-35 s, 1 clip Runway)'),
    (TIER_PREMIUM, 'Premium (~35-50 s, hasta 3 clips Runway)'),
)

TIER_DURACION_APROX_SEG = {
    TIER_ECONOMICO: (20, 30),
    TIER_ESTANDAR: (25, 35),
    TIER_PREMIUM: (35, 50),
}

# Catalogo eki — 2 mujer + 2 hombre (override via COURSE_ENGINE_VOICES_JSON en EB)
DEFAULT_VOICES: list[dict[str, str]] = [
    {'id': 'Wb1wmVQjMx9g2QSIOTPI', 'label': 'Maria', 'genero': 'F'},
    {'id': 'Mf0RJxPVoxXD0xzgV88r', 'label': 'Sofia', 'genero': 'F'},
    {'id': 'b2htR0pMe28pYwCY9gnP', 'label': 'Carlos', 'genero': 'M'},
    {'id': 'Ux2YbCNfurnKHnzlBHGX', 'label': 'Andres', 'genero': 'M'},
]


def catalogo_voces() -> list[dict[str, str]]:
    raw = getattr(settings, 'COURSE_ENGINE_VOICES', None)
    if isinstance(raw, list) and raw:
        return raw
    return DEFAULT_VOICES


def choices_voces(
    *,
    incluir_vacio: bool = False,
    incluir_heredar: bool = False,
    vacio_label: str = '— Default entorno (.env) —',
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if incluir_heredar:
        out.append(('', '— Heredar del curso —'))
    if incluir_vacio:
        out.append(('', vacio_label))
    for v in catalogo_voces():
        genero = v.get('genero', '').upper()
        tag = {'F': 'mujer', 'M': 'hombre'}.get(genero, genero.lower() or 'voz')
        out.append((v['id'], f"{v['label']} ({tag})"))
    return out


def label_voz(voice_id: Optional[str]) -> str:
    vid = (voice_id or '').strip()
    if not vid:
        return ''
    for v in catalogo_voces():
        if v['id'] == vid:
            genero = v.get('genero', '').upper()
            tag = {'F': 'mujer', 'M': 'hombre'}.get(genero, '')
            return f"{v['label']} ({tag})" if tag else v['label']
    return vid


def _default_voice_id() -> Optional[str]:
    vid = getattr(settings, 'ELEVENLABS_VOICE_ID', None)
    return str(vid).strip() if vid else None


def resolver_tier_curso(curso) -> str:
    tier = (getattr(curso, 'course_engine_tier', None) or TIER_ECONOMICO).strip().lower()
    if tier not in {TIER_ECONOMICO, TIER_ESTANDAR, TIER_PREMIUM}:
        return TIER_ECONOMICO
    return tier


def resolver_tier_modulo(modulo) -> str:
    override = (getattr(modulo, 'course_engine_tier', None) or '').strip().lower()
    if override in {TIER_ECONOMICO, TIER_ESTANDAR, TIER_PREMIUM}:
        return override
    return resolver_tier_curso(modulo.curso)


def resolver_voice_id_curso(curso) -> Optional[str]:
    vid = (getattr(curso, 'course_engine_voice_id', None) or '').strip()
    return vid or _default_voice_id()


def resolver_voice_id_modulo(modulo) -> Optional[str]:
    vid = (getattr(modulo, 'course_engine_voice_id', None) or '').strip()
    if vid:
        return vid
    return resolver_voice_id_curso(modulo.curso)


def resolver_voice_label_modulo(modulo) -> str:
    vid = resolver_voice_id_modulo(modulo)
    label = (getattr(modulo, 'course_engine_voice_label', None) or '').strip()
    if label:
        return label
    label = (getattr(modulo.curso, 'course_engine_voice_label', None) or '').strip()
    if label:
        return label
    catalog = label_voz(vid)
    return catalog or 'Voz default eki'


def config_modulo(modulo) -> dict:
    tier = resolver_tier_modulo(modulo)
    lo, hi = TIER_DURACION_APROX_SEG.get(tier, (20, 30))
    return {
        'tier': tier,
        'voice_id': resolver_voice_id_modulo(modulo),
        'voice_label': resolver_voice_label_modulo(modulo),
        'duracion_aprox_seg': (lo, hi),
        'modulo_id': modulo.pk,
        'curso_id': modulo.curso_id,
    }
