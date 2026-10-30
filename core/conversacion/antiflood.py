"""Tope de mensajes por minuto. Los statuses no pasan por aquí.

Un duplicado ya reclamado no llega a la tarea, así que no suma.
Si Redis no responde, el mensaje sigue.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings

logger = logging.getLogger(__name__)

AVISO_FLOOD = 'Estás escribiendo muy rápido; espera un momento…'
_BOGOTA = ZoneInfo('America/Bogota')


def _cliente():
    from redis import Redis

    url = getattr(settings, 'CELERY_BROKER_URL', None) or 'redis://localhost:6379/0'
    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


def _minuto() -> str:
    return datetime.now(_BOGOTA).strftime('%Y%m%d%H%M')


def flood_excedido(telefono: str) -> tuple[bool, bool]:
    """(descartar, enviar un solo aviso)."""
    if not telefono or telefono == 'sin-telefono':
        return False, False
    try:
        from core.locks import telefono_hash

        cliente = _cliente()
        minuto = _minuto()
        clave = f'eki:flood:{telefono_hash(telefono)}:{minuto}'
        n = int(cliente.incr(clave))
        if n == 1:
            cliente.expire(clave, 70)
        tope = int(getattr(settings, 'LINEA_MAX_MSG_MIN', 12) or 12)
        if n <= tope:
            return False, False
        logger.warning('flood_descartado n=%s', n)
        aviso = f'eki:flood:aviso:{telefono_hash(telefono)}:{minuto}'
        unico = bool(cliente.set(aviso, '1', nx=True, ex=60))
        return True, unico
    except Exception:
        logger.exception('flood_redis_caido')
        return False, False
