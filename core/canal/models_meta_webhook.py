"""Cada inbound autenticado de Meta deja un evento. Retención 30 días."""
from __future__ import annotations

from django.db import models


class MetaWebhookEvento(models.Model):
    RESULTADO_CHOICES = [
        ('respondido', 'Respondido'),
        ('sin_plan', 'Sin plan'),
        ('ignorado_twilio', 'Twilio hacia la línea Meta'),
        ('ignorado', 'Ignorado'),
        ('error', 'Error'),
        ('tipo_no_soportado', 'Tipo no soportado'),
        ('recibido', 'Recibido'),
    ]

    wamid = models.CharField(max_length=255, unique=True)
    telefono = models.CharField(max_length=20, db_index=True)
    tipo = models.CharField(max_length=32, blank=True, default='')
    payload_raw = models.JSONField(default=dict, blank=True)
    firma_ok = models.BooleanField(default=True)
    recibido_en = models.DateTimeField(auto_now_add=True, db_index=True)
    procesado_en = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(
        max_length=32,
        choices=RESULTADO_CHOICES,
        blank=True,
        default='',
    )
    error = models.CharField(max_length=200, blank=True, default='')
    estado_chat_antes = models.CharField(max_length=50, blank=True, default='')
    plan_efectivo = models.CharField(max_length=40, blank=True, default='')

    class Meta:
        verbose_name = 'Evento webhook Meta'
        verbose_name_plural = 'Eventos webhook Meta'
        ordering = ['-recibido_en']

    def __str__(self):
        sufijo = (self.telefono or '')[-4:]
        return f'{self.tipo or "?"} · {sufijo} · {self.resultado or "recibido"}'
