"""Turno: contexto de un mensaje entrante. Se arma una vez en el wrapper.

Vive en un ContextVar mientras dura el turno; cada hilo o tarea ve el suyo.
Solo lleva lo que se sabe sin ir a la base. Este módulo no importa nada del
ciclo de `core`: el wrapper lo construye y lo activa.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from core.lineas.perfil import PerfilLinea


@dataclass(frozen=True)
class Turno:
    telefono: str
    phone_id: str
    linea: str
    perfil: PerfilLinea
    canal: str


_turno: ContextVar[Turno | None] = ContextVar('eki_turno', default=None)


@contextmanager
def turno_activo(turno: Turno | None):
    token = _turno.set(turno)
    try:
        yield turno
    finally:
        _turno.reset(token)


def turno_actual() -> Turno | None:
    return _turno.get()
