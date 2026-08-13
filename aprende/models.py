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
    respuesta_estudiante = models.TextField(
        blank=True,
        help_text='Comentario del estudiante después de ver la calificación del profesor.',
    )
    fecha_respuesta_estudiante = models.DateTimeField(null=True, blank=True)
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


class AsistenciaAula(models.Model):
    """Registro de asistencia presencial por sesión (aula docente)."""

    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='asistencias_aula',
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='asistencias_aula',
    )
    fecha = models.DateField(verbose_name='Fecha de sesión')
    presente = models.BooleanField(default=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asistencias_registradas',
    )
    fecha_registro = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('curso', 'estudiante', 'fecha')]
        ordering = ['-fecha', 'estudiante__nombre']
        verbose_name = 'Asistencia (aula)'
        verbose_name_plural = 'Asistencias (aula)'

    def __str__(self):
        estado = 'presente' if self.presente else 'ausente'
        return f'{self.estudiante.nombre} — {self.curso.nombre} ({self.fecha}, {estado})'


class DocumentoEstudianteAula(models.Model):
    """Documento subido por el estudiante desde el aula (por curso o módulo)."""

    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='documentos_aula',
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='documentos_estudiantes_aula',
    )
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_estudiantes_aula',
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(upload_to='aprende/documentos/%Y/%m/')
    nombre_archivo = models.CharField(max_length=255, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Documento del estudiante (aula)'
        verbose_name_plural = 'Documentos del estudiante (aula)'

    def __str__(self):
        return f'{self.estudiante.nombre} — {self.titulo}'


class IntentoQuizModulo(models.Model):
    """Intento de práctica (quiz web) sobre PreguntaModulo del módulo."""

    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='intentos_quiz_aula',
    )
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.CASCADE,
        related_name='intentos_quiz_aula',
    )
    respuestas = models.JSONField(default=dict, blank=True)
    correctas = models.PositiveSmallIntegerField(default=0)
    total = models.PositiveSmallIntegerField(default=0)
    aprobado = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('estudiante', 'modulo')]
        ordering = ['-fecha']
        verbose_name = 'Intento quiz (aula)'
        verbose_name_plural = 'Intentos quiz (aula)'

    def __str__(self):
        return f'{self.estudiante_id} · módulo {self.modulo_id} · {self.correctas}/{self.total}'


class CodigoAccesoAprende(models.Model):
    """OTP de 6 dígitos emitido tras *aula* (compartido entre workers; no LocMem)."""

    codigo = models.CharField(max_length=6, unique=True, db_index=True)
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='codigos_acceso_aprende',
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Código acceso Aprende'
        verbose_name_plural = 'Códigos acceso Aprende'

    def __str__(self):
        return f'{self.codigo} → est={self.estudiante_id}'


class CredencialAprendeEstudiante(models.Model):
    """Contraseña del aula (hasheada). Alta/reset solo tras OTP de *aula*."""

    estudiante = models.OneToOneField(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='credencial_aprende',
    )
    password_hash = models.CharField(max_length=128)
    actualizado = models.DateTimeField(auto_now=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Credencial Aprende'
        verbose_name_plural = 'Credenciales Aprende'

    def __str__(self):
        return f'clave·est={self.estudiante_id}'

    def set_password(self, raw: str) -> None:
        from django.contrib.auth.hashers import make_password

        self.password_hash = make_password(raw)

    def check_password(self, raw: str) -> bool:
        from django.contrib.auth.hashers import check_password

        return check_password(raw or '', self.password_hash)
