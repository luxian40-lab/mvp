"""
Facade del dominio Learning para reglas de checkpoint / reto IA.

Fuente de verdad sigue en ``core.curso.helpers_examenes`` hasta completar migración.
"""

from core.curso.helpers_examenes import (
    debe_activar_checkpoint_reto_ia,
    es_modulo_checkpoint_reto_ia,
    evaluar_checkpoint_reto_ia,
    CheckpointDecision,
)

__all__ = [
    'debe_activar_checkpoint_reto_ia',
    'es_modulo_checkpoint_reto_ia',
    'evaluar_checkpoint_reto_ia',
    'CheckpointDecision',
]
