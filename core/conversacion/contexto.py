"""Contexto y Respuesta de un estado del motor de curso.

El cuerpo del webhook arma el Contexto con lo que ya leyó y llama al handler
del estado. El handler devuelve una Respuesta: o corta el turno (el cuerpo
sale sin el envío común) o deja el texto que el envío común manda.
Este módulo no importa nada de `core`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Contexto:
    estudiante: Any
    msg_body: str
    msg_from: str
    telefono_limpio: str
    estado_chat: str = ''
    msg_sid: str = ''
    evidencia_imagen_url: str | None = None
    evidencia_imagen_type: str | None = None
    texto_respuesta: str | None = None
    locales: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Respuesta:
    texto: str | None = None
    cortar: bool = False


CORTAR = Respuesta(cortar=True)
