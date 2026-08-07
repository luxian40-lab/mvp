# -*- coding: utf-8 -*-
"""Reglas de estructura Module Builder WA (sin envío WhatsApp)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:
    from .models import Modulo, PasoModulo


def detectar_secciones_intercaladas(pasos: Iterable[PasoModulo]) -> list[dict]:
    """
    Recorre pasos ya ordenados por ``orden``.
    Si una sección termina y luego reaparece → intercalado (colapso tipo Agrosavia).

    Devuelve lista de hallazgos ``{seccion_id, orden, paso_id}``.
    """
    hallazgos: list[dict] = []
    cerradas: set[int] = set()
    actual: Optional[int] = None
    for p in pasos:
        sid = getattr(p, 'seccion_id', None)
        if not sid:
            continue
        if sid != actual:
            if actual is not None:
                cerradas.add(actual)
            if sid in cerradas:
                hallazgos.append(
                    {
                        'seccion_id': sid,
                        'orden': getattr(p, 'orden', None),
                        'paso_id': getattr(p, 'pk', None),
                    }
                )
            actual = sid
    return hallazgos


def modulo_tiene_secciones_intercaladas(modulo: Modulo) -> list[dict]:
    from .module_steps import pasos_activos_qs

    return detectar_secciones_intercaladas(list(pasos_activos_qs(modulo)))


def mensaje_error_intercalado(hallazgos: list[dict]) -> str:
    if not hallazgos:
        return ''
    partes = [
        f"sección {h['seccion_id']} reaparece en orden={h['orden']} (paso {h['paso_id']})"
        for h in hallazgos[:5]
    ]
    return (
        'Estructura intercalada: los pasos de una sección deben quedar juntos '
        '(sin mezclar con otra en el medio). '
        + '; '.join(partes)
    )
