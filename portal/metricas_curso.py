"""Métricas por curso del portal: inicio, culminación y avance.

Inscrito = fila de ProgresoEstudiante (aceptó el curso).
Inició = recibió al menos un paso, cerró un módulo o terminó el curso.
Terminó = progreso completado.
Avance = módulos cerrados / módulos publicados; un curso terminado cuenta 100.
Los totales se cuentan por inscripción (persona y curso), así suman lo mismo que la tabla.
"""
from __future__ import annotations

from django.db.models import Q

from core.lineas.modelo import LineaWhatsapp
from core.modulo_publicacion import modulos_publicados_wa_qs
from core.models import Curso, ModuloCompletado, ProgresoEstudiante


def _pct(num: int, den: int):
    if not den:
        return None
    return round(num * 100 / den, 1)


def _fila(inscritos: int, iniciaron: int, terminaron: int, suma_avance: int) -> dict:
    return {
        'inscritos': inscritos,
        'iniciaron': iniciaron,
        'terminaron': terminaron,
        'inicio_pct': _pct(iniciaron, inscritos),
        'culminacion_iniciados_pct': _pct(terminaron, iniciaron),
        'culminacion_inscritos_pct': _pct(terminaron, inscritos),
        'avance_pct': round(suma_avance / inscritos, 1) if inscritos else None,
    }


def metricas_cursos(org) -> dict:
    """Totales, una fila por curso y los cursos agrupados por línea de WhatsApp."""
    progresos = list(
        ProgresoEstudiante.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
        ).values_list('id', 'curso_id', 'completado', 'paso_actual_modulo')
    )
    ids_curso = {curso_id for _, curso_id, _, _ in progresos}
    cursos = list(
        Curso.objects.filter(Q(id__in=ids_curso) | Q(cliente=org, activo=True))
        .order_by('orden', 'nombre')
    )

    publicados = {
        curso.id: set(modulos_publicados_wa_qs(curso).values_list('id', flat=True))
        for curso in cursos
    }
    cerrados: dict[int, set[int]] = {}
    for progreso_id, modulo_id in ModuloCompletado.objects.filter(
        progreso__estudiante__cliente=org,
        progreso__estudiante__activo=True,
    ).values_list('progreso_id', 'modulo_id'):
        cerrados.setdefault(progreso_id, set()).add(modulo_id)

    acumulado: dict[int, list[int]] = {curso.id: [0, 0, 0, 0] for curso in cursos}
    for progreso_id, curso_id, completado, paso in progresos:
        modulos = cerrados.get(progreso_id, set())
        inicio = completado or (paso or 1) > 1 or bool(modulos)
        total_modulos = len(publicados[curso_id])
        if completado:
            avance = 100
        elif total_modulos:
            avance = min(100, int(len(modulos & publicados[curso_id]) * 100 / total_modulos))
        else:
            avance = 0
        fila = acumulado[curso_id]
        fila[0] += 1
        fila[1] += int(inicio)
        fila[2] += int(completado)
        fila[3] += avance

    por_curso = []
    for curso in cursos:
        datos = _fila(*acumulado[curso.id])
        datos['id'] = curso.id
        datos['nombre'] = curso.nombre
        datos['general'] = curso.cliente_id is None
        por_curso.append(datos)

    total = _fila(*(sum(fila[i] for fila in acumulado.values()) for i in range(4)))

    filas_por_id = {fila['id']: fila for fila in por_curso}
    lineas = []
    con_linea: set[int] = set()
    for linea in (
        LineaWhatsapp.objects.filter(
            Q(cliente__isnull=True) | Q(cliente=org),
            activo=True,
            cursos__in=list(filas_por_id),
        )
        .distinct()
        .order_by('orden', 'id')
    ):
        ids = [
            curso_id
            for curso_id in linea.cursos.order_by('orden', 'nombre').values_list('id', flat=True)
            if curso_id in filas_por_id
        ]
        con_linea.update(ids)
        lineas.append({'nombre': linea.nombre, 'cursos': [filas_por_id[i] for i in ids]})
    sueltos = [fila for fila in por_curso if fila['id'] not in con_linea]
    if sueltos:
        lineas.append({'nombre': 'Sin línea asignada', 'cursos': sueltos})

    return {'total': total, 'por_curso': por_curso, 'lineas': lineas}
