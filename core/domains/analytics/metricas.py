"""Facade Analytics — reexporta cálculo de métricas desde módulo legacy."""

from core.metricas_empresa import (
    calcular_metricas_empresa,
    calcular_metricas_nati,
    calcular_semaforo,
    semaforo_label,
)

__all__ = [
    'calcular_metricas_empresa',
    'calcular_metricas_nati',
    'calcular_semaforo',
    'semaforo_label',
]
