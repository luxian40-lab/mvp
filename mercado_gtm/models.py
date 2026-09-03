from django.conf import settings
from django.db import models


class EscenarioMercado(models.Model):
    """Escenario TAM/SAM/SOM + GTM (multi-tenant, mismo patrón que calculadora_margen)."""

    ALCANCE_CHOICES = [
        ('local', 'Local'),
        ('departamental', 'Departamental'),
        ('nacional', 'Nacional'),
        ('exportacion', 'Exportación'),
    ]
    CONFIANZA_CHOICES = [
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escenarios_mercado',
    )
    cliente = models.ForeignKey(
        'core.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escenarios_mercado',
    )
    session_key = models.CharField(max_length=64, blank=True, default='', db_index=True)

    nombre_escenario = models.CharField(max_length=255, blank=True, default='')
    producto = models.CharField(max_length=200)
    categoria = models.CharField(max_length=120, blank=True, default='')
    presentacion = models.CharField(max_length=120, blank=True, default='')
    precio = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unidad_venta = models.CharField(max_length=40, default='unidad')

    ubicacion_actual = models.CharField(max_length=200, blank=True, default='')
    mercado_objetivo = models.CharField(max_length=200, blank=True, default='')
    alcance = models.CharField(max_length=20, choices=ALCANCE_CHOICES, default='local')

    segmentos_cliente = models.JSONField(default=list, blank=True)
    ticket_mensual_estimado = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    capacidad_mensual_maxima = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
    )

    tam = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    sam = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    som_conservador = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    som_base = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    som_ambicioso = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    confianza_estimacion = models.CharField(
        max_length=10, choices=CONFIANZA_CHOICES, default='media',
    )
    nota_confianza = models.TextField(blank=True, default='')
    trazabilidad = models.JSONField(default=dict, blank=True)
    gtm = models.JSONField(default=dict, blank=True)
    extraccion = models.JSONField(default=dict, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizado_en']
        verbose_name = 'Escenario de mercado'
        verbose_name_plural = 'Escenarios de mercado'

    def __str__(self) -> str:
        return self.nombre_escenario or f'{self.producto} ({self.creado_en:%Y-%m-%d})'
