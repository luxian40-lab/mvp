"""Modelo de estado de entrega de media (paquete recuperable)."""
from django.db import models


class MediaPaqueteEntrega(models.Model):
    """
    Unidad recuperable: un adjunto de curso enviado por WhatsApp.
    Estados: pendiente → enviado → fallido → recuperado (auto-reintento o reenvía video).
    """

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ENVIADO = 'enviado'
    ESTADO_FALLIDO = 'fallido'
    ESTADO_RECUPERADO = 'recuperado'
    ESTADOS = (
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_ENVIADO, 'Enviado'),
        (ESTADO_FALLIDO, 'Fallido'),
        (ESTADO_RECUPERADO, 'Recuperado'),
    )

    estudiante = models.ForeignKey(
        'core.Estudiante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paquetes_media',
    )
    telefono = models.CharField(max_length=30, db_index=True)
    curso = models.ForeignKey(
        'core.Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paquetes_media',
    )
    modulo = models.ForeignKey(
        'core.Modulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paquetes_media',
    )
    whatsapp_log = models.ForeignKey(
        'core.WhatsappLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paquetes_media',
    )
    media_url = models.TextField(blank=True, default='')
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_ENVIADO,
        db_index=True,
    )
    intentos = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=20, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paquete media WhatsApp'
        verbose_name_plural = 'Paquetes media WhatsApp'
        ordering = ['-actualizado_en']
        indexes = [
            models.Index(fields=['telefono', 'estado']),
            models.Index(fields=['estado', '-actualizado_en']),
        ]

    def __str__(self):
        return f'{self.telefono} [{self.estado}] intentos={self.intentos}'
