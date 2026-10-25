"""Estado del curso por persona y línea de WhatsApp.

Una fila por (estudiante, phone id). Los campos de Estudiante siguen siendo los
que lee el código; esta tabla guarda una copia por línea.

Con EKI_ESTADO_LINEA_ESCRITURA:
- un turno o una campaña de una línea escriben en la fila de esa línea;
- un cambio hecho fuera de una línea (admin, tareas) pasa a todas las filas,
  porque hoy el estado es uno solo y así lo ve todo el mundo.
Una fila que no existe nace del estado compartido.

Este módulo no importa nada de core: core.models lo importa a él.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable

from django.apps import apps
from django.conf import settings
from django.db import DatabaseError, models, transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

CAMPOS = ('estado_chat', 'estado_onboarding', 'contexto_temporal')


class EstadoLinea(models.Model):
    estudiante = models.ForeignKey(
        'core.Estudiante', on_delete=models.CASCADE, related_name='estados_linea',
    )
    phone_id = models.CharField('Phone number id', max_length=64)
    estado_chat = models.CharField(max_length=50, blank=True, default='')
    estado_onboarding = models.CharField(max_length=50, blank=True, default='')
    contexto_temporal = models.JSONField(null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('estudiante', 'phone_id'), name='estado_linea_unico'),
        ]
        verbose_name = 'Estado por línea'
        verbose_name_plural = 'Estados por línea'

    def __str__(self):
        return f'{self.estudiante_id} @ {self.phone_id}: {self.estado_chat} / {self.estado_onboarding}'


# (estudiante_id, phone_id) de la línea que está escribiendo: un turno o una campaña.
_linea: ContextVar[tuple[int | None, str] | None] = ContextVar('eki_estado_linea', default=None)


def escritura_activa() -> bool:
    return bool(getattr(settings, 'EKI_ESTADO_LINEA_ESCRITURA', False))


def _valores_de(estudiante_id) -> dict | None:
    estudiantes = apps.get_model('core', 'Estudiante')
    return estudiantes.objects.filter(pk=estudiante_id).values(*CAMPOS).first()


def _para_fila(valores: dict) -> dict:
    datos = {c: valores[c] for c in CAMPOS if c in valores}
    for campo in ('estado_chat', 'estado_onboarding'):
        if campo in datos:
            datos[campo] = datos[campo] or ''
    return datos


def guardar_en_linea(estudiante_id: int, phone_id: str, valores: dict, base: dict | None = None) -> None:
    """Escribe valores en la fila de esa línea. Si no existe, nace de base (el estado compartido)."""
    cambios = _para_fila(valores)
    filas = EstadoLinea.objects.filter(estudiante_id=estudiante_id, phone_id=phone_id)
    if filas.update(**cambios, actualizado_en=timezone.now()):
        return
    datos = _para_fila(base or {})
    datos.update(cambios)
    fila, creada = EstadoLinea.objects.get_or_create(
        estudiante_id=estudiante_id, phone_id=phone_id, defaults=datos,
    )
    if not creada:
        filas.update(**cambios, actualizado_en=timezone.now())


def _copiar_a_linea(estudiante, phone_id: str) -> None:
    pk = getattr(estudiante, 'pk', None)
    if not pk:
        return
    try:
        with transaction.atomic():
            valores = _valores_de(pk)
            if valores is not None:
                guardar_en_linea(pk, phone_id, valores)
    except DatabaseError:
        logger.warning('estado_linea_no_copiado phone_id=%s', phone_id, exc_info=True)


@contextmanager
def en_linea(phone_id: str, buscar: Callable[[], object | None], *, copiar_al_salir: bool = True):
    """Lo que el estudiante cambie aquí dentro va a la fila de esta línea.

    copiar_al_salir: al terminar, la fila queda igual al estudiante (turnos).
    Una campaña no copia: solo escribe lo que cambia.
    """
    phone_id = (phone_id or '').strip()
    if not escritura_activa() or not phone_id:
        yield
        return
    estudiante = buscar()
    token = _linea.set((getattr(estudiante, 'pk', None), phone_id))
    try:
        yield
    finally:
        _linea.reset(token)
        if copiar_al_salir:
            _copiar_a_linea(estudiante or buscar(), phone_id)


def _toca_estado(update_fields) -> bool:
    return update_fields is None or bool(set(update_fields) & set(CAMPOS))


@receiver(pre_save, sender='core.Estudiante')
def _recordar_estado(sender, instance, update_fields=None, **kwargs):
    instance._eki_estado_antes = None
    if not escritura_activa() or not instance.pk or not _toca_estado(update_fields):
        return
    try:
        with transaction.atomic():
            instance._eki_estado_antes = _valores_de(instance.pk)
    except DatabaseError:
        logger.warning('estado_linea_antes_no_leido', exc_info=True)


@receiver(post_save, sender='core.Estudiante')
def _copiar_estado(sender, instance, created, update_fields=None, **kwargs):
    antes = getattr(instance, '_eki_estado_antes', None)
    instance._eki_estado_antes = None
    if not antes:
        return
    campos = CAMPOS if update_fields is None else [c for c in CAMPOS if c in update_fields]
    cambios = {c: getattr(instance, c) for c in campos if getattr(instance, c) != antes.get(c)}
    if not cambios:
        return
    linea = _linea.get()
    try:
        with transaction.atomic():
            if linea and linea[0] == instance.pk:
                guardar_en_linea(instance.pk, linea[1], cambios, base=antes)
            else:
                EstadoLinea.objects.filter(estudiante_id=instance.pk).update(
                    **_para_fila(cambios), actualizado_en=timezone.now(),
                )
    except DatabaseError:
        logger.warning('estado_linea_no_escrito', exc_info=True)
