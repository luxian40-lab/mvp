"""
Extracción y persistencia de contexto agronómico estructurado para Nati (Parte 3).
"""

from __future__ import annotations

import re
from typing import Any

from django.utils import timezone

# Patrones ligeros (NLU rule-based) — extensible con LLM después
_PATRONES = {
    'cultivo': re.compile(
        r'\b(caf[eé]|cacao|platano|plátano|banano|aguacate|papa|tomate|ma[ií]z|arroz|'
        r'caña|papa|mora|fríjol|frijol|hortaliza|pasto|ganado|bovino|porcino|avícola|avicola)\b',
        re.I,
    ),
    'etapa': re.compile(
        r'\b(germinaci[oó]n|siembra|vegeta|floraci[oó]n|fructificaci[oó]n|cosecha|'
        r'beneficio|poscosecha|secado|tensi[oó]n)\b',
        re.I,
    ),
    'problema': re.compile(
        r'\b(roya|broca|mancha|plaga|gusano|trips|ácaro|acaro|chocolate|'
        r'deficiencia|clorosis|sequ[ií]a|humedad|hongos?|mildiu|oidio|'
        r'nutrici[oó]n|fertiliz|abono|nitr[oó]geno|f[oó]sforo|potasio)\b',
        re.I,
    ),
    'clima': re.compile(
        r'\b(lluvia|sequ[ií]a|humedad| helada|calor|viento|clima|temporal|'
        r'invierno|verano|alta humedad|baja humedad)\b',
        re.I,
    ),
    'region': re.compile(
        r'\b(cundinamarca|huila|nariño|narino|antioquia|santander|tolima|'
        r'caquet[aá]|quind[ií]o|risaralda|caldas|boyac[aá]|meta|cordoba|c[oó]rdoba|'
        r'valle|cauca|putumayo|magdalena|choc[oó])\b',
        re.I,
    ),
}


def _normalizar_valor(campo: str, match: re.Match) -> str:
    val = (match.group(1) or match.group(0) or '').strip()
    if campo == 'cultivo' and val.lower() in ('cafe', 'café'):
        return 'café'
    return val[:200] if campo == 'problema' else val[:80]


def extraer_campos_desde_mensaje(mensaje: str) -> dict[str, str]:
    """Detecta dimensiones agronómicas en un mensaje del productor."""
    texto = (mensaje or '').strip()
    if not texto:
        return {}
    found: dict[str, str] = {}
    for campo, patron in _PATRONES.items():
        m = patron.search(texto)
        if m:
            found[campo] = _normalizar_valor(campo, m)
    # Municipio: "en <Nombre>" muy heurístico
    m_mun = re.search(r'\ben\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)\b', texto)
    if m_mun and 'region' not in found:
        found.setdefault('municipio', m_mun.group(1)[:80])
    return found


def obtener_o_crear_contexto(sesion) -> 'ContextoAgroSession':
    from core.models import ContextoAgroSession

    ctx, _ = ContextoAgroSession.objects.get_or_create(sesion=sesion)
    return ctx


def actualizar_contexto_desde_mensaje(sesion, mensaje: str) -> 'ContextoAgroSession':
    """Fusiona extracción del mensaje con contexto previo de la sesión."""
    ctx = obtener_o_crear_contexto(sesion)
    nuevos = extraer_campos_desde_mensaje(mensaje)
    changed = False
    for campo, valor in nuevos.items():
        if valor and not (getattr(ctx, campo, '') or '').strip():
            setattr(ctx, campo, valor)
            changed = True
    if changed:
        meta = dict(ctx.metadata or {})
        meta['ultima_extraccion'] = timezone.now().isoformat()
        ctx.metadata = meta
        ctx.save()
    return ctx


def formatear_bloque_contexto_para_prompt(ctx) -> str:
    """Bloque obligatorio en el prompt de Nati."""
    if not ctx:
        return ''
    d = ctx.to_dict() if hasattr(ctx, 'to_dict') else {}
    lineas = []
    etiquetas = {
        'cultivo': 'Cultivo',
        'etapa': 'Etapa fenológica',
        'region': 'Región',
        'municipio': 'Municipio',
        'clima': 'Clima / condición',
        'problema': 'Problema reportado',
    }
    for k, lbl in etiquetas.items():
        v = (d.get(k) or '').strip()
        if v:
            lineas.append(f'- {lbl}: {v}')
    if not lineas:
        return (
            'CONTEXTO AGRONÓMICO: parcial. Si falta cultivo o síntoma principal, '
            'formule como máximo 2 preguntas concretas antes de recomendar.'
        )
    pct = d.get('completitud_pct', ctx.completitud_pct() if ctx else 0)
    return (
        f'CONTEXTO AGRONÓMICO ESTRUCTURADO (completitud {pct}%):\n'
        + '\n'.join(lineas)
        + '\n\nUsa este contexto explícitamente. No des recomendaciones genéricas fuera de él.'
    )


def campos_faltantes(ctx) -> list[str]:
    if not ctx:
        return ['cultivo', 'problema', 'region']
    faltan = []
    for k in ('cultivo', 'problema', 'region'):
        if not (getattr(ctx, k, '') or '').strip():
            faltan.append(k)
    return faltan
