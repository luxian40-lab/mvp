"""Contador Redis de ventana fija. Si Redis no responde, falla cerrado."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def hit(clave: str, limite: int, ventana_seg: int) -> tuple[bool, int]:
    """INCR con TTL en la primera vez. Devuelve (permitido, intentos).

    Redis caído: (False, -1) y un log. No abre la puerta.
    """
    try:
        from core.locks import _cliente_redis

        cliente = _cliente_redis()
        n = int(cliente.incr(clave))
        if n == 1 or int(cliente.ttl(clave)) < 0:
            cliente.expire(clave, int(ventana_seg))
        return n <= int(limite), n
    except Exception:
        logger.exception('rate_limit_redis_caido')
        return False, -1
