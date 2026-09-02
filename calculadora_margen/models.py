from django.conf import settings
from django.db import models


class CalculoMargen(models.Model):
    """Registro de un cálculo de margen (MVP público eki)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calculos_margen',
    )
    cliente = models.ForeignKey(
        'core.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calculos_margen',
    )

    producto = models.CharField(max_length=200)
    cantidad_producida = models.DecimalField(max_digits=14, decimal_places=4)
    unidad = models.CharField(max_length=40, default='unidades')

    materias_primas = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    mano_obra = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    transporte = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    empaque = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    otros_costos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    costos_fijos = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    precio_actual = models.DecimalField(max_digits=14, decimal_places=2)

    costo_unitario = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    margen_actual = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    precio_sugerido_25 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    recomendaciones = models.JSONField(default=dict, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Cálculo de margen'
        verbose_name_plural = 'Cálculos de margen'

    def __str__(self) -> str:
        return f'{self.producto} ({self.creado_en:%Y-%m-%d})'


class MargenUsoEvento(models.Model):
    """Evento agregado de uso (sin montos ni PII del negocio)."""

    EVENTO_CHOICES = [
        ('apertura', 'Apertura'),
        ('inicio_wizard', 'Inicio wizard'),
        ('calculo_ok', 'Cálculo completado'),
        ('resultado_visto', 'Resultado visto'),
        ('simulo_precio', 'Simuló precio'),
        ('recomendaciones_ok', 'Recomendaciones IA'),
    ]

    cliente = models.ForeignKey(
        'core.Cliente',
        on_delete=models.CASCADE,
        related_name='margen_eventos',
    )
    curso_id = models.PositiveIntegerField(null=True, blank=True)
    session_key = models.CharField(max_length=64, db_index=True)
    evento = models.CharField(max_length=32, choices=EVENTO_CHOICES, db_index=True)
    margen_rango = models.CharField(max_length=20, blank=True, default='')
    meta = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Evento calculadora margen'
        verbose_name_plural = 'Eventos calculadora margen'
        indexes = [
            models.Index(fields=['cliente', 'evento', 'creado_en']),
        ]

    def __str__(self) -> str:
        return f'{self.cliente_id} · {self.evento} ({self.creado_en:%Y-%m-%d %H:%M})'


class MargenEnlaceCliente(models.Model):
    """Link público único por organización (?org=slug o ?t=token)."""

    cliente = models.OneToOneField(
        'core.Cliente',
        on_delete=models.CASCADE,
        related_name='margen_enlace',
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text='Segmento legible para ?org= (ej. cooperativa-valle)',
    )
    token = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text='Token opaco para ?t= (compartir sin revelar nombre)',
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Enlace calculadora margen'
        verbose_name_plural = 'Enlaces calculadora margen'

    def __str__(self) -> str:
        return f'{self.slug} (cliente {self.cliente_id})'
