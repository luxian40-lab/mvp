"""La línea Meta no abre cursos ni llama al modelo a un número sin programa.

Un estudiante de campaña (tiene organización) sigue el habeas y la cédula.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings

logger = logging.getLogger(__name__)

TEXTO_SOLO_REGISTRADOS = (
    'Esta línea es para estudiantes de programas eki. '
    'Si su organización lo inscribió, escriba desde el número que ellos registraron.'
)
_BOGOTA = ZoneInfo('America/Bogota')


def solo_registrados_activo() -> bool:
    return bool(getattr(settings, 'LINEA_META_SOLO_REGISTRADOS', True))


def _cliente_redis():
    from redis import Redis

    url = getattr(settings, 'CELERY_BROKER_URL', None) or 'redis://localhost:6379/0'
    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


def es_registrado(telefono: str) -> bool:
    from core.models import Estudiante, ProgresoEstudiante
    from core.models_extras import GrupoEstudiantes
    from core.nati import normalizar_telefono_whatsapp

    tel = normalizar_telefono_whatsapp(telefono or '')
    if not tel:
        return False
    est = Estudiante.objects.filter(telefono=tel).order_by('-id').first()
    if est is None:
        return False
    if est.cliente_id:
        return True
    if ProgresoEstudiante.objects.filter(estudiante=est).exists():
        return True
    return GrupoEstudiantes.objects.filter(estudiantes=est).exists()


def debe_cortar(telefono: str) -> bool:
    if not solo_registrados_activo():
        return False
    return not es_registrado(telefono)


def aviso_unico_24h(telefono: str) -> bool:
    """True si toca enviar el texto. Si Redis cae, se envía."""
    try:
        from core.locks import telefono_hash

        dia = datetime.now(_BOGOTA).strftime('%Y%m%d')
        clave = f'eki:linea:aviso:{telefono_hash(telefono)}:{dia}'
        return bool(_cliente_redis().set(clave, '1', nx=True, ex=26 * 3600))
    except Exception:
        logger.exception('linea_aviso_redis_caido')
        return True


def permitir_numero_nuevo(telefono: str) -> bool:
    """Tope diario de números que aún no son estudiantes. Redis caído: deja pasar."""
    try:
        from core.locks import telefono_hash

        tope = int(getattr(settings, 'LINEA_MAX_NUEVOS_DIA', 300) or 300)
        cliente = _cliente_redis()
        dia = datetime.now(_BOGOTA).strftime('%Y%m%d')
        clave = f'eki:linea:nuevos:{dia}'
        marca = telefono_hash(telefono)
        if cliente.sismember(clave, marca):
            return True
        if int(cliente.scard(clave) or 0) >= tope:
            logger.warning('linea_nuevos_tope')
            return False
        cliente.sadd(clave, marca)
        cliente.expire(clave, 48 * 3600)
        return True
    except Exception:
        logger.exception('linea_nuevos_redis_caido')
        return True
