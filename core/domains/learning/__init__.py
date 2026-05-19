"""Dominio Learning — progreso, drip y checkpoints de reto IA."""

from core.domains.learning.checkpoints import (
    CheckpointDecision,
    debe_activar_checkpoint_reto_ia,
    es_modulo_checkpoint_reto_ia,
    evaluar_checkpoint_reto_ia,
)

__all__ = [
    'debe_activar_checkpoint_reto_ia',
    'es_modulo_checkpoint_reto_ia',
    'evaluar_checkpoint_reto_ia',
    'CheckpointDecision',
]
