"""Contexto y Respuesta de un estado del motor de curso.

El cuerpo del webhook arma el Contexto con lo que ya leyó y llama al handler
del estado. El handler devuelve una Respuesta: o corta el turno (el cuerpo
sale sin el envío común) o deja el texto que el envío común manda.
Solo importa los lectores hoja de `core.conversacion` (marcas, multimsg).
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
    """Lo nuevo arma `partes`; `texto` queda como formato legado para el envío común del cuerpo."""

    texto: str | None = None
    cortar: bool = False
    partes: tuple = ()

    def __post_init__(self):
        if self.partes and self.texto is None:
            from core.conversacion.marcas import componer

            object.__setattr__(self, 'texto', componer(self.partes))

    @classmethod
    def de_partes(cls, *partes, cortar: bool = False) -> 'Respuesta':
        return cls(partes=tuple(partes), cortar=cortar)

    def como_partes(self) -> list:
        if self.partes:
            return list(self.partes)
        from core.conversacion.marcas import TEXTO, Parte, es_marcado, partes

        texto = (self.texto or '').strip()
        if es_marcado(texto):
            return partes(texto)
        return [Parte(TEXTO, texto=texto)] if texto else []


CORTAR = Respuesta(cortar=True)
