"""Fachada del diploma por Meta.

La entrega vive en `core.lineas.diploma_entrega` (Sender, plantilla, flag).
Este módulo conserva los nombres que ya usan utils, admin y tests.
"""
from __future__ import annotations

import importlib

_DIPLOMA_ATTRS = frozenset({
    'es_entrega_diploma',
    'enviar_diploma_plantilla_meta',
    'nombre_plantilla_diploma',
    'entregar_si_corresponde',
})


def __getattr__(name: str):
    if name in _DIPLOMA_ATTRS:
        return getattr(importlib.import_module('core.lineas.diploma_entrega'), name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def entregar_si_es_diploma(
    telefono: str,
    texto: str,
    media_url: str | None = None,
    *,
    agente_evento: str = '',
) -> dict | None:
    """None si no es diploma. Si lo es, sale por la entrega unificada."""
    entregar_si_corresponde = importlib.import_module(
        'core.lineas.diploma_entrega',
    ).entregar_si_corresponde
    return entregar_si_corresponde(
        telefono,
        texto,
        media_url,
        agente=agente_evento or 'diploma_meta',
    )