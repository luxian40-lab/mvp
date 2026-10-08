"""Fuentes del Experto en café. Orden fijo: Agrosavia, web Colombia, FAO.

La FAO solo entra si las dos primeras no devolvieron texto. Cada bloque
pide citar la institución. No inventa manejo.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PREFIJO = 'café Colombia'


def consulta_cafe(pregunta: str) -> str:
    q = (pregunta or '').strip()
    if not q:
        return _PREFIJO
    low = q.lower()
    if 'café' in low or 'cafe' in low:
        return q
    return f'{_PREFIJO} {q}'


def enriquecer_contexto_cafe(
    consulta: str,
    contexto: str = '',
) -> tuple[str, dict[str, Any]]:
    """Concatena la primera fuente que responda. Meta.fuente: agrosavia|web|fao|''."""
    meta: dict[str, Any] = {'fuente': '', 'agrosavia_usada': False, 'web_usada': False, 'fao_usada': False}
    base = (contexto or '').strip()
    q = consulta_cafe(consulta)

    try:
        from core.agrosavia_connector import enriquecer_contexto_con_agrosavia

        ctx, agro = enriquecer_contexto_con_agrosavia(q, base)
    except Exception:
        logger.exception('cafe_agrosavia_fail')
        ctx, agro = base, {}
    if agro.get('agrosavia_usada') and (ctx or '').strip():
        meta['fuente'] = 'agrosavia'
        meta['agrosavia_usada'] = True
        return ctx, meta

    web = ''
    try:
        from core.nati import buscar_en_web_colombia

        web = (buscar_en_web_colombia(q, ambito='cafe') or '').strip()
    except Exception:
        logger.exception('cafe_web_fail')
    if web:
        bloque = (
            'FUENTES WEB CAFÉ COLOMBIA (cite Cenicafé, la Federación Nacional de '
            'Cafeteros o el ICA; no use caña ni Cenicana):\n'
            f'{web}'
        )
        meta['fuente'] = 'web'
        meta['web_usada'] = True
        return (f'{base}\n\n{bloque}'.strip() if base else bloque), meta

    try:
        from core.fao_connector import buscar_fao, formatear_contexto_fao

        fao = formatear_contexto_fao(buscar_fao(q))
    except Exception:
        logger.exception('cafe_fao_fail')
        fao = ''
    if fao:
        meta['fuente'] = 'fao'
        meta['fao_usada'] = True
        return (f'{base}\n\n{fao}'.strip() if base else fao), meta

    return base, meta
