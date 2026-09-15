"""From sticky para replies WhatsApp (sandbox menú dual).

Cuando el usuario escribe al sandbox Twilio, las respuestas deben salir
del mismo número aunque el modo sea «cursos» (edu no pasa from_number).
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_reply_from: ContextVar[str | None] = ContextVar('wa_reply_from', default=None)


def get_reply_from_override() -> str | None:
    return _reply_from.get()


@contextmanager
def reply_from(numero: str | None):
    token = _reply_from.set((numero or '').strip() or None)
    try:
        yield
    finally:
        _reply_from.reset(token)
