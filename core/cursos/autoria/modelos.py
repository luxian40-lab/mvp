"""Versiones de curso. Expand: tablas nuevas; con el flag apagado nadie las escribe."""
from __future__ import annotations

from django.db import models


class CursoVersion(models.Model):
    """Instantánea publicada o borrador de un curso.

    numero crece por curso. Solo una version_publicada por curso (FK en Curso).
    """

    BORRADOR = 'borrador'
    PUBLICADO = 'publicado'
    ARCHIVADO = 'archivado'
    ESTADO_CHOICES = [
        (BORRADOR, 'Borrador'),
        (PUBLICADO, 'Publicado'),
        (ARCHIVADO, 'Archivado'),
    ]

    curso = models.ForeignKey(
        'core.Curso',
        on_delete=models.CASCADE,
        related_name='versiones',
    )
    numero = models.PositiveIntegerField()
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default=BORRADOR)
    # Snapshot del ensamblado (módulos/bloques/mensajes). Vacío hasta el corte de publicar.
    ensamblado = models.JSONField(default=dict, blank=True)
    nota = models.CharField(max_length=200, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)
    publicado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Versión de curso'
        verbose_name_plural = 'Versiones de curso'
        constraints = [
            models.UniqueConstraint(
                fields=['curso', 'numero'],
                name='uniq_curso_version_numero',
            ),
        ]
        indexes = [
            models.Index(fields=['curso', 'estado'], name='curso_version_estado'),
        ]

    def __str__(self):
        return f'{self.curso_id} v{self.numero} ({self.estado})'
