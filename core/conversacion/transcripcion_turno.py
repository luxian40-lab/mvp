"""Una nota de voz de Meta se transcribe una vez por turno.

El menú, la ruta, Nat y el curso del mismo turno leen el mismo texto.
Fuera de un turno no se guarda nada. Si la transcripción falla con excepción,
no se guarda y el siguiente que la pida lo intenta otra vez.

Este módulo no importa nada de core.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable

_transcritos: ContextVar[dict[str, str | None] | None] = ContextVar('eki_transcritos', default=None)


@contextmanager
def un_turno():
    token = _transcritos.set({})
    try:
        yield
    finally:
        _transcritos.reset(token)


def del_turno(media_id: str, transcribir: Callable[[], str | None]) -> str | None:
    """Lo que devolvió la primera transcripción de este audio en el turno."""
    guardados = _transcritos.get()
    if guardados is None or not media_id:
        return transcribir()
    if media_id not in guardados:
        guardados[media_id] = transcribir()
    return guardados[media_id]
