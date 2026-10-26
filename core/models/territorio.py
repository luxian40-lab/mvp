"""Modelos de territorio (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models


class SenalTerritorial(models.Model):
    """Señal tipada para correlación territorial (ej. salud.sintoma.diarrea)."""

    tipo = models.CharField(
        max_length=80,
        db_index=True,
        help_text='Ej: salud.sintoma.diarrea',
    )
    territory_id = models.CharField(max_length=32, db_index=True)
    org_id = models.IntegerField(null=True, blank=True, db_index=True)
    confianza = models.FloatField(default=0.7)
    fuente = models.CharField(max_length=40, default='manual')
    occurred_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Señal territorial'
        verbose_name_plural = 'Señales territoriales'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['territory_id', 'tipo', '-occurred_at']),
        ]

    def __str__(self):
        return f'{self.tipo} @ {self.territory_id}'


class AlertaTerritorial(models.Model):
    """Cluster detectado (density_v0) sobre SenalTerritorial."""

    ESTADO_DETECTADA = 'detectada'
    ESTADO_VALIDADA = 'validada'
    ESTADO_COMUNICADA = 'comunicada'
    ESTADO_ACCIONADA = 'accionada'
    ESTADO_CERRADA = 'cerrada'
    ESTADO_CHOICES = [
        (ESTADO_DETECTADA, 'Detectada'),
        (ESTADO_VALIDADA, 'Validada'),
        (ESTADO_COMUNICADA, 'Comunicada'),
        (ESTADO_ACCIONADA, 'Accionada'),
        (ESTADO_CERRADA, 'Cerrada'),
    ]

    familia = models.CharField(max_length=80, db_index=True)
    subtipo = models.CharField(max_length=80, default='cluster')
    territory_id = models.CharField(max_length=32, db_index=True)
    ventana_horas = models.PositiveIntegerField(default=72)
    conteo = models.PositiveIntegerField(default=0)
    score = models.FloatField(default=0.0)
    min_k = models.PositiveIntegerField(default=3)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_DETECTADA,
        db_index=True,
    )
    explicacion = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alerta territorial'
        verbose_name_plural = 'Alertas territoriales'
        ordering = ['-actualizado_en']
        indexes = [
            models.Index(fields=['territory_id', 'estado', '-score']),
        ]

    def __str__(self):
        return f'{self.familia}.{self.subtipo} @ {self.territory_id} n={self.conteo}'
