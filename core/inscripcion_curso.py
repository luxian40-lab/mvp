"""Inscripción de estudiante a curso con defaults seguros para Aprende."""

from __future__ import annotations

from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante


def primer_modulo_curso(curso: Curso) -> Modulo | None:
    return (
        Modulo.objects.filter(curso=curso)
        .order_by('numero', 'id')
        .first()
    )


def defaults_progreso_nuevo(curso: Curso) -> dict:
    """Defaults al crear ProgresoEstudiante (sin campo inventado `progreso`)."""
    defaults = {'completado': False}
    m1 = primer_modulo_curso(curso)
    if m1 is not None:
        defaults['modulo_actual'] = m1
    return defaults


def inscribir_estudiante_en_curso(
    estudiante: Estudiante,
    curso: Curso,
    *,
    asegurar_modulo_actual: bool = True,
) -> tuple[ProgresoEstudiante, bool]:
    """
    get_or_create de progreso. Si se crea, asigna modulo_actual = 1er módulo.
    Si ya existía y asegurar_modulo_actual y no tiene módulo, lo completa.
    """
    progreso, creado = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso,
        defaults=defaults_progreso_nuevo(curso),
    )
    if (
        asegurar_modulo_actual
        and not creado
        and progreso.modulo_actual_id is None
        and not progreso.completado
    ):
        m1 = primer_modulo_curso(curso)
        if m1 is not None:
            progreso.modulo_actual = m1
            progreso.save(update_fields=['modulo_actual'])
    return progreso, creado
