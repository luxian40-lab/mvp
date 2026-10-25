"""Un solo punto que cambia `twilio.rest.Client` según el canal del turno.

El código viejo hace `from twilio.rest import Client` dentro de la función que
envía. Cada capa (Meta en el sandbox, botón Continuemos en Twilio) envuelve al
cliente mientras dura el turno.

Con EKI_CLIENTE_CANAL_PERMANENTE=False (default) cada capa cambia el atributo
global y lo restaura al salir, como siempre. Con True se instala una vez un
cliente que lee las capas de un ContextVar: dos hilos con canales distintos no
se pisan.

No importa nada de core: las capas llegan desde quien las abre.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable

from django.conf import settings

Envolver = Callable[[Callable], Callable]

_claves: ContextVar[tuple[str, ...]] = ContextVar('eki_cliente_claves', default=())
_capas: ContextVar[tuple[Envolver, ...]] = ContextVar('eki_cliente_capas', default=())
_lock = threading.Lock()
_original: Callable | None = None


class ClienteCanal:
    """Construye el cliente aplicando las capas activas sobre el Client de twilio."""

    _eki_cliente_canal = True

    def __new__(cls, *args, **kwargs):
        fabrica = _original
        for envolver in _capas.get():
            fabrica = envolver(fabrica)
        return fabrica(*args, **kwargs)


def permanente() -> bool:
    return bool(getattr(settings, 'EKI_CLIENTE_CANAL_PERMANENTE', False))


def instalado() -> bool:
    import twilio.rest as twilio_rest

    return bool(getattr(twilio_rest.Client, '_eki_cliente_canal', False))


def instalar() -> None:
    """Idempotente. Guarda el Client real y deja ClienteCanal en su lugar."""
    global _original
    with _lock:
        if instalado():
            return
        import twilio.rest as twilio_rest

        _original = twilio_rest.Client
        _poner(ClienteCanal)


def _poner(clase) -> None:
    import twilio.rest as twilio_rest

    twilio_rest.Client = clase


@contextmanager
def capa_cliente(clave: str, envolver: Envolver):
    """Mientras dura el bloque, `twilio.rest.Client(...)` pasa por `envolver(base)`.

    La misma clave anidada no se aplica dos veces.
    """
    if clave in _claves.get():
        yield
        return
    token_claves = _claves.set(_claves.get() + (clave,))
    try:
        if permanente():
            instalar()
            token_capas = _capas.set(_capas.get() + (envolver,))
            try:
                yield
            finally:
                _capas.reset(token_capas)
        else:
            import twilio.rest as twilio_rest

            anterior = twilio_rest.Client
            _poner(envolver(anterior))
            try:
                yield
            finally:
                _poner(anterior)
    finally:
        _claves.reset(token_claves)
