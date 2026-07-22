"""
Runtime Nat / bot comercial.

El enrutado vive en ``core.bot_comercial_routing``.
El orquestador WhatsApp sigue re-exportado desde ``core.views`` mientras se completa
la extracción del monolito; este paquete es el hogar canónico de lógica Nat.
"""

from core.bot_comercial_routing import (
    es_destino_bot_comercial,
    es_numero_comercial_conocido,
    numeros_destino_comercial,
)

__all__ = [
    'es_destino_bot_comercial',
    'es_numero_comercial_conocido',
    'numeros_destino_comercial',
]
