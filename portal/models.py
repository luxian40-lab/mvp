from django.db import models
from django.contrib.auth.models import User
from core.models import Cliente


class PortalUsuario(models.Model):
    ROL_CHOICES = [
        ('admin', 'Administrador (portal clientes)'),
        ('profesor', 'Profesor (solo aula web /aprende/)'),
        ('viewer', 'Solo lectura (portal clientes)'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='portal_usuario',
    )
    organizacion = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='usuarios_portal',
    )
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='viewer')
    debe_cambiar_credenciales = models.BooleanField(
        default=False,
        verbose_name='Debe cambiar nombre y contraseña',
        help_text='Si está activo, al entrar al portal debe definir nombre y contraseña nueva.',
    )
    password_temporal = models.CharField(
        max_length=128,
        blank=True,
        default='',
        verbose_name='Contraseña temporal (visible)',
        help_text=(
            'Solo para entrega al cliente. Se borra cuando el usuario completa el primer acceso. '
            'No es un hash: úsala solo como referencia operativa.'
        ),
    )

    def __str__(self):
        return f"{self.user.username} - {self.organizacion.nombre} ({self.rol})"

    class Meta:
        verbose_name = 'Usuario portal clientes'
        verbose_name_plural = 'Usuarios portal clientes'


class PortalFeedback(models.Model):
    """Comentarios de usuarios del portal hacia el equipo eki."""

    CATEGORIA_CHOICES = [
        ('bug', 'Problema / error'),
        ('mejora', 'Sugerencia de mejora'),
        ('pregunta', 'Pregunta'),
        ('otro', 'Otro'),
    ]

    organizacion = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='feedbacks_portal',
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='mejora')
    mensaje = models.TextField()
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Feedback portal'
        verbose_name_plural = 'Feedbacks portal'

    def __str__(self):
        return f'Feedback {self.organizacion.nombre} ({self.categoria})'


class PortalSugerenciaIA(models.Model):
    """Preguntas sugeridas para la facilitadora IA (cursos / GEI)."""

    AMBITO_CHOICES = [
        ('curso', 'Curso / facilitadora'),
        ('gei', 'Inventario GEI'),
    ]

    organizacion = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='sugerencias_ia_portal',
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    ambito = models.CharField(max_length=10, choices=AMBITO_CHOICES)
    curso = models.ForeignKey(
        'core.Curso',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    pregunta = models.TextField(help_text='Pregunta o tema que la IA debería saber responder.')
    notas = models.TextField(blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Sugerencia IA portal'
        verbose_name_plural = 'Sugerencias IA portal'
