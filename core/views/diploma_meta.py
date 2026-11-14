"""Fachada del diploma por Meta.

La entrega vive en `core.lineas.diploma_entrega` (Sender, plantilla, flag).
Este módulo conserva los nombres que ya usan utils, admin y tests.
"""
from __future__ import annotations

from core.lineas.diploma_entrega import (  # noqa: F401
    es_entrega_diploma,
    enviar_diploma_plantilla_meta,
    nombre_plantilla_diploma,
)
from core.lineas.diploma_entrega import entregar_si_corresponde


def entregar_si_es_diploma(
    telefono: str,
    texto: str,
    media_url: str | None = None,
    *,
    agente_evento: str = '',
) -> dict | None:
    """None si no es diploma. Si lo es, sale por la entrega unificada."""
    return entregar_si_corresponde(
        telefono,
        texto,
        media_url,
        agente=agente_evento or 'diploma_meta',
    )
