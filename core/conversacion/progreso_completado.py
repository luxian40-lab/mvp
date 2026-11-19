"""Único escritor de producto para cerrar ``ProgresoEstudiante.completado``.

Corte 2 del expediente (``docs/PLAN_EXPEDIENTE_APRENDIZAJE_EKI.md``).
Corte 4: ``origen`` distingue chat / operación / presencial sin redefinir
el KPI ``completado``.

No usar al abrir el checkpoint Compañero/reto final: eso dejaba
completado=True antes del Formador y *continuar* respondía «Ya completaste»
(Maryuri / AgriCapital 2026-11-13).

``con_fecha=False`` conserva el camino del selector de curso (completado sin
fecha → el signal de diploma no dispara), caracterizado en corte 1.
"""
from __future__ import annotations

ORIGEN_CHAT = 'chat'
ORIGEN_OPERACION = 'operacion'
ORIGEN_PRESENCIAL = 'presencial'


def marcar_progreso_curso_completado(
    progreso,
    *,
    con_fecha: bool = True,
    origen: str | None = ORIGEN_CHAT,
    extra_update_fields: list[str] | None = None,
) -> None:
    """Idempotente. No-op si no hay fila de progreso o ya está completado."""
    if progreso is None or not getattr(progreso, 'id', None):
        return
    if getattr(progreso, 'completado', False):
        return

    progreso.completado = True
    fields: list[str] = ['completado']

    if con_fecha:
        from django.utils import timezone

        ahora = timezone.now()
        progreso.fecha_completado = ahora
        fields.append('fecha_completado')
        if hasattr(progreso, 'fecha_ultimo_avance'):
            progreso.fecha_ultimo_avance = ahora
            fields.append('fecha_ultimo_avance')

    if origen and hasattr(progreso, 'origen_cierre'):
        progreso.origen_cierre = origen
        if 'origen_cierre' not in fields:
            fields.append('origen_cierre')

    if extra_update_fields:
        for nombre in extra_update_fields:
            if nombre and nombre not in fields:
                fields.append(nombre)

    progreso.save(update_fields=fields)
