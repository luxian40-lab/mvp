"""Métricas por curso del portal: inicio, culminación y avance.

Inscrito = fila de ProgresoEstudiante (aceptó el curso).
Inició = recibió al menos un paso, cerró un módulo o terminó el curso.
Terminó = progreso completado.
Avance = módulos cerrados / módulos publicados; un curso terminado cuenta 100.
Los totales se cuentan por inscripción (persona y curso), así suman lo mismo que la tabla.
"""
from __future__ import annotations

from django.db.models import Count, Q

from core.lineas.modelo import LineaWhatsapp
from core.modulo_publicacion import modulos_publicados_wa_qs
from core.models import Curso, ModuloCompletado, NotaCierreCurso, ProgresoEstudiante


def _pct(num: int, den: int):
    if not den:
        return None
    return round(num * 100 / den, 1)


MIN_INICIADORES_CULMINACION = 5


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


def _recorte(fila):
    if not fila:
        return None
    return {
        'id': fila['id'],
        'nombre': fila['nombre'],
        'iniciaron': fila['iniciaron'],
        'terminaron': fila['terminaron'],
        'culminacion_iniciados_pct': fila['culminacion_iniciados_pct'],
    }


def _destacados(por_curso: list[dict]) -> dict:
    """Curso con más inicios, y el de mayor culminación sobre iniciadores.

    La culminación solo entra si el curso tiene al menos cinco iniciadores:
    un 1 de 1 no gana la caja.
    """
    con_inicio = [fila for fila in por_curso if fila['iniciaron']]
    mas_inicios = None
    if con_inicio:
        mas_inicios = sorted(
            con_inicio,
            key=lambda fila: (-fila['iniciaron'], -fila['inscritos'], fila['nombre']),
        )[0]
    elegibles = [fila for fila in por_curso if fila['iniciaron'] >= MIN_INICIADORES_CULMINACION]
    mayor = None
    if elegibles:
        mayor = sorted(
            elegibles,
            key=lambda fila: (
                -(fila['culminacion_iniciados_pct'] or 0),
                -fila['iniciaron'],
                fila['nombre'],
            ),
        )[0]
    return {
        'mas_inicios': _recorte(mas_inicios),
        'mayor_culminacion': _recorte(mayor),
        'min_iniciadores': MIN_INICIADORES_CULMINACION,
    }


def metricas_cursos(org) -> dict:
    """Totales, una fila por curso y los cursos agrupados por línea de WhatsApp."""
    progresos = list(
        ProgresoEstudiante.objects.filter(
            estudiante__cliente=org,
            estudiante__activo=True,
        ).values_list('id', 'estudiante_id', 'curso_id', 'completado', 'paso_actual_modulo')
    )
    ids_curso = {curso_id for _, _, curso_id, _, _ in progresos}
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
    cursos_iniciados: dict[int, set[int]] = {}
    for progreso_id, estudiante_id, curso_id, completado, paso in progresos:
        modulos = cerrados.get(progreso_id, set())
        inicio = completado or (paso or 1) > 1 or bool(modulos)
        if inicio:
            cursos_iniciados.setdefault(estudiante_id, set()).add(curso_id)
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
    base_segundo = len(cursos_iniciados)
    con_segundo = sum(1 for cursos_de_persona in cursos_iniciados.values() if len(cursos_de_persona) >= 2)

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

    return {
        'total': total,
        'por_curso': por_curso,
        'lineas': lineas,
        'segundo_curso': {
            'pct': _pct(con_segundo, base_segundo),
            'n': con_segundo,
            'base': base_segundo,
        },
        'destacados': _destacados(por_curso),
        'nota_cierre': _nota_cierre(org),
    }


def _nota_cierre(org) -> dict:
    """NPS de la nota 1 a 10 guardada al cerrar el curso.

    Promotores 9–10, pasivos 7–8, detractores 1–6.
    NPS = porcentaje de promotores menos porcentaje de detractores.
    """
    fila = NotaCierreCurso.objects.filter(
        estudiante__cliente=org,
        estudiante__activo=True,
    ).aggregate(
        n=Count('id'),
        promotores=Count('id', filter=Q(nota__gte=9)),
        detractores=Count('id', filter=Q(nota__lte=6)),
    )
    n = fila['n'] or 0
    if not n:
        return {'n': 0, 'nps': None}
    return {
        'n': n,
        'nps': round((fila['promotores'] - fila['detractores']) * 100 / n),
    }
