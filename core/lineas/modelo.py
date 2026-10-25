"""Líneas de WhatsApp Cloud API guardadas en la base.

Solo cuentan con EKI_LINEAS_BD_ENABLED encendido y al menos una fila activa.
Si no, manda META_LINEAS y las variables de siempre (core.lineas.meta).
Este módulo no importa core.models ni core.lineas.meta: devuelve tuplas.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.lineas.perfil import USO_COMPLETA, USO_SOLO_CURSOS

logger = logging.getLogger(__name__)

CLAVE_CACHE = 'eki:lineas_bd:v1'

USOS_LINEA = [
    (USO_COMPLETA, 'Completa: menú, carrusel, planes y asesores'),
    (USO_SOLO_CURSOS, 'Curso lineal: campaña y curso, sin menú'),
]


class LineaWhatsapp(models.Model):
    phone_id = models.CharField('Phone number id', max_length=64, unique=True)
    e164 = models.CharField('Número', max_length=20, blank=True, default='', help_text='Solo dígitos, con indicativo.')
    nombre = models.CharField(max_length=80)
    waba_id = models.CharField(
        'WABA', max_length=64, blank=True, default='',
        help_text='Vacío = la WABA que ya usa la línea según el entorno.',
    )
    cliente = models.ForeignKey(
        'core.Cliente', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='lineas_whatsapp', help_text='Empresa dueña de la línea. Vacío = de eki.',
    )
    uso = models.CharField(max_length=20, choices=USOS_LINEA, default=USO_COMPLETA)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0, help_text='La primera activa es la línea principal.')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('orden', 'id')
        verbose_name = 'Línea de WhatsApp'
        verbose_name_plural = 'Líneas de WhatsApp'

    def __str__(self):
        return f'{self.nombre} ({self.e164 or self.phone_id})'

    def save(self, *args, **kwargs):
        self.phone_id = (self.phone_id or '').strip()
        self.e164 = ''.join(c for c in (self.e164 or '') if c.isdigit())
        self.waba_id = (self.waba_id or '').strip()
        super().save(*args, **kwargs)


def filas_activas() -> tuple[tuple, ...]:
    """(phone_id, e164, nombre, uso, waba_id, cliente_id) de las líneas activas. Vacío si la tabla falla."""
    filas = cache.get(CLAVE_CACHE)
    if filas is not None:
        return filas
    try:
        filas = tuple(
            LineaWhatsapp.objects.filter(activo=True).values_list(
                'phone_id', 'e164', 'nombre', 'uso', 'waba_id', 'cliente_id',
            )
        )
    except DatabaseError:
        logger.warning('lineas_bd_no_leidas', exc_info=True)
        return ()
    cache.set(CLAVE_CACHE, filas, int(getattr(settings, 'EKI_LINEAS_BD_CACHE_SEG', 60)))
    return filas


@receiver(post_save, sender=LineaWhatsapp)
@receiver(post_delete, sender=LineaWhatsapp)
def _olvidar_cache(**_kwargs):
    cache.delete(CLAVE_CACHE)
