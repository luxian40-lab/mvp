"""Bandeja durable de entrada. Bloque 1.

Guarda el orden de llegada a la base, por teléfono. Un mensaje posterior no
se aplica mientras uno anterior del mismo teléfono sigue abierto.

EKI_BANDEJA_ENTRADA en false: anotar y tomar turno no miran la base, y el
candado de core/locks.py sigue igual. La firma del POST se valida en el
webhook, antes de anotar_payload_meta o anotar_payload_twilio.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import IntegrityError, models, transaction

logger = logging.getLogger(__name__)

PENDIENTE = 'PENDIENTE'
PROCESANDO = 'PROCESANDO'
PROCESADO = 'PROCESADO'
FALLIDO = 'FALLIDO'
TOPE_INTENTOS = 5
_ABIERTOS = (PENDIENTE, PROCESANDO)


class EntradaBandeja(models.Model):
    """Un mensaje entrante, en el orden en que llegó a la base."""

    canal = models.CharField(max_length=16)
    external_id = models.CharField(max_length=128)
    telefono = models.CharField(max_length=32)
    secuencia = models.PositiveIntegerField()
    estado = models.CharField(max_length=16, default=PENDIENTE)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'entrada de bandeja'
        verbose_name_plural = 'entradas de bandeja'
        constraints = [
            models.UniqueConstraint(
                fields=['canal', 'external_id'],
                name='uniq_entrada_bandeja_externo',
            ),
            models.UniqueConstraint(
                fields=['telefono', 'secuencia'],
                name='uniq_entrada_bandeja_secuencia',
            ),
        ]
        indexes = [
            models.Index(
                fields=['telefono', 'estado', 'secuencia'],
                name='entrada_bandeja_cabeza',
            ),
        ]

    def __str__(self):
        return f'{self.canal}:{self.external_id}'


class FueraDeTurno(Exception):
    """Este mensaje no es la cabeza. No se aplicó y su fila no cambió."""


def bandeja_activa() -> bool:
    return bool(getattr(settings, 'EKI_BANDEJA_ENTRADA', False))


_STATUS_TWILIO = frozenset({
    'queued', 'sending', 'sent', 'delivered', 'undelivered', 'failed', 'read',
})


def anotar_payload_meta(payload) -> None:
    """Anota cada messages[].id. No-op con el flag apagado. No mira statuses."""
    if not bandeja_activa() or not isinstance(payload, dict):
        return
    from core.canal.telefono import normalizar_telefono
    from core.webhook_evento import CANAL_META

    for entry in payload.get('entry') or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get('changes') or []:
            if not isinstance(change, dict):
                continue
            value = change.get('value')
            if not isinstance(value, dict):
                continue
            for message in value.get('messages') or []:
                if not isinstance(message, dict):
                    continue
                mid = str(message.get('id') or '').strip()[:128]
                if not mid:
                    continue
                telefono = normalizar_telefono(str(message.get('from') or '')) or 'sin-telefono'
                anotar_llegada(CANAL_META, mid, telefono, {'id': mid})


def anotar_payload_twilio(data) -> None:
    """Anota el MessageSid. No-op con el flag apagado o si es un status callback."""
    if not bandeja_activa() or not hasattr(data, 'get'):
        return
    estado = (data.get('MessageStatus') or data.get('SmsStatus') or '').lower()
    if estado in _STATUS_TWILIO:
        return
    from core.canal.telefono import normalizar_telefono
    from core.webhook_evento import CANAL_TWILIO

    sid = str(data.get('MessageSid') or '').strip()[:128]
    if not sid:
        return
    telefono = normalizar_telefono(str(data.get('From') or '')) or 'sin-telefono'
    anotar_llegada(CANAL_TWILIO, sid, telefono, {'MessageSid': sid})


def tomar_turno(canal, external_id, telefono) -> bool:
    """True si este mensaje puede aplicarse ahora.

    Flag apagado, o fila inexistente: True, sin escribir.
    Si hay una abierta más vieja del mismo teléfono: False, sin cambiar filas.
    Si esta es la cabeza pendiente, pasa a PROCESANDO.
    """
    if not bandeja_activa():
        return True
    canal = (canal or '')[:16]
    external_id = (external_id or '').strip()[:128]
    if not external_id:
        return True
    with transaction.atomic():
        fila = (
            EntradaBandeja.objects.select_for_update()
            .filter(canal=canal, external_id=external_id)
            .first()
        )
        if fila is None:
            return True
        if fila.estado in (PROCESADO, FALLIDO):
            return False
        if _hay_abierta_anterior(fila):
            return False
        if fila.estado == PENDIENTE:
            fila.estado = PROCESANDO
            fila.save(update_fields=['estado'])
        return True


def cerrar_turno(canal, external_id) -> None:
    """Marca PROCESADO la fila de este id, si es la cabeza. No-op con el flag apagado."""
    if not bandeja_activa():
        return
    canal = (canal or '')[:16]
    external_id = (external_id or '').strip()[:128]
    if not external_id:
        return
    fila = EntradaBandeja.objects.filter(canal=canal, external_id=external_id).first()
    if fila is None:
        return
    cerrar_procesado(fila)


def omitir_turno(canal, external_id) -> None:
    """Cierra esta fila aunque no sea la cabeza. No-op con el flag apagado.

    Sirve cuando el mensaje se aceptó y no va a correr: flood o duplicado.
    """
    if not bandeja_activa():
        return
    canal = (canal or '')[:16]
    external_id = (external_id or '').strip()[:128]
    if not external_id:
        return
    EntradaBandeja.objects.filter(
        canal=canal,
        external_id=external_id,
        estado__in=_ABIERTOS,
    ).update(estado=PROCESADO)


def soltar_turno_fallido(canal, external_id) -> None:
    """Fallo definitivo de la cabeza: FALLIDO, y el teléfono puede seguir."""
    if not bandeja_activa():
        return
    canal = (canal or '')[:16]
    external_id = (external_id or '').strip()[:128]
    if not external_id:
        return
    with transaction.atomic():
        fila = (
            EntradaBandeja.objects.select_for_update()
            .filter(canal=canal, external_id=external_id)
            .first()
        )
        if fila is None or fila.estado in (PROCESADO, FALLIDO):
            return
        if _hay_abierta_anterior(fila):
            return
        fila.estado = FALLIDO
        if not fila.ultimo_error:
            fila.ultimo_error = 'fallo definitivo'
        fila.save(update_fields=['estado', 'ultimo_error'])
        logger.error(
            'bandeja_cabeza_fallida canal=%s external_id=%s intentos=%s',
            fila.canal,
            fila.external_id,
            fila.intentos,
        )


def aplicar_con_turno(canal, external_id, telefono, aplicar):
    """Corre aplicar solo si este mensaje es la cabeza. Flag apagado: solo aplica."""
    if not bandeja_activa():
        return aplicar()
    if not tomar_turno(canal, external_id, telefono):
        raise FueraDeTurno()
    resultado = aplicar()
    cerrar_turno(canal, external_id)
    return resultado


def anotar_tras_firma(*, firma_valida, canal, external_id, telefono, payload=None):
    """None si la firma no vale: no crea fila. Si vale, anota o devuelve la ya anotada."""
    if not firma_valida:
        return None
    fila, _nueva = anotar_llegada(canal, external_id, telefono, payload)
    return fila


def anotar_llegada(canal, external_id, telefono, payload=None):
    """Crea la fila o devuelve la del mismo (canal, external_id). La secuencia es por teléfono."""
    canal = (canal or '')[:16]
    external_id = (external_id or '').strip()[:128]
    if not external_id:
        raise ValueError('external_id vacio')
    telefono = (telefono or '').strip()[:32] or 'sin-telefono'
    previa = EntradaBandeja.objects.filter(canal=canal, external_id=external_id).first()
    if previa:
        return previa, False
    datos = dict(payload) if isinstance(payload, dict) else {}
    for _ in range(5):
        try:
            with transaction.atomic():
                otra = (
                    EntradaBandeja.objects.select_for_update()
                    .filter(canal=canal, external_id=external_id)
                    .first()
                )
                if otra:
                    return otra, False
                ultima = (
                    EntradaBandeja.objects.select_for_update()
                    .filter(telefono=telefono)
                    .order_by('-secuencia')
                    .first()
                )
                secuencia = (ultima.secuencia + 1) if ultima else 1
                fila = EntradaBandeja.objects.create(
                    canal=canal,
                    external_id=external_id,
                    telefono=telefono,
                    secuencia=secuencia,
                    estado=PENDIENTE,
                    payload=datos,
                )
                return fila, True
        except IntegrityError:
            previa = EntradaBandeja.objects.filter(
                canal=canal, external_id=external_id,
            ).first()
            if previa:
                return previa, False
    raise IntegrityError('entrada_bandeja_no_anotada')


def reclamar_cabeza(telefono):
    """La más antigua abierta de ese teléfono. Si estaba pendiente, pasa a PROCESANDO.

    Las posteriores quedan como estaban. None si no hay ninguna abierta.
    """
    telefono = (telefono or '').strip()[:32] or 'sin-telefono'
    with transaction.atomic():
        abiertas = list(
            EntradaBandeja.objects.select_for_update()
            .filter(telefono=telefono, estado__in=_ABIERTOS)
            .order_by('secuencia')
        )
        if not abiertas:
            return None
        cabeza = abiertas[0]
        if cabeza.estado == PENDIENTE:
            cabeza.estado = PROCESANDO
            cabeza.save(update_fields=['estado'])
        return cabeza


def cerrar_procesado(entrada):
    """Marca PROCESADO solo si esta fila es la cabeza abierta."""
    with transaction.atomic():
        fila = EntradaBandeja.objects.select_for_update().get(pk=entrada.pk)
        if fila.estado == PROCESADO:
            return fila
        if fila.estado == FALLIDO or _hay_abierta_anterior(fila):
            return fila
        fila.estado = PROCESADO
        fila.save(update_fields=['estado'])
        return fila


def anotar_fallo(entrada, error=''):
    """Suma un intento de la cabeza. Al quinto, FALLIDO y la cola de ese teléfono sigue.

    Si la fila no es la cabeza, no cambia nada.
    """
    with transaction.atomic():
        fila = EntradaBandeja.objects.select_for_update().get(pk=entrada.pk)
        if fila.estado in (PROCESADO, FALLIDO) or _hay_abierta_anterior(fila):
            return fila.estado
        fila.intentos += 1
        fila.ultimo_error = (error or '')[:2000]
        fila.estado = FALLIDO if fila.intentos >= TOPE_INTENTOS else PENDIENTE
        fila.save(update_fields=['intentos', 'ultimo_error', 'estado'])
        if fila.estado == FALLIDO:
            logger.error(
                'bandeja_cabeza_fallida canal=%s external_id=%s intentos=%s',
                fila.canal,
                fila.external_id,
                fila.intentos,
            )
        return fila.estado


def anotar_fallo_id(canal, external_id, error=''):
    """Suma un intento de esta fila si es la cabeza. No-op con el flag apagado."""
    if not bandeja_activa():
        return None
    canal = (canal or '')[:16]
    external_id = (external_id or '').strip()[:128]
    if not external_id:
        return None
    fila = EntradaBandeja.objects.filter(canal=canal, external_id=external_id).first()
    if fila is None:
        return None
    return anotar_fallo(fila, error)


def _hay_abierta_anterior(fila) -> bool:
    return EntradaBandeja.objects.filter(
        telefono=fila.telefono,
        secuencia__lt=fila.secuencia,
        estado__in=_ABIERTOS,
    ).exists()
