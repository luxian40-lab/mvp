"""Aviso de módulo disponible. Reexportados en core.models.

Las relaciones van por nombre: este archivo no importa otros modelos de core.
"""
from django.db import models


class AvisoModuloDisponible(models.Model):
    """Plantilla que sale cuando el calendario del cliente abre un módulo del curso."""

    cliente = models.ForeignKey(
        'core.Cliente',
        on_delete=models.CASCADE,
        related_name='avisos_modulo_disponible',
        verbose_name='Cliente',
    )
    curso = models.ForeignKey(
        'core.Curso',
        on_delete=models.CASCADE,
        related_name='avisos_modulo_disponible',
        verbose_name='Curso',
    )
    grupo = models.ForeignKey(
        'core.GrupoEstudiantes',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avisos_modulo_disponible',
        verbose_name='Grupo',
        help_text='Vacío = todos los estudiantes del cliente inscritos en el curso.',
    )
    phone_number_id = models.CharField(max_length=32, verbose_name='Línea')
    plantilla = models.ForeignKey(
        'core.PlantillaMeta',
        on_delete=models.PROTECT,
        related_name='avisos_modulo_disponible',
        verbose_name='Plantilla Meta',
        help_text='Aprobada y de la cuenta de esa línea. Variables: {{1}} nombre, {{2}} módulo, {{3}} curso.',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aviso de módulo disponible'
        verbose_name_plural = 'Avisos de módulo disponible'
        constraints = [
            models.UniqueConstraint(fields=['cliente', 'curso'], name='uniq_aviso_modulo_cliente_curso'),
        ]

    def __str__(self):
        return f'{self.cliente} → {self.curso}'


class AvisoModuloEnviado(models.Model):
    """Un aviso por persona y módulo. La fila se crea antes de enviar."""

    ESTADOS = [
        ('ENVIANDO', 'Enviando'),
        ('ENVIADO', 'Enviado'),
        ('FALLIDO', 'Fallido'),
    ]

    aviso = models.ForeignKey(AvisoModuloDisponible, on_delete=models.CASCADE, related_name='envios')
    estudiante = models.ForeignKey('core.Estudiante', on_delete=models.CASCADE, related_name='avisos_modulo')
    modulo = models.ForeignKey('core.Modulo', on_delete=models.CASCADE, related_name='avisos_enviados')
    estado = models.CharField(max_length=10, choices=ESTADOS, default='ENVIANDO')
    wamid = models.CharField(max_length=200, blank=True, default='')
    respuesta = models.TextField(blank=True, default='')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aviso de módulo enviado'
        verbose_name_plural = 'Avisos de módulo enviados'
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'modulo'], name='uniq_aviso_modulo_estudiante_modulo'),
        ]

    def __str__(self):
        return f'{self.estudiante_id} M{self.modulo_id} {self.estado}'
