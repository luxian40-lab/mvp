"""Notas internas del equipo sobre un estudiante. No salen por WhatsApp."""

from django.conf import settings
from django.db import models


class NotaEstudiante(models.Model):
    estudiante = models.ForeignKey(
        'core.Estudiante',
        on_delete=models.CASCADE,
        related_name='notas_equipo',
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='notas_estudiante',
    )
    texto = models.TextField()
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado', '-pk']
        indexes = [
            models.Index(fields=['estudiante', '-creado'], name='nota_est_est_creado'),
        ]
        verbose_name = 'Nota de estudiante'
        verbose_name_plural = 'Notas de estudiante'

    def __str__(self):
        return f'Nota {self.pk} de {self.estudiante_id}'
