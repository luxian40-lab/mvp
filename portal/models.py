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

    def __str__(self):
        return f"{self.user.username} - {self.organizacion.nombre} ({self.rol})"

    class Meta:
        verbose_name = 'Usuario portal clientes'
        verbose_name_plural = 'Usuarios portal clientes'
