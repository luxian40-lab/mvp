"""Modelos de pregunta final (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models.estudiantes import Estudiante
from core.models.cursos import Curso
from core.models.modulos import ProgresoEstudiante


class PreguntaAbiertaFinalCurso(models.Model):
    """Pregunta abierta opcional al final del curso, evaluada por facilitadora."""
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='preguntas_abiertas_finales'
    )
    orden = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Orden',
        help_text='Orden de la pregunta en el cierre (1 a 3).'
    )
    pregunta = models.TextField(verbose_name='Pregunta abierta final')
    activa = models.BooleanField(default=True, verbose_name='Activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pregunta Abierta Final'
        verbose_name_plural = 'Preguntas Abiertas Finales'
        ordering = ['curso', 'orden', 'id']
        unique_together = ['curso', 'orden']

    def __str__(self):
        return f"Pregunta final #{self.orden} - {self.curso.nombre}"

    def clean(self):
        super().clean()
        if self.orden < 1 or self.orden > 3:
            raise ValidationError({'orden': 'El orden debe estar entre 1 y 3.'})

        existentes = PreguntaAbiertaFinalCurso.objects.filter(curso=self.curso)
        if self.pk:
            existentes = existentes.exclude(pk=self.pk)
        if existentes.count() >= 3:
            raise ValidationError('Cada curso permite máximo 3 preguntas abiertas finales.')


class RespuestaAbiertaFinal(models.Model):
    """Respuesta del estudiante a la pregunta abierta final (calificada por facilitadora)."""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de calificar'),
        ('calificada', 'Calificada'),
    ]

    pregunta = models.ForeignKey(
        PreguntaAbiertaFinalCurso,
        on_delete=models.CASCADE,
        related_name='respuestas'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='respuestas_abiertas_finales'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='respuestas_abiertas_finales'
    )
    progreso = models.ForeignKey(
        ProgresoEstudiante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_abiertas_finales'
    )
    respuesta_texto = models.TextField(verbose_name='Respuesta del estudiante')
    fecha_respuesta = models.DateTimeField(default=timezone.now)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    calificacion = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Calificación (0-100)'
    )
    retroalimentacion = models.TextField(blank=True, default='', verbose_name='Retroalimentación facilitadora')
    calificada_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calificaciones_preguntas_abiertas'
    )
    fecha_calificacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Respuesta Abierta Final'
        verbose_name_plural = 'Respuestas Abiertas Finales'
        ordering = ['-fecha_respuesta']
        unique_together = ['pregunta', 'estudiante']

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.curso.nombre}"
