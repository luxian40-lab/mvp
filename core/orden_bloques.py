"""Intercambiar orden de bloques de módulo (secciones, pasos, multimedia).

Usado por botones ↑↓ en el admin Unfold. No toca S3 ni envío WhatsApp.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Max


def _siblings_qs(model, obj):
    """Hermanos del mismo módulo, ordenados por orden/id."""
    return model.objects.filter(modulo_id=obj.modulo_id).order_by('orden', 'id')


def intercambiar_orden(obj, direction: str) -> bool:
    """
    Mueve obj arriba ('up') o abajo ('down') intercambiando `orden` con el vecino.
    Respeta UniqueConstraint (modulo, orden) con un valor temporal.
    Retorna True si hubo cambio.
    """
    if direction not in ('up', 'down') or not obj or not obj.pk:
        return False

    model = obj.__class__
    siblings = list(_siblings_qs(model, obj))
    try:
        idx = next(i for i, s in enumerate(siblings) if s.pk == obj.pk)
    except StopIteration:
        return False

    target_idx = idx - 1 if direction == 'up' else idx + 1
    if target_idx < 0 or target_idx >= len(siblings):
        return False

    other = siblings[target_idx]
    if other.pk == obj.pk:
        return False

    a_orden = obj.orden
    b_orden = other.orden
    if a_orden == b_orden:
        # Normalizar: asignar índices 1..n y reintentar vecino por posición
        with transaction.atomic():
            for i, s in enumerate(siblings, start=1):
                if s.orden != i:
                    model.objects.filter(pk=s.pk).update(orden=i)
            obj.refresh_from_db()
            siblings = list(_siblings_qs(model, obj))
            idx = next(i for i, s in enumerate(siblings) if s.pk == obj.pk)
            target_idx = idx - 1 if direction == 'up' else idx + 1
            if target_idx < 0 or target_idx >= len(siblings):
                return False
            other = siblings[target_idx]
            a_orden = obj.orden
            b_orden = other.orden

    with transaction.atomic():
        max_orden = (
            _siblings_qs(model, obj).aggregate(m=Max('orden')).get('m') or 0
        )
        temp = max_orden + 1000
        model.objects.filter(pk=obj.pk).update(orden=temp)
        model.objects.filter(pk=other.pk).update(orden=a_orden)
        model.objects.filter(pk=obj.pk).update(orden=b_orden)
    return True
