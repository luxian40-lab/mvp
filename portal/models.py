from django.db import models
from django.contrib.auth.models import User
from core.models import Cliente


class PortalUsuario(models.Model):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('viewer', 'Solo lectura'),
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
        verbose_name = "Usuario del Portal"
        verbose_name_plural = "Usuarios del Portal"
