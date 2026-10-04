"""Tope diario de IA. El día cambia a medianoche en Bogotá.

Si Redis no responde, la llamada sigue: un corte de Redis no apaga el curso ni a Nat.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings

logger = logging.getLogger(__name__)

_BOGOTA = ZoneInfo('America/Bogota')
_TTL_SEG = 48 * 3600


def dia_bogota(cuando: datetime | None = None) -> str:
    momento = cuando or datetime.now(_BOGOTA)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=_BOGOTA)
    return momento.astimezone(_BOGOTA).strftime('%Y%m%d')


def _clave(dia: str, cliente_id=None) -> str:
    if cliente_id:
        return f'eki:llm:gasto:{cliente_id}:{dia}'
    return f'eki:llm:gasto:{dia}'


def _cliente():
    from redis import Redis

    url = getattr(settings, 'CELERY_BROKER_URL', None) or 'redis://localhost:6379/0'
    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


def _tope(cliente_id=None) -> Decimal:
    nombre = 'LLM_PRESUPUESTO_DIARIO_ORG_USD' if cliente_id else 'LLM_PRESUPUESTO_DIARIO_USD'
    return Decimal(str(getattr(settings, nombre, 10)))


def leer_gasto(cliente_id=None, cuando: datetime | None = None) -> Decimal | None:
    try:
        bruto = _cliente().get(_clave(dia_bogota(cuando), cliente_id))
    except Exception:
        logger.exception('llm_redis_caido')
        return None
    if bruto is None:
        return Decimal('0')
    if isinstance(bruto, bytes):
        bruto = bruto.decode('utf-8')
    return Decimal(str(bruto))


def nivel(cliente_id=None) -> str:
    """ok, economico, alerta, agotado o redis_caido."""
    global_gasto = leer_gasto(None)
    if global_gasto is None:
        return 'redis_caido'
    org_gasto = Decimal('0')
    if cliente_id:
        org_gasto = leer_gasto(cliente_id)
        if org_gasto is None:
            return 'redis_caido'
    tope_g = _tope(None)
    tope_o = _tope(cliente_id) if cliente_id else tope_g
    if tope_g <= 0 or (cliente_id and tope_o <= 0):
        logger.error('llm_presupuesto_agotado')
        return 'agotado'
    ratio = max(global_gasto / tope_g, (org_gasto / tope_o) if cliente_id else Decimal('0'))
    if ratio >= 1:
        logger.error('llm_presupuesto_agotado')
        return 'agotado'
    if ratio >= Decimal(str(getattr(settings, 'LLM_UMBRAL_ALERTA', 0.8))):
        logger.warning('llm_presupuesto_80')
        return 'alerta'
    if ratio >= Decimal(str(getattr(settings, 'LLM_UMBRAL_ECONOMICO', 0.7))):
        return 'economico'
    return 'ok'


def debe_degradar(cliente_id=None) -> bool:
    return nivel(cliente_id) == 'agotado'


def modelo_segun_presupuesto(modelo: str, cliente_id=None) -> str:
    if nivel(cliente_id) not in ('economico', 'alerta'):
        return modelo
    premium = getattr(settings, 'BOT_COMERCIAL_MODEL_TECNICO', None) or 'gpt-5'
    mini = getattr(settings, 'BOT_COMERCIAL_OPENAI_MODEL', None) or 'gpt-5-mini'
    if modelo in (premium, 'gpt-5'):
        return mini
    return modelo


def anotar_gasto(usd, cliente_id=None) -> None:
    try:
        monto = float(usd or 0)
        if monto <= 0:
            return
        cliente = _cliente()
        dia = dia_bogota()
        claves = [_clave(dia, None)]
        if cliente_id:
            claves.append(_clave(dia, cliente_id))
        for clave in claves:
            cliente.incrbyfloat(clave, monto)
            cliente.expire(clave, _TTL_SEG)
    except Exception:
        logger.exception('llm_redis_caido')
