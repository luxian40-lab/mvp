"""Marca si esta ejecución ya entregó un mensaje al usuario.

Sirve para no reintentar un SoftTimeLimitExceeded después de un envío:
el reintento duplicaría el WhatsApp.
"""
from __future__ import annotations

import contextvars

_salio: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'eki_mensaje_usuario_salio',
    default=False,
)


def reset_mensaje_salio() -> None:
    _salio.set(False)


def marcar_mensaje_salio() -> None:
    _salio.set(True)


def mensaje_ya_salio() -> bool:
    return bool(_salio.get())
