"""Ledger de llamadas a modelos. No guarda el teléfono en claro."""
from decimal import Decimal

from django.db import models


class UsoLLM(models.Model):
    cliente = models.ForeignKey(
        'core.Cliente',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='usos_llm',
    )
    telefono_hash = models.CharField(max_length=64, blank=True, default='')
    agente = models.CharField(max_length=64, blank=True, default='')
    modelo = models.CharField(max_length=64)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    tokens_razonamiento = models.PositiveIntegerField(null=True, blank=True)
    costo_usd_est = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('0'))
    estimado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['cliente', 'creado'], name='uso_llm_cliente_creado'),
        ]
