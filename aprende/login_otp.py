"""OTP por WhatsApp para login de estudiante en Aprende.

Cédula + teléfono solo identifican; el código enviado al WhatsApp
registrado prueba posesión del canal.
"""

from __future__ import annotations

import logging
import secrets
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

SESSION_PENDING_ID = 'aprende_login_pending_id'
SESSION_PENDING_MASK = 'aprende_login_pending_mask'


def _ttl() -> int:
    return int(getattr(settings, 'APRENDE_LOGIN_OTP_TTL', 600) or 600)


def _max_attempts() -> int:
    return int(getattr(settings, 'APRENDE_LOGIN_OTP_MAX_ATTEMPTS', 5) or 5)


def _cooldown() -> int:
    return int(getattr(settings, 'APRENDE_LOGIN_OTP_COOLDOWN', 45) or 45)


def _hour_cap() -> int:
    return int(getattr(settings, 'APRENDE_LOGIN_OTP_HOUR_CAP', 8) or 8)


def _otp_key(estudiante_id: int) -> str:
    return f'aprende_login_otp:v1:{estudiante_id}'


def _cooldown_key(estudiante_id: int) -> str:
    return f'aprende_login_otp_cd:v1:{estudiante_id}'


def _hour_key(estudiante_id: int) -> str:
    return f'aprende_login_otp_hour:v1:{estudiante_id}'


def enmascarar_telefono(telefono: str) -> str:
    digits = ''.join(c for c in (telefono or '') if c.isdigit())
    if len(digits) < 4:
        return '****'
    return f'***{digits[-4:]}'


def limpiar_pending(session) -> None:
    session.pop(SESSION_PENDING_ID, None)
    session.pop(SESSION_PENDING_MASK, None)


def puede_reenviar(estudiante_id: int) -> tuple[bool, str]:
    cd = _cooldown()
    if cd > 0 and cache.get(_cooldown_key(estudiante_id)):
        return False, 'Espera unos segundos antes de pedir otro código.'
    enviados = int(cache.get(_hour_key(estudiante_id)) or 0)
    if enviados >= _hour_cap():
        return False, 'Demasiados códigos enviados. Intenta en una hora.'
    return True, ''


def generar_codigo() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def guardar_otp(estudiante_id: int, codigo: str) -> None:
    cache.set(
        _otp_key(estudiante_id),
        {'codigo': codigo, 'intentos': 0},
        timeout=_ttl(),
    )
    cd = _cooldown()
    if cd > 0:
        cache.set(_cooldown_key(estudiante_id), 1, timeout=cd)
    hour_key = _hour_key(estudiante_id)
    n = int(cache.get(hour_key) or 0) + 1
    cache.set(hour_key, n, timeout=3600)


def verificar_otp(estudiante_id: int, codigo: str) -> tuple[bool, str]:
    raw = (codigo or '').strip()
    if not raw.isdigit() or len(raw) != 6:
        return False, 'El código debe tener 6 dígitos.'
    data = cache.get(_otp_key(estudiante_id))
    if not data:
        return False, 'El código expiró. Solicita uno nuevo.'
    intentos = int(data.get('intentos') or 0) + 1
    max_att = _max_attempts()
    if intentos > max_att:
        cache.delete(_otp_key(estudiante_id))
        return False, 'Demasiados intentos. Solicita un código nuevo.'
    data['intentos'] = intentos
    cache.set(_otp_key(estudiante_id), data, timeout=_ttl())
    if secrets.compare_digest(str(data.get('codigo') or ''), raw):
        cache.delete(_otp_key(estudiante_id))
        return True, ''
    restantes = max_att - intentos
    if restantes <= 0:
        cache.delete(_otp_key(estudiante_id))
        return False, 'Código incorrecto. Solicita uno nuevo.'
    return False, f'Código incorrecto. Te quedan {restantes} intentos.'


def enviar_codigo_whatsapp(telefono: str, codigo: str, nombre: str = '') -> tuple[bool, str]:
    """Envía el OTP. En tests/local sin Twilio, puede ecoar si APRENDE_LOGIN_OTP_DEV=1."""
    if getattr(settings, 'APRENDE_LOGIN_OTP_DEV', False) or (
        settings.DEBUG and not getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    ):
        logger.warning('OTP Aprende DEV (no Twilio): estudiante recibe código en logs')
        logger.info('APRENDE_LOGIN_OTP codigo=%s tel=%s', codigo, enmascarar_telefono(telefono))
        return True, ''

    from core.utils import enviar_whatsapp_twilio

    saludo = (nombre or '').split()[0] if nombre else ''
    pref = f'Hola {saludo}, ' if saludo else ''
    texto = (
        f'{pref}tu código de acceso a eki Aprende es: *{codigo}*\n\n'
        f'Válido por {_ttl() // 60} minutos. '
        'Si no pediste entrar al aula, ignora este mensaje.'
    )
    try:
        res = enviar_whatsapp_twilio(telefono, texto, canal_evento='aprende_login_otp')
    except Exception as exc:
        logger.exception('Error enviando OTP Aprende: %s', exc)
        return False, 'No pudimos enviar el código por WhatsApp. Intenta de nuevo.'
    if not res.get('success'):
        logger.error('Twilio OTP falló: %s', res.get('response'))
        return False, 'No pudimos enviar el código por WhatsApp. Intenta de nuevo.'
    return True, ''


def emitir_otp(estudiante) -> tuple[bool, str]:
    ok, msg = puede_reenviar(estudiante.pk)
    if not ok:
        return False, msg
    codigo = generar_codigo()
    ok_send, err = enviar_codigo_whatsapp(estudiante.telefono, codigo, estudiante.nombre or '')
    if not ok_send:
        return False, err
    guardar_otp(estudiante.pk, codigo)
    return True, ''


def next_aprende_seguro(raw: Optional[str]) -> str:
    nxt = (raw or '').strip() or '/aprende/estudiante/'
    if not nxt.startswith('/aprende/') or nxt.startswith('//'):
        return '/aprende/estudiante/'
    return nxt
