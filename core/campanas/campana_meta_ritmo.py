"""Velocidad y pausa de campañas Meta. Si Redis no responde, el envío sigue."""
from __future__ import annotations

import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# Topes y fecha de verificación: WA_META_MPS en settings.
LUA_BUCKET = """
local d = redis.call('HMGET', KEYS[1], 't', 'ms')
local t = tonumber(d[1]) or tonumber(ARGV[2])
local ms = tonumber(d[2]) or tonumber(ARGV[3])
t = math.min(tonumber(ARGV[2]), t + (tonumber(ARGV[3]) - ms) / 1000 * tonumber(ARGV[1]))
local ok = 0
local espera = 0
if t >= tonumber(ARGV[4]) then
  t = t - tonumber(ARGV[4])
  ok = 1
else
  espera = (tonumber(ARGV[4]) - t) / tonumber(ARGV[1])
end
redis.call('HSET', KEYS[1], 't', t, 'ms', ARGV[3])
redis.call('EXPIRE', KEYS[1], 60)
return {ok, tostring(espera)}
"""


def paso_bucket(tokens: float, ultimo_ms: float, ahora_ms: float, rate: float, capacity: float, pedir: float = 1):
    tokens = min(capacity, tokens + (ahora_ms - ultimo_ms) / 1000 * rate)
    if tokens >= pedir:
        return True, 0.0, tokens - pedir, ahora_ms
    espera = (pedir - tokens) / rate if rate else 30
    return False, espera, tokens, ahora_ms


def _redis():
    from redis import Redis

    url = getattr(settings, 'CELERY_BROKER_URL', None) or 'redis://localhost:6379/0'
    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


def _bucket_de_linea(phone_id: str = '') -> tuple[str, float, float]:
    rate = float(getattr(settings, 'WA_META_MPS', 20) or 20)
    capacity = float(getattr(settings, 'WA_META_BURST', 20) or 20)
    phone_id = (phone_id or '').strip()
    if not phone_id or not getattr(settings, 'WA_META_BUCKET_POR_LINEA', False):
        return 'eki:wa:bucket:meta', rate, capacity
    propio = (getattr(settings, 'WA_META_MPS_POR_LINEA', None) or {}).get(phone_id)
    if propio:
        rate = float(propio)
    return f'eki:wa:bucket:meta:{phone_id}', rate, min(capacity, rate)


def pedir_token(phone_id: str = '') -> tuple[bool, float]:
    clave, rate, capacity = _bucket_de_linea(phone_id)
    try:
        ahora = int(time.time() * 1000)
        crudo = _redis().eval(LUA_BUCKET, 1, clave, rate, capacity, ahora, 1)
        ok = int(crudo[0]) == 1
        espera = float(crudo[1] or 0)
        return ok, espera
    except Exception:
        logger.exception('campana_bucket_redis')
        return True, 0.0


def hueco_destino(telefono_hash: str) -> bool:
    """True si este número puede recibir ahora."""
    try:
        gap = int(getattr(settings, 'WA_DESTINO_GAP_SEG', 6) or 6)
        return bool(_redis().set(f'eki:wa:gap:{telefono_hash}', '1', nx=True, px=gap * 1000))
    except Exception:
        logger.exception('campana_hueco_redis')
        return True


def bajo_tope_contactos(telefono_hash: str) -> bool:
    """False si ya vamos al 90 % del tope de contactos nuevos en 24 h."""
    try:
        tope = int(getattr(settings, 'META_LIMITE_CONTACTOS_24H', 1000) or 1000)
        ahora = time.time()
        cliente = _redis()
        clave = 'eki:wa:contactos24h'
        cliente.zremrangebyscore(clave, 0, ahora - 86400)
        if cliente.zscore(clave, telefono_hash) is not None:
            return True
        if int(cliente.zcard(clave) or 0) >= int(tope * 0.9):
            logger.warning('campana_contactos_24h_90')
            return False
        cliente.zadd(clave, {telefono_hash: ahora})
        cliente.expire(clave, 90000)
        return True
    except Exception:
        logger.exception('campana_contactos_redis')
        return True


def anotar_resultado(campana, *, fallo: bool, nuevo: bool) -> bool:
    """True si la tasa de fallo pausó la campaña."""
    try:
        cliente = _redis()
        nclave = f'eki:campana:{campana.pk}:n'
        fclave = f'eki:campana:{campana.pk}:fallos'
        n = int(cliente.incr(nclave)) if nuevo else int(cliente.get(nclave) or 0)
        cliente.expire(nclave, 48 * 3600)
        fallos = int(cliente.incr(fclave)) if fallo else int(cliente.get(fclave) or 0)
        if fallo:
            cliente.expire(fclave, 48 * 3600)
        tasa = float(getattr(settings, 'CAMPANA_PAUSA_TASA_FALLO', 0.15) or 0.15)
        if n >= 100 and n and (fallos / n) > tasa:
            if not campana.pausada:
                campana.pausada = True
                campana.pausa_motivo = 'tasa_fallos'
                campana.save(update_fields=['pausada', 'pausa_motivo'])
                logger.error('campana_pausada_por_fallos id=%s', campana.pk)
            return True
    except Exception:
        logger.exception('campana_pausa_redis')
    return False


def reanudar(campana) -> None:
    campana.pausada = False
    campana.pausa_motivo = ''
    campana.save(update_fields=['pausada', 'pausa_motivo'])
    try:
        cliente = _redis()
        cliente.delete(f'eki:campana:{campana.pk}:n', f'eki:campana:{campana.pk}:fallos')
    except Exception:
        logger.exception('campana_reanudar_redis')


def espera_backoff(intento: int) -> int:
    return min(2 ** max(intento, 0), 30)


def resumen_preflight(campana) -> list[str]:
    from core.consentimiento_wa import puede_recibir_plantilla
    from core.meta_token import token_invalido
    from core.meta_waba import _destinatarios, _phone_default

    dest = list(_destinatarios(campana))
    con = sum(1 for est in dest if puede_recibir_plantilla(est))
    mps = _bucket_de_linea(campana.phone_number_id or _phone_default())[1]
    segundos = round(len(dest) / mps, 1) if mps else 0
    return [
        f"token {'invalido' if token_invalido() else 'sin_marca'}",
        f'plantilla {campana.plantilla.estado}',
        f'optin {con} de {len(dest)}',
        f"tope_24h {getattr(settings, 'META_LIMITE_CONTACTOS_24H', 1000)}",
        f'duracion_estimada_s {segundos}',
    ]
