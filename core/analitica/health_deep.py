"""Salud interna. No incluye teléfonos, cuerpos ni el token de infra."""
from __future__ import annotations

import hmac
import time

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone

CLAVE_LATIDO = 'eki:beat:latido'
_COLAS = ('conversacion', 'masivo', 'celery', 'media_encode')


def _redis():
    from redis import Redis

    url = getattr(settings, 'CELERY_BROKER_URL', None) or 'redis://localhost:6379/0'
    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


def autorizado(request) -> bool:
    usuario = getattr(request, 'user', None)
    if usuario is not None and usuario.is_authenticated and usuario.is_staff:
        return True
    esperado = (getattr(settings, 'EKI_INFRA_HEALTH_TOKEN', '') or '').strip()
    if not esperado:
        return False
    recibido = (
        request.headers.get('X-Eki-Infra-Token')
        or request.GET.get('token')
        or ''
    )
    recibido = str(recibido)
    if len(recibido) != len(esperado):
        return False
    return hmac.compare_digest(recibido, esperado)


def escribir_latido() -> None:
    _redis().set(CLAVE_LATIDO, str(time.time()), ex=600)


def estado_latido() -> dict:
    try:
        crudo = _redis().get(CLAVE_LATIDO)
    except Exception:
        return {'ok': False, 'edad_seg': None, 'alerta': True}
    if not crudo:
        return {'ok': False, 'edad_seg': None, 'alerta': True}
    if isinstance(crudo, bytes):
        crudo = crudo.decode('utf-8', 'ignore')
    try:
        edad = max(0, int(time.time() - float(crudo)))
    except ValueError:
        return {'ok': False, 'edad_seg': None, 'alerta': True}
    return {'ok': edad <= 180, 'edad_seg': edad, 'alerta': edad > 180}


def _colas() -> dict:
    salida = {nombre: None for nombre in _COLAS}
    mas_viejo = None
    try:
        cliente = _redis()
        for nombre in _COLAS:
            salida[nombre] = int(cliente.llen(nombre) or 0)
            if salida[nombre]:
                mas_viejo = mas_viejo if mas_viejo is not None else 'hay_pendientes'
    except Exception:
        return {'profundidad': salida, 'mas_viejo': None, 'ok': False}
    return {'profundidad': salida, 'mas_viejo': mas_viejo, 'ok': True}


def pct_canal_vacio() -> dict:
    from datetime import timedelta

    from django.db.models import Q

    from core.models import WhatsappLog

    desde = timezone.now() - timedelta(hours=24)
    base = WhatsappLog.objects.filter(tipo='INCOMING', fecha__gte=desde)
    total = base.count()
    vacios = base.filter(Q(canal='') | Q(canal__isnull=True)).count()
    pct = round(100 * vacios / total, 1) if total else 0
    return {'entrantes_24h': total, 'canal_vacio': vacios, 'pct': pct}


def resumen_para_infra() -> dict:
    try:
        from core.meta_token import CLAVE_TOKEN_INVALIDO

        token = {'invalido': bool(_redis().get(CLAVE_TOKEN_INVALIDO))}
    except Exception:
        token = {'invalido': None}
    try:
        canal = pct_canal_vacio()
    except Exception:
        canal = {'entrantes_24h': None, 'canal_vacio': None, 'pct': None}
    return {'latido': estado_latido(), 'canal_vacio_24h': canal, 'token_meta': token}


def chequeo() -> dict:
    db_ok = False
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    redis_ok = False
    try:
        redis_ok = bool(_redis().ping())
    except Exception:
        redis_ok = False
    extra = resumen_para_infra()
    return {
        'db': db_ok,
        'redis': redis_ok,
        'colas': _colas(),
        'latido': extra['latido'],
        'token_meta': extra['token_meta'],
        'canal_vacio_24h': extra['canal_vacio_24h'],
    }


def health_deep(request):
    if not autorizado(request):
        return JsonResponse({'ok': False}, status=403)
    datos = chequeo()
    datos['ok'] = bool(datos['db'] and datos['redis'] and datos['latido']['ok'])
    return JsonResponse(datos)
