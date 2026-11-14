"""Marca el progreso del curso cuando el cierre real termina (post-Formador).

No usar al abrir el checkpoint Compañero/reto final: eso dejaba
completado=True antes del Formador y *continuar* respondía «Ya completaste»
(Maryuri / AgriCapital 2026-11-13).
"""
from __future__ import annotations


def marcar_progreso_curso_completado(progreso) -> None:
    """Idempotente. No-op si no hay fila de progreso o ya está completado."""
    if progreso is None or not getattr(progreso, 'id', None):
        return
    if getattr(progreso, 'completado', False):
        return
    from django.utils import timezone

    ahora = timezone.now()
    progreso.completado = True
    progreso.fecha_completado = ahora
    if hasattr(progreso, 'fecha_ultimo_avance'):
        progreso.fecha_ultimo_avance = ahora
        progreso.save(
            update_fields=['completado', 'fecha_completado', 'fecha_ultimo_avance']
        )
    else:
        progreso.save(update_fields=['completado', 'fecha_completado'])
