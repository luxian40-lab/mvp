"""Métricas por curso del portal: inicio, culminación y avance.

Inscrito = fila de ProgresoEstudiante (aceptó el curso).
Inició = empezó el módulo inicial: fecha_ultimo_avance, cerró un módulo o terminó.
No basta con paso_actual_modulo > 1: el primer envío mueve el puntero
sin que la persona haya avanzado.
Terminó = progreso completado.
Avance promedio = módulo promedio alcanzado (número), no porcentaje.
Los totales se cuentan por inscripción (persona y curso), así suman lo mismo que la tabla.
"""
from __future__ import annotations

from django.db.models import Q

from core.analitica.nps_cierre import nps_nota_cierre
from core.lineas.modelo import LineaWhatsapp
from core.modulo_publicacion import modulos_publicados_wa_qs
from core.models import Curso, ModuloCompletado, ProgresoEstudiante
from portal.analitica_universo import ids_estudiantes_analitica


def _pct(num: int, den: int):
    if not den:
        return None
    return round(num * 100 / den, 1)


MIN_INICIADORES_CULMINACION = 5


def _fila(
    inscritos: int,
    iniciaron: int,
    terminaron: int,
    suma_modulos: float,
    suma_avance_pct: int,
) -> dict:
    avance_modulo = round(suma_modulos / inscritos, 1) if inscritos else None
    avance_pct = round(suma_avance_pct / inscritos, 1) if inscritos else None
    return {
        'inscritos': inscritos,
        'iniciaron': iniciaron,
        'terminaron': terminaron,
        'inicio_pct': _pct(iniciaron, inscritos),
        'culminacion_iniciados_pct': _pct(terminaron, iniciaron),
        'culminacion_inscritos_pct': _pct(terminaron, inscritos),
        'avance_modulo': avance_modulo,
        'avance_pct': avance_pct,
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

    Si ya hay culminaciones con al menos 2 iniciadores (p. ej. diploma), gana
    entre esos. Un 1 de 1 no llena la caja. Si nadie terminó así, solo entran
    cursos con al menos cinco iniciadores.
    """
    con_inicio = [fila for fila in por_curso if fila['iniciaron']]
    mas_inicios = None
    if con_inicio:
        mas_inicios = sorted(
            con_inicio,
            key=lambda fila: (-fila['iniciaron'], -fila['inscritos'], fila['nombre']),
        )[0]
    clave = lambda fila: (
        -(fila['culminacion_iniciados_pct'] or 0),
        -fila['iniciaron'],
        fila['nombre'],
    )
    con_termino = [
        fila for fila in por_curso
        if fila['terminaron'] and fila['iniciaron'] >= 2
    ]
    if con_termino:
        mayor = sorted(con_termino, key=clave)[0]
    else:
        elegibles = [fila for fila in por_curso if fila['iniciaron'] >= MIN_INICIADORES_CULMINACION]
        mayor = sorted(elegibles, key=clave)[0] if elegibles else None
    return {
        'mas_inicios': _recorte(mas_inicios),
        'mayor_culminacion': _recorte(mayor),
        'min_iniciadores': MIN_INICIADORES_CULMINACION,
        'culminacion_por_terminados': bool(con_termino),
    }


def _semaforo(pct) -> str:
    if pct is None:
        return 'gris'
    if pct >= 70:
        return 'verde'
    if pct >= 35:
        return 'amarillo'
    return 'rojo'


def metricas_cursos(org) -> dict:
    """Totales, una fila por curso y los cursos agrupados por línea de WhatsApp."""
    ids_universo = ids_estudiantes_analitica(org)
    progresos = list(
        ProgresoEstudiante.objects.filter(
            estudiante_id__in=ids_universo,
        ).select_related('modulo_actual').values_list(
            'id',
            'estudiante_id',
            'curso_id',
            'completado',
            'fecha_ultimo_avance',
            'modulo_actual__numero',
        )
    ) if ids_universo else []
    ids_curso = {curso_id for _, _, curso_id, _, _, _ in progresos}
    cursos = list(
        Curso.objects.filter(Q(id__in=ids_curso) | Q(cliente=org, activo=True))
        .order_by('orden', 'nombre')
    )

    publicados = {
        curso.id: list(
            modulos_publicados_wa_qs(curso).order_by('numero').values_list('id', 'numero')
        )
        for curso in cursos
    }
    pub_ids = {curso.id: {mid for mid, _ in pares} for curso, pares in (
        (c, publicados[c.id]) for c in cursos
    )}
    max_numero = {
        curso.id: max((num for _, num in publicados[curso.id]), default=0)
        for curso in cursos
    }
    cerrados: dict[int, set[int]] = {}
    max_cerrado: dict[int, int] = {}
    if ids_universo:
        for progreso_id, modulo_id, numero in ModuloCompletado.objects.filter(
            progreso__estudiante_id__in=ids_universo,
        ).values_list('progreso_id', 'modulo_id', 'modulo__numero'):
            cerrados.setdefault(progreso_id, set()).add(modulo_id)
            if numero is not None:
                prev = max_cerrado.get(progreso_id, 0)
                if int(numero) > prev:
                    max_cerrado[progreso_id] = int(numero)

    # inscritos, iniciaron, terminaron, suma_modulos, suma_avance_pct
    acumulado: dict[int, list] = {curso.id: [0, 0, 0, 0.0, 0] for curso in cursos}
    cursos_iniciados: dict[int, set[int]] = {}
    terminaron_persona: set[int] = set()
    for progreso_id, estudiante_id, curso_id, completado, fecha_avance, num_actual in progresos:
        modulos = cerrados.get(progreso_id, set())
        # Inicio = arrancó el módulo inicial (avance real, no solo el primer envío).
        inicio = completado or bool(modulos) or fecha_avance is not None
        if inicio:
            cursos_iniciados.setdefault(estudiante_id, set()).add(curso_id)
        if completado:
            terminaron_persona.add(estudiante_id)
        total_modulos = len(pub_ids.get(curso_id, ()))
        if completado:
            avance_pct = 100
            modulo_alcanzado = float(max_numero.get(curso_id, 0) or total_modulos or 0)
        else:
            if total_modulos:
                avance_pct = min(
                    100,
                    int(len(modulos & pub_ids[curso_id]) * 100 / total_modulos),
                )
            else:
                avance_pct = 0
            modulo_alcanzado = float(max(
                max_cerrado.get(progreso_id, 0),
                int(num_actual or 0),
            ))
        fila = acumulado[curso_id]
        fila[0] += 1
        fila[1] += int(inicio)
        fila[2] += int(completado)
        fila[3] += modulo_alcanzado
        fila[4] += avance_pct

    por_curso = []
    for curso in cursos:
        datos = _fila(*acumulado[curso.id])
        datos['id'] = curso.id
        datos['nombre'] = curso.nombre
        datos['general'] = curso.cliente_id is None
        datos['avance_semaforo'] = _semaforo(datos['avance_pct'])
        por_curso.append(datos)

    total = _fila(*(sum(fila[i] for fila in acumulado.values()) for i in range(5)))
    total['avance_semaforo'] = _semaforo(total['avance_pct'])
    registrados = len(ids_universo)
    personas_iniciaron = len(cursos_iniciados)
    personas_terminaron = len(terminaron_persona)
    total['registrados'] = registrados
    total['iniciaron_reg'] = personas_iniciaron
    total['terminaron_reg'] = personas_terminaron
    total['inicio_pct'] = _pct(personas_iniciaron, registrados)
    total['culminacion_inscritos_pct'] = _pct(personas_terminaron, registrados)
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
    """NPS alineado con el Pulso admin (misma función y filtros de cliente activo)."""
    data = nps_nota_cierre(cliente_id=org.pk, solo_activos=True)
    return {
        'n': data['n'],
        'nps': data['nps'],
        'promotores': data['promotores'],
        'pasivos': data['pasivos'],
        'detractores': data['detractores'],
    }
