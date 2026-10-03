"""Candado Redis por teléfono para los webhooks de WhatsApp.

El orden estricto entre mensajes del mismo teléfono no está garantizado:
si uno agota la espera y reintenta, otro que llegó después puede tomar el
candado primero. El candado evita que se procesen a la vez, no que salgan
en el orden de llegada.
"""
from __future__ import annotations

import hashlib
import hmac
from contextlib import contextmanager

from django.conf import settings

LOCK_TIMEOUT = 90
LOCK_BLOCKING = 10


def telefono_hash(telefono_normalizado: str) -> str:
    """HMAC-SHA256(SECRET_KEY, teléfono) en 16 hex. No es reversible por fuerza bruta."""
    secreto = str(getattr(settings, 'SECRET_KEY', '') or '').encode('utf-8')
    base = (telefono_normalizado or '').encode('utf-8')
    return hmac.new(secreto, base, hashlib.sha256).hexdigest()[:16]


def _cliente_redis():
    from redis import Redis

    url = (
        getattr(settings, 'CELERY_BROKER_URL', None)
        or 'redis://localhost:6379/0'
    )
    return Redis.from_url(url)


@contextmanager
def telefono_lock(
    telefono_normalizado,
    timeout=None,
    blocking_timeout=None,
):
    """Candado por teléfono normalizado, no por Estudiante.

    timeout debe superar el time_limit de la tarea (60 s). Si no se obtiene
    en blocking_timeout, redis levanta LockError y la tarea reintenta.
    """
    from redis.exceptions import LockError

    espera_bloqueo = LOCK_BLOCKING if blocking_timeout is None else blocking_timeout
    vigencia = LOCK_TIMEOUT if timeout is None else timeout
    clave = f"eki:wa:tel:{(telefono_normalizado or 'sin-telefono')}"
    cliente = _cliente_redis()
    candado = cliente.lock(
        clave,
        timeout=vigencia,
        blocking_timeout=espera_bloqueo,
    )
    adquirido = candado.acquire(blocking=True, blocking_timeout=espera_bloqueo)
    if not adquirido:
        raise LockError(f'telefono_lock no obtenido: {telefono_hash(str(telefono_normalizado or ""))}')
    try:
        yield
    finally:
        try:
            candado.release()
        except LockError:
            pass
        try:
            cliente.close()
        except Exception:
            pass
