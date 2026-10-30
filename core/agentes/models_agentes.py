"""Conocimiento editable de los agentes de la línea Meta (Coach, Profe IA, Ventas).

Nat tiene su propia biblioteca (Knowledge Studio). Aquí solo entra lo que el
equipo aprueba; lo capturado de conversaciones queda «sugerido» hasta revisión.
"""
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import models

logger = logging.getLogger(__name__)

AGENTES = ('coach', 'ia_campo', 'ventas', 'finanzas', 'cafe')
_CACHE_KEY = 'conocimiento_agente:v2:{agente}:{cliente}'


def limpiar_cache_conocimiento(cliente_id=None) -> None:
    claves = [_CACHE_KEY.format(agente=a, cliente='0') for a in AGENTES]
    if cliente_id:
        claves.extend(_CACHE_KEY.format(agente=a, cliente=cliente_id) for a in AGENTES)
    try:
        cache.delete_many(claves)
    except Exception:
        logger.exception('conocimiento_cache_clear_fail')


class ConocimientoAgente(models.Model):
    AGENTE_TODOS = 'todos'
    AGENTE_CHOICES = [
        (AGENTE_TODOS, 'Todos (Coach, Profe IA, Ventas, Finanzas, Café)'),
        ('coach', 'Coach (Lina)'),
        ('ia_campo', 'Profe IA'),
        ('ventas', 'Ventas'),
        ('finanzas', 'Experto en finanzas'),
        ('cafe', 'Experto en café'),
    ]
    TIPO_CONOCIMIENTO = 'conocimiento'
    TIPO_INSTRUCCION = 'instruccion'
    TIPO_CHOICES = [
        (TIPO_CONOCIMIENTO, 'Dato o respuesta validada'),
        (TIPO_INSTRUCCION, 'Regla de comportamiento'),
    ]
    ESTADO_SUGERIDO = 'sugerido'
    ESTADO_APROBADO = 'aprobado'
    ESTADO_DESCARTADO = 'descartado'
    ESTADO_CHOICES = [
        (ESTADO_SUGERIDO, 'Sugerido (revisar)'),
        (ESTADO_APROBADO, 'Aprobado (lo usa el agente)'),
        (ESTADO_DESCARTADO, 'Descartado'),
    ]
    ORIGEN_MANUAL = 'manual'
    ORIGEN_CONVERSACION = 'conversacion'
    ORIGEN_CHOICES = [
        (ORIGEN_MANUAL, 'Equipo eki'),
        (ORIGEN_CONVERSACION, 'Capturado de conversación'),
    ]

    agente = models.CharField(max_length=16, choices=AGENTE_CHOICES, default=AGENTE_TODOS)
    tipo = models.CharField(max_length=16, choices=TIPO_CHOICES, default=TIPO_CONOCIMIENTO)
    titulo = models.CharField(max_length=160, verbose_name='Tema')
    contenido = models.TextField(
        verbose_name='Lo que debe saber o hacer el agente',
        help_text='Corto y concreto (máx. ~600 caracteres). Solo se usa si está Aprobado.',
    )
    estado = models.CharField(max_length=16, choices=ESTADO_CHOICES, default=ESTADO_APROBADO)
    origen = models.CharField(max_length=16, choices=ORIGEN_CHOICES, default=ORIGEN_MANUAL)
    pregunta_origen = models.TextField(blank=True, default='', verbose_name='Pregunta del usuario')
    respuesta_origen = models.TextField(blank=True, default='', verbose_name='Respuesta que dio el agente')
    orden = models.PositiveSmallIntegerField(default=0)
    ALCANCE_TODOS = 'todos'
    ALCANCE_CLIENTE = 'cliente'
    ALCANCE_CHOICES = [
        (ALCANCE_TODOS, 'Todos'),
        (ALCANCE_CLIENTE, 'Un cliente'),
    ]
    alcance = models.CharField(
        max_length=16,
        choices=ALCANCE_CHOICES,
        default=ALCANCE_TODOS,
        verbose_name='Alcance',
    )
    cliente = models.ForeignKey(
        'core.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conocimientos_agente',
        verbose_name='Cliente',
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Conocimiento de agente'
        verbose_name_plural = 'Entrenar agentes (Coach, Profe IA, Ventas)'
        ordering = ['orden', '-actualizado_en']
        indexes = [models.Index(fields=['agente', 'estado'])]

    def __str__(self):
        return f'{self.get_agente_display()} · {self.titulo}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        limpiar_cache_conocimiento(self.cliente_id)

    def delete(self, *args, **kwargs):
        resultado = super().delete(*args, **kwargs)
        limpiar_cache_conocimiento(self.cliente_id)
        return resultado


class PruebaAgente(models.Model):
    """Pregunta fija del laboratorio. No se envía por WhatsApp ni gasta cupo."""

    AGENTE_CHOICES = [
        ('coach', 'Coach eki'),
        ('ia_campo', 'Profesor IA'),
        ('ventas', 'Ventas eki'),
        ('finanzas', 'Experto en finanzas'),
        ('cafe', 'Experto en café'),
    ]
    RESULTADO_PASA = 'pasa'
    RESULTADO_REVISAR = 'revisar'

    agente = models.CharField(max_length=16, choices=AGENTE_CHOICES)
    pregunta = models.TextField()
    cliente = models.ForeignKey(
        'core.Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pruebas_agente',
    )
    plan = models.CharField(max_length=20, blank=True, default='')
    debe_mencionar = models.TextField(blank=True, default='')
    no_debe_mencionar = models.TextField(blank=True, default='')
    debe_usar_fuente = models.CharField(max_length=160, blank=True, default='')
    ultima_corrida = models.DateTimeField(null=True, blank=True)
    ultimo_resultado = models.CharField(max_length=16, blank=True, default='')
    corridas = models.PositiveIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Prueba de agente'
        verbose_name_plural = 'Pruebas de agente'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.get_agente_display()} · {self.pregunta[:60]}'
