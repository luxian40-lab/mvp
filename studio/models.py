"""Modelos eki Studio: cuentas web, creadores y pagos."""

from __future__ import annotations

import secrets

from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


class CuentaAula(models.Model):
    """
    Cuenta web (correo + contraseña) separada del flujo WhatsApp.
    Opcionalmente vinculada a core.Estudiante para progreso y gamificación.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cuenta_aula',
    )
    estudiante = models.OneToOneField(
        'core.Estudiante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuenta_aula',
    )
    nombre_visible = models.CharField(max_length=120, blank=True, default='')
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cuenta aula / Studio'
        verbose_name_plural = 'Cuentas aula / Studio'

    def __str__(self) -> str:
        return self.user.email or self.user.username

    @property
    def email(self) -> str:
        return self.user.email


class CreadorStudio(models.Model):
    """Instructor o experto que publica y monetiza cursos en Studio."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='creador_studio',
    )
    nombre_publico = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    bio = models.TextField(blank=True, default='')
    activo = models.BooleanField(
        default=False,
        help_text='Revisión eki antes de publicar en catálogo.',
    )
    wompi_recipient_id = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='ID de beneficiario Wompi para split de pagos (futuro).',
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Creador Studio'
        verbose_name_plural = 'Creadores Studio'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre_publico) or f'creador-{self.user_id or secrets.token_hex(4)}'
            slug = base
            n = 1
            while CreadorStudio.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nombre_publico


class PublicacionStudio(models.Model):
    """Configuración comercial de un curso en Studio."""

    curso = models.OneToOneField(
        'core.Curso',
        on_delete=models.CASCADE,
        related_name='publicacion_studio',
    )
    creador = models.ForeignKey(
        CreadorStudio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publicaciones',
    )
    precio_cop = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text='0 = gratuito. Monto en pesos colombianos.',
    )
    destacado = models.BooleanField(default=False)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Publicación Studio'
        verbose_name_plural = 'Publicaciones Studio'

    def __str__(self) -> str:
        return f'{self.curso.nombre} ({self.precio_cop} COP)'

    @property
    def es_gratis(self) -> bool:
        return self.precio_cop <= 0


class AccesoCursoPagado(models.Model):
    """Registro de pago Wompi (o gratuito) para acceder a un curso."""

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_APROBADO = 'aprobado'
    ESTADO_RECHAZADO = 'rechazado'
    ESTADO_EXPIRADO = 'expirado'

    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_APROBADO, 'Aprobado'),
        (ESTADO_RECHAZADO, 'Rechazado'),
        (ESTADO_EXPIRADO, 'Expirado'),
    ]

    cuenta = models.ForeignKey(
        CuentaAula,
        on_delete=models.CASCADE,
        related_name='accesos_curso',
    )
    curso = models.ForeignKey(
        'core.Curso',
        on_delete=models.CASCADE,
        related_name='accesos_pagados',
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    monto_cop = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    wompi_referencia = models.CharField(max_length=64, unique=True, db_index=True)
    wompi_transaccion_id = models.CharField(max_length=120, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    pagado_en = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Acceso curso pagado'
        verbose_name_plural = 'Accesos curso pagados'
        indexes = [
            models.Index(fields=['cuenta', 'curso', 'estado']),
        ]

    def __str__(self) -> str:
        return f'{self.cuenta.email} → {self.curso.nombre} ({self.estado})'
