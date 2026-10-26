"""Modelos de empleabilidad (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.models.clientes import Cliente
from core.models.estudiantes import Estudiante


class AliadoEmpleabilidad(models.Model):
    """Empresas aliadas para gamificación geolocalizada de empleabilidad."""
    nombre_empresa = models.CharField(max_length=200, verbose_name='Nombre de la empresa')
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aliados_empleabilidad',
        verbose_name='Cliente asociado',
        help_text='Opcional. Si se define, solo aplica para estudiantes de ese cliente.'
    )
    latitud = models.FloatField(verbose_name='Latitud')
    longitud = models.FloatField(verbose_name='Longitud')
    cupos_disponibles = models.PositiveIntegerField(
        default=0,
        verbose_name='Cupos disponibles',
        help_text='Vacantes disponibles para priorización del radar de empleabilidad.'
    )
    prioridad = models.PositiveSmallIntegerField(
        default=3,
        verbose_name='Prioridad (1-5)',
        help_text='5 = máxima prioridad para aparecer en el radar de oportunidades.'
    )
    vigencia_desde = models.DateField(
        null=True,
        blank=True,
        verbose_name='Vigencia desde',
        help_text='Fecha de inicio de vigencia de la oportunidad.'
    )
    vigencia_hasta = models.DateField(
        null=True,
        blank=True,
        verbose_name='Vigencia hasta',
        help_text='Fecha de fin de vigencia de la oportunidad.'
    )
    vacantes_activas = models.BooleanField(default=True, verbose_name='Vacantes activas')
    codigo_secreto = models.CharField(max_length=120, verbose_name='Código secreto')
    indicacion_sector = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Indicación de sector',
        help_text='Ej: costado oriental del parque principal'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aliado de Empleabilidad'
        verbose_name_plural = 'Aliados de Empleabilidad'
        ordering = ['nombre_empresa']

    def __str__(self):
        return self.nombre_empresa


class MisionEmpleabilidad(models.Model):
    """Misiones de exploración/validación de oportunidades por proximidad."""

    ESTADO_CHOICES = [
        ('descubierta', 'Descubierta'),
        ('reclamada', 'Reclamada'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    FLUJO_CHOICES = [
        ('descubierto', 'Descubierto'),
        ('interesado', 'Interesado'),
        ('postulado', 'Postulado'),
        ('entrevista', 'Entrevista'),
        ('vinculado', 'Vinculado'),
        ('descartado', 'Descartado'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='misiones_empleabilidad',
        verbose_name='Cliente'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='misiones_empleabilidad',
        verbose_name='Estudiante'
    )
    aliado = models.ForeignKey(
        AliadoEmpleabilidad,
        on_delete=models.CASCADE,
        related_name='misiones_empleabilidad',
        verbose_name='Aliado'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='descubierta', verbose_name='Estado')
    latitud = models.FloatField(null=True, blank=True, verbose_name='Latitud referencia')
    longitud = models.FloatField(null=True, blank=True, verbose_name='Longitud referencia')
    distancia_metros = models.FloatField(null=True, blank=True, verbose_name='Distancia en metros')
    codigo_validado = models.BooleanField(default=False, verbose_name='Código validado')
    puntos_otorgados = models.IntegerField(default=0, verbose_name='Puntos otorgados')
    estado_flujo = models.CharField(
        max_length=20,
        choices=FLUJO_CHOICES,
        default='descubierto',
        verbose_name='Estado del embudo'
    )
    puntaje_prioridad = models.FloatField(
        default=0,
        verbose_name='Puntaje de priorización',
        help_text='Score calculado para priorizar oportunidades en el radar.'
    )
    canal_origen = models.CharField(
        max_length=40,
        default='whatsapp',
        verbose_name='Canal origen'
    )
    metadata = models.JSONField(null=True, blank=True, help_text='Datos adicionales de misión (debug/contexto).')

    fecha_descubierta = models.DateTimeField(auto_now_add=True)
    fecha_reclamada = models.DateTimeField(null=True, blank=True)
    fecha_completada = models.DateTimeField(null=True, blank=True)
    fecha_interes = models.DateTimeField(null=True, blank=True)
    fecha_postulacion = models.DateTimeField(null=True, blank=True)
    fecha_entrevista = models.DateTimeField(null=True, blank=True)
    fecha_vinculacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Misión de Empleabilidad'
        verbose_name_plural = 'Misiones de Empleabilidad'
        ordering = ['-fecha_descubierta']
        indexes = [
            models.Index(fields=['estudiante', 'estado', 'fecha_descubierta']),
            models.Index(fields=['cliente', 'estado', 'fecha_descubierta']),
            models.Index(fields=['aliado', 'estado']),
            models.Index(fields=['cliente', 'estado_flujo', 'fecha_descubierta']),
        ]

    def __str__(self):
        return f"{self.estudiante.nombre} -> {self.aliado.nombre_empresa} ({self.get_estado_display()})"
