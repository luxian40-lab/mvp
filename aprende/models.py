"""Modelos del aula web: tareas y entregas (estilo Moodle)."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import Curso, Estudiante, Modulo


class TareaCurso(models.Model):
    """Tarea asignada por el profesor dentro de un curso."""

    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='tareas_aula',
    )
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tareas_aula',
        help_text='Opcional: vincular la tarea a una lección específica.',
    )
    titulo = models.CharField(max_length=200)
    instrucciones = models.TextField(blank=True)
    fecha_limite = models.DateTimeField(null=True, blank=True)
    activa = models.BooleanField(default=True)
    orden = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', '-fecha_creacion']
        verbose_name = 'Tarea del curso'
        verbose_name_plural = 'Tareas del curso'

    def __str__(self):
        return f'{self.curso.nombre} — {self.titulo}'


class EntregaTarea(models.Model):
    """Entrega de un estudiante a una tarea."""

    tarea = models.ForeignKey(
        TareaCurso,
        on_delete=models.CASCADE,
        related_name='entregas',
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='entregas_tareas',
    )
    archivo = models.FileField(upload_to='aprende/entregas/%Y/%m/')
    nombre_archivo = models.CharField(max_length=255, blank=True)
    comentario_estudiante = models.TextField(blank=True)
    fecha_entrega = models.DateTimeField(auto_now=True)
    nota = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Calificación del profesor (1 a 5).',
    )
    comentario_profesor = models.TextField(blank=True)
    fecha_calificacion = models.DateTimeField(null=True, blank=True)
    calificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregas_calificadas',
    )

    class Meta:
        unique_together = [('tarea', 'estudiante')]
        ordering = ['-fecha_entrega']
        verbose_name = 'Entrega de tarea'
        verbose_name_plural = 'Entregas de tareas'

    def __str__(self):
        return f'{self.estudiante.nombre} — {self.tarea.titulo}'

    @property
    def calificada(self) -> bool:
        return self.nota is not None
