"""Enlaces cortos de video (WhatsApp) y eventos de apertura / progreso.

No reutiliza MargenEnlaceCliente (enlace público de la calculadora) ni
EnlaceFormularioExterno (webhook de Google Form): esos tokens no identifican
un video ni un estudiante.
"""
from django.db import models


class VideoEnlace(models.Model):
    """Token opaco por estudiante + video. La URL pública no lleva PII."""

    DESTINO_S3 = 's3'
    DESTINO_ARCHIVO = 'archivo'
    DESTINO_EXTERNO = 'externo'
    DESTINOS = [
        (DESTINO_S3, 'S3 (URL firmada al abrir)'),
        (DESTINO_ARCHIVO, 'Archivo directo (reproductor propio)'),
        (DESTINO_EXTERNO, 'YouTube o Vimeo (redirect)'),
    ]

    token = models.CharField(max_length=40, unique=True, db_index=True)
    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.CASCADE,
        related_name='enlaces_video',
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='enlaces_video',
    )
    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enlaces_video',
    )
    video_id = models.CharField(max_length=64, db_index=True)
    etiqueta = models.CharField(max_length=200, blank=True, default='')
    destino_tipo = models.CharField(max_length=16, choices=DESTINOS)
    destino_ref = models.TextField(
        help_text='Key S3 o URL de YouTube/Vimeo/archivo. Nunca una URL ya firmada.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Enlace de video'
        verbose_name_plural = 'Enlaces de video'
        constraints = [
            models.UniqueConstraint(
                fields=['estudiante', 'video_id'],
                name='uniq_video_enlace_estudiante_video',
            ),
        ]

    def __str__(self):
        return f'{self.video_id} · est={self.estudiante_id}'


class VideoView(models.Model):
    """Apertura del enlace o hito de progreso del reproductor propio."""

    EVENTO_APERTURA = 'apertura'
    EVENTO_P25 = 'progreso_25'
    EVENTO_P50 = 'progreso_50'
    EVENTO_P75 = 'progreso_75'
    EVENTO_P100 = 'progreso_100'
    EVENTOS = [
        (EVENTO_APERTURA, 'Apertura del enlace'),
        (EVENTO_P25, 'Progreso 25%'),
        (EVENTO_P50, 'Progreso 50%'),
        (EVENTO_P75, 'Progreso 75%'),
        (EVENTO_P100, 'Progreso 100%'),
    ]

    enlace = models.ForeignKey(
        VideoEnlace,
        on_delete=models.CASCADE,
        related_name='vistas',
    )
    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.CASCADE,
        related_name='vistas_video',
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='vistas_video',
    )
    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vistas_video',
    )
    video_id = models.CharField(max_length=64, db_index=True)
    evento = models.CharField(max_length=20, choices=EVENTOS, db_index=True)
    user_agent = models.CharField(max_length=400, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Vista de video'
        verbose_name_plural = 'Vistas de video'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['curso', 'evento', 'creado_en']),
            models.Index(fields=['estudiante', 'video_id', 'evento']),
            models.Index(fields=['enlace', 'evento']),
        ]

    def __str__(self):
        return f'{self.evento} · {self.video_id} · est={self.estudiante_id}'
