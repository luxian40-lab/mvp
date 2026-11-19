"""W2: profundidad y edad del mensaje más viejo en colas Celery/Redis.

Celery con Redis hace LPUSH + BRPOP: el más viejo está en el índice -1.
Si el sobre no trae marca de tiempo, edad_seg queda null (sigue reportando LLEN).
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from django.conf import settings
from django.utils import timezone

COLAS_W2 = ('conversacion', 'masivo', 'media_encode')


def _cliente_redis():
    from redis import Redis

    url = (getattr(settings, 'CELERY_BROKER_URL', None) or '').strip()
    if not url:
        raise ConnectionError('redis_sin_broker')
    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


def _epoch_de_sobre(bruto) -> float | None:
    if bruto is None:
        return None
    if isinstance(bruto, bytes):
        bruto = bruto.decode('utf-8', 'ignore')
    if not isinstance(bruto, str) or not bruto.strip():
        return None
    try:
        data = json.loads(bruto)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    headers = data.get('headers') if isinstance(data.get('headers'), dict) else {}
    props = data.get('properties') if isinstance(data.get('properties'), dict) else {}
    for candidato in (
        headers.get('sent_at'),
        headers.get('timestamp'),
        props.get('timestamp'),
        data.get('timestamp'),
    ):
        epoch = _a_epoch(candidato)
        if epoch is not None:
            return epoch
    eta = headers.get('eta')
    if eta:
        epoch = _a_epoch(eta)
        if epoch is not None:
            return epoch
    return None


def _a_epoch(valor) -> float | None:
    if valor is None or valor == '':
        return None
    if isinstance(valor, (int, float)):
        n = float(valor)
        if n > 1e12:
            n = n / 1000.0
        return n if n > 0 else None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        n = float(texto)
        if n > 1e12:
            n = n / 1000.0
        return n if n > 0 else None
    except ValueError:
        pass
    try:
        if texto.endswith('Z'):
            texto = texto[:-1] + '+00:00'
        dt = datetime.fromisoformat(texto)
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt.timestamp()
    except Exception:
        return None


def edad_segundos_desde_epoch(epoch: float | None, ahora: float | None = None) -> int | None:
    if epoch is None:
        return None
    base = ahora if ahora is not None else time.time()
    return max(0, int(base - epoch))


def snapshot_colas_w2(*, cliente=None) -> dict[str, Any]:
    """Lee LLEN y edad del más viejo en conversacion, masivo, media_encode."""
    detalle: dict[str, Any] = {
        nombre: {'profundidad': None, 'edad_seg': None, 'fuente': None}
        for nombre in COLAS_W2
    }
    propio = cliente is None
    r = None
    try:
        r = cliente or _cliente_redis()
        ahora = time.time()
        for nombre in COLAS_W2:
            n = int(r.llen(nombre) or 0)
            fila = detalle[nombre]
            fila['profundidad'] = n
            if n <= 0:
                fila['edad_seg'] = 0
                fila['fuente'] = 'vacia'
                continue
            bruto = r.lindex(nombre, -1)
            epoch = _epoch_de_sobre(bruto)
            edad = edad_segundos_desde_epoch(epoch, ahora)
            fila['edad_seg'] = edad
            fila['fuente'] = 'sobre' if edad is not None else 'sin_timestamp'
    except Exception as exc:
        return {
            'ok': False,
            'error': str(exc)[:200],
            'colas': detalle,
            'mas_viejo_seg': None,
            'tomado_en': timezone.now().isoformat(),
        }
    finally:
        if propio and r is not None:
            try:
                r.close()
            except Exception:
                pass

    edades = [
        int(v['edad_seg'])
        for v in detalle.values()
        if v.get('profundidad') and v.get('edad_seg') is not None
    ]
    return {
        'ok': True,
        'error': None,
        'colas': detalle,
        'mas_viejo_seg': max(edades) if edades else 0,
        'tomado_en': timezone.now().isoformat(),
    }
