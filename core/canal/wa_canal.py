"""Canal del webhook que está escribiendo WhatsappLog. Vacío = no marcar."""
from contextlib import contextmanager
from contextvars import ContextVar

CANAL_META = 'meta'
CANAL_TWILIO = 'twilio'

_canal: ContextVar[str] = ContextVar('wa_log_canal', default='')


def canal_actual() -> str:
    return (_canal.get() or '').strip()


@contextmanager
def canal_webhook(canal: str):
    token = _canal.set((canal or '').strip())
    try:
        yield
    finally:
        _canal.reset(token)
