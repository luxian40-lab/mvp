"""Conocimiento editable de los agentes de la línea Meta (Coach, Profe IA, Ventas).

Nat tiene su propia biblioteca (Knowledge Studio). Aquí solo entra lo que el
equipo aprueba; lo capturado de conversaciones queda «sugerido» hasta revisión.
"""
from django.conf import settings
from django.db import models


class ConocimientoAgente(models.Model):
    AGENTE_TODOS = 'todos'
    AGENTE_CHOICES = [
        (AGENTE_TODOS, 'Todos (Coach, Profe IA, Ventas)'),
        ('coach', 'Coach (Lina)'),
        ('ia_campo', 'Profe IA'),
        ('ventas', 'Ventas'),
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
        from core.conocimiento_agentes import limpiar_cache_conocimiento

        limpiar_cache_conocimiento()

    def delete(self, *args, **kwargs):
        resultado = super().delete(*args, **kwargs)
        from core.conocimiento_agentes import limpiar_cache_conocimiento

        limpiar_cache_conocimiento()
        return resultado
