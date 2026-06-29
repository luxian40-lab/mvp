"""Tareas del estudiante en el aula (entregas calificadas por el docente)."""

from __future__ import annotations

from core.models import Curso, Estudiante, ProgresoEstudiante

from .acceso_modulos import tareas_visibles_aula
from .models import EntregaTarea, TareaCurso


def tareas_por_curso(estudiante: Estudiante, curso: Curso) -> list[dict]:
    progreso = ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso).first()
    if not progreso:
        return []
    tareas = tareas_visibles_aula(estudiante, curso, progreso)
    entregas = {
        e.tarea_id: e
        for e in EntregaTarea.objects.filter(estudiante=estudiante, tarea__curso=curso)
    }
    return [{'tarea': t, 'entrega': entregas.get(t.pk)} for t in tareas]


def tareas_agrupadas_estudiante(estudiante: Estudiante) -> list[dict]:
    """Todas las tareas visibles, agrupadas por curso inscrito."""
    progresos = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, curso__activo=True)
        .select_related('curso')
        .order_by('curso__nombre')
    )
    secciones: list[dict] = []
    for prog in progresos:
        items = tareas_por_curso(estudiante, prog.curso)
        if items:
            secciones.append({'curso': prog.curso, 'tareas_list': items})
    return secciones


def total_tareas_pendientes(estudiante: Estudiante) -> int:
    n = 0
    for sec in tareas_agrupadas_estudiante(estudiante):
        for item in sec['tareas_list']:
            entrega = item.get('entrega')
            if not entrega or entrega.nota is None:
                n += 1
    return n
