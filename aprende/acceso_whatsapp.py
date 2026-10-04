"""Acceso web a Aprende iniciado desde WhatsApp (no OTP saliente en frío).

Twilio no puede enviar texto libre a un número que no ha escrito reciente
(ventana 24h / plantilla Meta). Por eso el estudiante escribe *aula* al bot
y eki responde *dentro* de esa conversación con enlace firmado + código.

El código se guarda en BD (no LocMem) para que cualquier worker de gunicorn
pueda validarlo al POST de login.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_KEYWORDS = re.compile(
    r'^\s*(?:'
    r'aula|aprende|'
    r'entrar\s+(?:al\s+)?aula|'
    r'acceso\s+(?:al\s+)?aula|'
    r'codigo\s+(?:aula|aprende)|'
    r'código\s+(?:aula|aprende)|'
    r'link\s+aula|enlace\s+aula'
    r')\s*$',
    re.IGNORECASE,
)


def _ttl() -> int:
    return int(getattr(settings, 'APRENDE_ACCESO_WA_TTL', 600) or 600)


def _otp_emit_max() -> int:
    return int(getattr(settings, 'APRENDE_OTP_EMIT_MAX', 8) or 8)


def _otp_emit_window() -> int:
    return int(getattr(settings, 'APRENDE_OTP_EMIT_WINDOW', 3600) or 3600)


MENSAJE_CODIGO_RECHAZADO = (
    'Código inválido o vencido. Escribe *aula* por WhatsApp para pedir uno nuevo.'
)


def client_ip_from_request(request) -> str:
    """IP del cliente en el login del aula.

    Una sola de estas redes:
    - EKI_BEHIND_CLOUDFLARE true: el borde es Cloudflare. Se usa
      CF-Connecting-IP y no se lee X-Forwarded-For. Si ese header falta,
      queda REMOTE_ADDR (el par TCP con Cloudflare).
    - Flag false o sin definir: no hay Cloudflare. Con
      EKI_TRUSTED_PROXY_COUNT en 0 (default) se usa REMOTE_ADDR y se
      ignora X-Forwarded-For. Si el conteo es N > 0 y el header trae al
      menos N saltos, se usa el último valor, el que agregó el proxy más
      cercano. Un cliente no elige la IP mientras el conteo sea 0.
    """
    if request is None:
        return ''
    remoto = (request.META.get('REMOTE_ADDR') or '').strip()
    if getattr(settings, 'EKI_BEHIND_CLOUDFLARE', False):
        cf = (request.META.get('HTTP_CF_CONNECTING_IP') or '').split(',')[0].strip()
        return cf or remoto
    try:
        saltos = int(getattr(settings, 'EKI_TRUSTED_PROXY_COUNT', 0) or 0)
    except (TypeError, ValueError):
        saltos = 0
    if saltos <= 0:
        return remoto
    partes = [
        parte.strip()
        for parte in (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')
        if parte.strip()
    ]
    if len(partes) >= saltos:
        return partes[-1]
    return remoto


def mensaje_pide_acceso_aula(texto: str) -> bool:
    t = (texto or '').strip()
    if not t or len(t) > 80:
        return False
    return bool(_KEYWORDS.match(t))


def generar_codigo() -> str:
    import secrets
    return f'{secrets.randbelow(1_000_000):06d}'


def emitir_acceso_desde_whatsapp(estudiante) -> str:
    """Genera solo código OTP + URL de login Aprende (sin handoff de Studio)."""
    from django.core.cache import cache

    from aprende.models import CodigoAccesoAprende
    from core.host_isolation import absolute_path

    emit_key = f'aprende_otp_emit:{int(estudiante.pk)}'
    emit_n = int(cache.get(emit_key, 0) or 0)
    if emit_n >= _otp_emit_max():
        mins = max(1, _otp_emit_window() // 60)
        return (
            "Ya pediste varios accesos seguidos. Espera unos minutos "
            f"(hasta ~{mins} min) e intenta de nuevo con *aula*."
        )
    cache.set(emit_key, emit_n + 1, _otp_emit_window())

    # Limpiar códigos vencidos del mismo estudiante
    corte = timezone.now() - timedelta(seconds=_ttl())
    CodigoAccesoAprende.objects.filter(estudiante=estudiante, creado__lt=corte).delete()
    CodigoAccesoAprende.objects.filter(estudiante=estudiante).delete()

    codigo = generar_codigo()
    for _ in range(8):
        if not CodigoAccesoAprende.objects.filter(codigo=codigo).exists():
            break
        codigo = generar_codigo()

    CodigoAccesoAprende.objects.create(codigo=codigo, estudiante=estudiante)
    login_url = absolute_path('aprende', '/aprende/estudiante/login/')
    nombre = (estudiante.nombre or '').split()[0] or 'Hola'
    mins = max(1, _ttl() // 60)
    return (
        f"{nombre}, aquí tienes acceso a *eki Aprende*:\n\n"
        f"1) Abre: {login_url}\n"
        f"2) Ingresa el código: *{codigo}*\n"
        f"(válido {mins} min)\n\n"
        "Si es tu primera vez en la web, crea tu contraseña ahí. "
        "Luego podrás entrar con tu documento y esa clave.\n"
        "Si olvidaste la clave, vuelve a escribir *aula* y créala de nuevo.\n\n"
        "Cuando quieras seguir el curso por WhatsApp, escribe *listo*.\n\n"
        "No compartas el código."
    )


def _aula_prefijo() -> str:
    return str(getattr(settings, 'AULA_LOGIN_PREFIJO', 'eki:aula') or 'eki:aula')


def _aula_int(nombre: str, default: int) -> int:
    try:
        return int(getattr(settings, nombre, default) or default)
    except (TypeError, ValueError):
        return default


def verificar_codigo_web(
    codigo: str,
    *,
    ip: str | None = None,
    documento: str = '',
) -> tuple[Optional[int], str]:
    """Canjea el código de aula.

    Redis caído cierra el login: rechaza con el mensaje genérico y no
    borra el código. No deja pasar.
    """
    import hmac

    from aprende.models import CodigoAccesoAprende
    from core.locks import telefono_hash
    from core.rate_limit import hit

    mensaje = MENSAJE_CODIGO_RECHAZADO
    prefijo = _aula_prefijo()
    ventana = _aula_int('AULA_LOGIN_VENTANA_SEG', 600)
    ip_hash = telefono_hash(ip or 'sin-ip')
    est_hash = ''

    _ok_global, n_global = hit(
        f'{prefijo}:global',
        _aula_int('AULA_LOGIN_MAX_GLOBAL', 200),
        ventana,
    )
    if n_global < 0:
        logger.warning('aula_login_fallido ip_hash=%s est_hash=', ip_hash)
        return None, mensaje
    if n_global == _aula_int('AULA_LOGIN_MAX_GLOBAL', 200) + 1:
        logger.warning('aula_login_ataque_probable')
        try:
            from core.locks import _cliente_redis

            _cliente_redis().set(
                f'{prefijo}:estricto',
                '1',
                ex=_aula_int('AULA_LOGIN_ESTRICTO_SEG', 900),
            )
        except Exception:
            logger.exception('rate_limit_redis_caido')
            return None, mensaje

    try:
        from core.locks import _cliente_redis

        estricto = bool(_cliente_redis().get(f'{prefijo}:estricto'))
    except Exception:
        logger.exception('rate_limit_redis_caido')
        return None, mensaje

    limite_ip = 3 if estricto else _aula_int('AULA_LOGIN_MAX_POR_IP', 10)
    ok_ip, n_ip = hit(f'{prefijo}:ip:{ip_hash}', limite_ip, ventana)
    if n_ip < 0 or not ok_ip:
        logger.warning('aula_login_fallido ip_hash=%s est_hash=', ip_hash)
        return None, mensaje

    from core.models import Estudiante

    estudiante = None
    if getattr(settings, 'AULA_LOGIN_REQUIERE_DOCUMENTO', False):
        doc = re.sub(r'\D', '', (documento or '').strip())
        if doc:
            estudiante = Estudiante.objects.filter(cedula=doc, activo=True).first()
        if estudiante is None:
            logger.warning('aula_login_fallido ip_hash=%s est_hash=', ip_hash)
            return None, mensaje
        est_hash = telefono_hash(str(estudiante.pk))
        ok_est, n_est = hit(
            f'{prefijo}:est:{est_hash}',
            _aula_int('AULA_LOGIN_MAX_POR_ESTUDIANTE', 5),
            ventana,
        )
        if n_est < 0 or not ok_est:
            CodigoAccesoAprende.objects.filter(estudiante=estudiante).delete()
            logger.warning('aula_login_fallido ip_hash=%s est_hash=%s', ip_hash, est_hash)
            return None, mensaje
    else:
        ok_est, n_est = True, 0

    raw = re.sub(r'\D', '', (codigo or '').strip())
    if len(raw) != 6:
        logger.warning('aula_login_fallido ip_hash=%s est_hash=%s', ip_hash, est_hash)
        return None, mensaje

    row = (
        CodigoAccesoAprende.objects.select_related('estudiante')
        .filter(codigo=raw)
        .first()
    )
    if row and not hmac.compare_digest(row.codigo.encode('utf-8'), raw.encode('utf-8')):
        row = None
    if row and estudiante is not None and row.estudiante_id != estudiante.pk:
        row = None
    if not row or row.creado < timezone.now() - timedelta(seconds=_ttl()):
        if row:
            row.delete()
        if estudiante is not None and n_est >= _aula_int('AULA_LOGIN_MAX_POR_ESTUDIANTE', 5):
            CodigoAccesoAprende.objects.filter(estudiante=estudiante).delete()
        logger.warning('aula_login_fallido ip_hash=%s est_hash=%s', ip_hash, est_hash)
        return None, mensaje

    eid = int(row.estudiante_id)
    row.delete()
    if est_hash:
        try:
            from core.locks import _cliente_redis

            _cliente_redis().delete(f'{prefijo}:est:{est_hash}')
        except Exception:
            logger.exception('rate_limit_redis_caido')
    return eid, ''

def next_aprende_seguro(raw: Optional[str]) -> str:
    nxt = (raw or '').strip() or '/aprende/estudiante/'
    if not nxt.startswith('/aprende/') or nxt.startswith('//'):
        return '/aprende/estudiante/'
    return nxt
