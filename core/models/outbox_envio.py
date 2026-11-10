"""Outbox de envío WhatsApp. Distinto de EventOutbox (lago territorial).

Flag off: nadie escribe filas. El claim vive en PostgreSQL, no en Redis.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone

PENDIENTE = 'PENDIENTE'
ENVIANDO = 'ENVIANDO'
ENVIADO = 'ENVIADO'
ERROR = 'ERROR'
INCIERTO = 'INCIERTO'
_RECLAMABLE = (PENDIENTE,)
_correlacion_envio: ContextVar[str] = ContextVar('outbox_correlacion', default='')


def correlacion_en_vuelo() -> str:
    return _correlacion_envio.get() or ''


def outbox_activo() -> bool:
    return bool(getattr(settings, 'EKI_OUTBOX_ENVIO', False))


def _minutos_dudosas() -> int:
    try:
        return max(int(getattr(settings, 'WA_ENVIANDO_DUDOSO_MIN', 10) or 10), 1)
    except (TypeError, ValueError):
        return 10


class OutboxEnvio(models.Model):
    correlacion = models.CharField(max_length=64, unique=True)
    canal = models.CharField(max_length=16)
    telefono = models.CharField(max_length=32)
    phone_id = models.CharField(max_length=32, blank=True, default='')
    estado = models.CharField(max_length=20, default=PENDIENTE, db_index=True)
    wamid = models.CharField(max_length=200, blank=True, default='')
    codigo_error = models.CharField(max_length=32, blank=True, default='')
    claim_token = models.UUIDField(null=True, blank=True)
    intento_en = models.DateTimeField(null=True, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Outbox de envío'
        verbose_name_plural = 'Outbox de envíos'
        indexes = [
            models.Index(fields=['estado', 'intento_en'], name='outbox_envio_enviando'),
        ]

    def __str__(self):
        return f'{self.correlacion} {self.estado}'


def _solo_digitos(raw: str) -> str:
    return ''.join(ch for ch in str(raw or '') if ch.isdigit())[:32]


def registrar(*, correlacion: str, canal: str, telefono: str, phone_id: str = '') -> OutboxEnvio | None:
    if not outbox_activo():
        return None
    corr = (correlacion or '').strip() or str(uuid.uuid4())
    fila, _creada = OutboxEnvio.objects.get_or_create(
        correlacion=corr[:64],
        defaults={
            'canal': (canal or '')[:16],
            'telefono': _solo_digitos(telefono),
            'phone_id': (phone_id or '')[:32],
            'estado': PENDIENTE,
        },
    )
    return fila


def reclamar(correlacion: str):
    if not outbox_activo():
        return None
    corr = (correlacion or '').strip()
    if not corr:
        return None
    token = uuid.uuid4()
    n = OutboxEnvio.objects.filter(correlacion=corr, estado__in=_RECLAMABLE).update(
        estado=ENVIANDO,
        claim_token=token,
        intento_en=timezone.now(),
        intentos=F('intentos') + 1,
    )
    if n != 1:
        return None
    return token


def marcar(correlacion: str, estado: str, *, token, wamid: str = '', codigo_error: str = '') -> bool:
    if estado not in (ENVIADO, ERROR, INCIERTO):
        return False
    n = OutboxEnvio.objects.filter(
        correlacion=(correlacion or '').strip(),
        claim_token=token,
        estado=ENVIANDO,
    ).update(
        estado=estado,
        wamid=(wamid or '')[:200],
        codigo_error=(codigo_error or '')[:32],
    )
    return n == 1


def cerrar_con_wamid(correlacion: str, wamid: str) -> bool:
    """El status de Meta cierra ENVIANDO o INCIERTO. No reenvía."""
    n = OutboxEnvio.objects.filter(
        correlacion=(correlacion or '').strip(),
        estado__in=(ENVIANDO, INCIERTO),
    ).update(estado=ENVIADO, wamid=(wamid or '')[:200])
    return n == 1


def cerrar_por_status(*, wamid: str, opaco: str = '') -> bool:
    """Cierra por wamid ya guardado o por biz_opaque outbox:<correlacion>."""
    if not outbox_activo():
        return False
    mid = (wamid or '').strip()[:200]
    if not mid:
        return False
    n = OutboxEnvio.objects.filter(
        wamid=mid, estado__in=(ENVIANDO, INCIERTO),
    ).update(estado=ENVIADO)
    if n:
        return True
    bruto = (opaco or '').strip()
    if not bruto.startswith('outbox:'):
        return False
    return cerrar_con_wamid(bruto.split(':', 1)[1].strip(), mid)


def vencer_enviando(minutos: int | None = None) -> int:
    limite = timezone.now() - timedelta(minutes=minutos if minutos is not None else _minutos_dudosas())
    return OutboxEnvio.objects.filter(estado=ENVIANDO, intento_en__lt=limite).update(estado=INCIERTO)


def ejecutar(*, correlacion: str, canal: str, telefono: str, phone_id: str, enviar):
    """Claim, envía, marca. Flag off: solo llama enviar(). INCIERTO no se reenvía."""
    if not outbox_activo():
        return enviar()
    fila = registrar(
        correlacion=correlacion, canal=canal, telefono=telefono, phone_id=phone_id,
    )
    if fila is None:
        return enviar()
    if fila.estado == ENVIADO:
        return {'success': True, 'mensaje_id': fila.wamid or None, 'response': 'ya_enviado'}
    token = reclamar(fila.correlacion)
    if token is None:
        return {'success': False, 'mensaje_id': None, 'response': 'sin_claim'}
    ctx = _correlacion_envio.set(fila.correlacion)
    try:
        resultado = enviar()
    finally:
        _correlacion_envio.reset(ctx)
    if isinstance(resultado, dict) and resultado.get('success'):
        marcar(
            fila.correlacion, ENVIADO, token=token,
            wamid=str(resultado.get('mensaje_id') or ''),
        )
    else:
        marcar(fila.correlacion, INCIERTO, token=token)
    return resultado
