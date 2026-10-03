"""Candado Redis por teléfono para los webhooks de WhatsApp.

El orden estricto entre mensajes del mismo teléfono no está garantizado:
si uno agota la espera y reintenta, otro que llegó después puede tomar el
candado primero. El candado evita que se procesen a la vez, no que salgan
en el orden de llegada.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from contextlib import contextmanager

from django.conf import settings

logger = logging.getLogger(__name__)

LOCK_TIMEOUT = 90
LOCK_BLOCKING = 10
ENTREGA_TTL_SEG = 3600
ENTREGA_TOPE = 3


def telefono_hash(telefono_normalizado: str) -> str:
    """HMAC-SHA256(SECRET_KEY, teléfono) en 16 hex. No es reversible por fuerza bruta."""
    secreto = str(getattr(settings, 'SECRET_KEY', '') or '').encode('utf-8')
    base = (telefono_normalizado or '').encode('utf-8')
    return hmac.new(secreto, base, hashlib.sha256).hexdigest()[:16]


def clave_entrega(canal: str, external_id: str) -> str:
    return f'eki:wa:entrega:{canal}:{external_id}'


def contar_entrega(canal: str, external_id: str) -> int:
    """Cuenta reentregas del broker por (canal, external_id). TTL de 1 h.

    Sin external_id no hay clave estable: devuelve 1 y no escribe.
    El TTL se pone en la primera entrega y, si faltara, en la siguiente.
    El caller solo llama esto cuando delivery_info['redelivered'] es True.
    """
    ext = (external_id or '').strip()
    if not ext:
        return 1
    clave = clave_entrega(canal, ext)
    cliente = _cliente_redis()
    try:
        n = int(cliente.incr(clave))
        if n == 1 or int(cliente.ttl(clave)) < 0:
            cliente.expire(clave, ENTREGA_TTL_SEG)
        return n
    finally:
        try:
            cliente.close()
        except Exception:
            pass


def borrar_entrega(canal: str, external_id: str) -> None:
    """Quita el contador para que un reproceso staff no herede reentregas viejas."""
    ext = (external_id or '').strip()
    if not ext:
        return
    clave = clave_entrega(canal or '', ext)
    try:
        cliente = _cliente_redis()
        try:
            pool = cliente.connection_pool
            pool.connection_kwargs['socket_connect_timeout'] = 1
            pool.connection_kwargs['socket_timeout'] = 1
            cliente.delete(clave)
        finally:
            try:
                cliente.close()
            except Exception:
                pass
    except Exception:
        logger.exception(
            'webhook_entrega_no_borrada canal=%s external_id=%s',
            canal,
            ext,
        )


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
