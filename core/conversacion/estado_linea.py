"""Estado del curso por persona y línea de WhatsApp.

Una fila por (estudiante, phone id). Los campos de Estudiante siguen siendo los
que lee el código; esta tabla guarda una copia por línea.
Este módulo no importa nada de core: core.models lo importa a él.
"""
from __future__ import annotations

from django.db import models


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
