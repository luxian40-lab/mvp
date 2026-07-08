"""Asistencia y calificaciones del aula docente (portal profesor)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import Count, F, Sum
from django.utils.dateparse import parse_date

from core.gamificacion import EvaluacionNotaGamificacion, PerfilGamificacion
from core.gamificacion_modo import (
    gamificacion_activa,
    modo_usa_calificacion,
    modo_usa_puntos,
    registrar_nota_gamificacion,
    resumen_calificaciones_estudiante,
)
from core.models import Curso, Estudiante, ProgresoEstudiante

from .models import AsistenciaAula, EntregaTarea, TareaCurso

PESO_ASISTENCIA = Decimal('1')
NOTA_PRESENTE = Decimal('5')
NOTA_AUSENTE = Decimal('1')


def estudiantes_inscritos_curso(curso: Curso):
    """Estudiantes activos con progreso en el curso."""
    return (
        Estudiante.objects.filter(
            progresos__curso=curso,
            activo=True,
        )
        .distinct()
        .order_by('nombre')
    )


def _detalle_asistencia(fecha: date) -> str:
    return f'Asistencia {fecha.isoformat()}'


def _sync_asistencia_gamificacion(asistencia: AsistenciaAula) -> None:
    """Asistencia cuenta como 1 punto de peso en el promedio (modo calificación)."""
    cliente = asistencia.curso.cliente
    if not cliente or not modo_usa_calificacion(cliente):
        if cliente and modo_usa_puntos(cliente) and asistencia.presente:
            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=asistencia.estudiante)
            motivo = _detalle_asistencia(asistencia.fecha)
            if not perfil.transacciones.filter(razon=motivo).exists():
                perfil.ajustar_puntos_manual(1, motivo)
        return

    detalle = _detalle_asistencia(asistencia.fecha)
    nota = NOTA_PRESENTE if asistencia.presente else NOTA_AUSENTE
    prev = EvaluacionNotaGamificacion.objects.filter(
        estudiante=asistencia.estudiante,
        curso=asistencia.curso,
        tipo='asistencia',
        detalle=detalle,
    ).first()
    if prev:
        prev.nota = nota
        prev.peso = PESO_ASISTENCIA
        prev.save(update_fields=['nota', 'peso'])
    else:
        registrar_nota_gamificacion(
            asistencia.estudiante,
            nota,
            'asistencia',
            curso=asistencia.curso,
            detalle=detalle,
            peso=PESO_ASISTENCIA,
        )


def sincronizar_nota_tarea_entrega(entrega: EntregaTarea) -> None:
    """Refleja la nota de tarea en el ranking por calificaciones (peso 1)."""
    if entrega.nota is None:
        EvaluacionNotaGamificacion.objects.filter(
            estudiante=entrega.estudiante,
            curso=entrega.tarea.curso,
            tipo='tarea_aula',
            detalle=f'Tarea: {entrega.tarea.titulo}'[:200],
        ).delete()
        return

    cliente = entrega.tarea.curso.cliente
    if not cliente or not modo_usa_calificacion(cliente):
        return

    detalle = f'Tarea: {entrega.tarea.titulo}'[:200]
    prev = EvaluacionNotaGamificacion.objects.filter(
        estudiante=entrega.estudiante,
        curso=entrega.tarea.curso,
        tipo='tarea_aula',
        detalle=detalle,
    ).first()
    if prev:
        prev.nota = Decimal(str(entrega.nota))
        prev.peso = Decimal('1')
        prev.save(update_fields=['nota', 'peso'])
    else:
        registrar_nota_gamificacion(
            entrega.estudiante,
            entrega.nota,
            'tarea_aula',
            curso=entrega.tarea.curso,
            detalle=detalle,
            peso=Decimal('1'),
        )


def guardar_asistencia_sesion(request, curso: Curso, fecha: date, presente_ids: set[int]) -> int:
    """Registra asistencia de todos los inscritos para una fecha. Devuelve # presentes."""
    pu = getattr(request, 'portal_usuario', None)
    user = pu.user if pu else None
    count = 0
    for est in estudiantes_inscritos_curso(curso):
        presente = est.pk in presente_ids
        if presente:
            count += 1
        asistencia, _ = AsistenciaAula.objects.update_or_create(
            curso=curso,
            estudiante=est,
            fecha=fecha,
            defaults={'presente': presente, 'registrado_por': user},
        )
        _sync_asistencia_gamificacion(asistencia)
    return count


def filas_asistencia_curso(curso: Curso, fecha: date) -> list[dict]:
    """Lista inscritos con checkbox de asistencia para una fecha."""
    registros = {
        a.estudiante_id: a
        for a in AsistenciaAula.objects.filter(curso=curso, fecha=fecha)
    }
    filas = []
    for est in estudiantes_inscritos_curso(curso):
        reg = registros.get(est.pk)
        filas.append({
            'estudiante': est,
            'presente': reg.presente if reg else False,
            'registrado': reg is not None,
        })
    return filas


def resumen_asistencia_estudiante(curso: Curso, estudiante_id: int) -> dict:
    agg = AsistenciaAula.objects.filter(curso=curso, estudiante_id=estudiante_id).aggregate(
        total=Count('id'),
        presentes=Count('id', filter=F('presente')),
    )
    return {
        'total': agg['total'] or 0,
        'presentes': agg['presentes'] or 0,
    }


def filas_calificacion_curso(curso: Curso) -> list[dict]:
    """Resumen por estudiante: asistencia, tareas, evaluaciones y promedio."""
    filas = []
    for est in estudiantes_inscritos_curso(curso):
        asist = resumen_asistencia_estudiante(curso, est.pk)
        entregas = (
            EntregaTarea.objects.filter(estudiante=est, tarea__curso=curso, nota__isnull=False)
            .select_related('tarea')
            .order_by('tarea__titulo')
        )
        evals = (
            EvaluacionNotaGamificacion.objects.filter(estudiante=est, curso=curso)
            .order_by('-fecha')
        )
        resumen = resumen_calificaciones_estudiante(est, curso_id=curso.pk)
        promedio = float(resumen['promedio']) if resumen['promedio'] is not None else None
        filas.append({
            'estudiante': est,
            'asistencia': asist,
            'entregas': list(entregas),
            'evaluaciones': list(evals),
            'promedio': promedio,
            'num_evaluaciones': resumen['cantidad'],
            'suma_pesos': float(resumen['suma_pesos']) if resumen['suma_pesos'] else 0,
        })
    return filas


def parse_fecha_asistencia(raw: str) -> date | None:
    return parse_date((raw or '').strip())


def actualizar_nota_evaluacion(eval_id: int, curso: Curso, nota_raw: str) -> EvaluacionNotaGamificacion:
    try:
        nota = Decimal(str(nota_raw).replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError('Nota inválida. Use un número entre 1 y 5.')
    if not Decimal('1') <= nota <= Decimal('5'):
        raise ValueError('La nota debe estar entre 1 y 5.')

    ev = EvaluacionNotaGamificacion.objects.get(pk=eval_id, curso=curso)
    ev.nota = nota
    ev.save(update_fields=['nota'])
    return ev


def registrar_nota_manual_curso(
    curso: Curso,
    estudiante_id: int,
    nota_raw: str,
    detalle: str = '',
    peso_raw: str = '',
) -> dict:
    try:
        est = Estudiante.objects.get(pk=estudiante_id, cliente=curso.cliente, activo=True)
    except Estudiante.DoesNotExist:
        raise ValueError('Estudiante no válido.')

    try:
        nota = Decimal(str(nota_raw).replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError('Nota inválida.')
    peso = Decimal(str(peso_raw).replace(',', '.')) if peso_raw else Decimal('1')

    registrar_nota_gamificacion(
        est,
        nota,
        'manual',
        curso=curso,
        detalle=(detalle or 'Evaluación docente')[:200],
        peso=peso,
    )
    resumen = resumen_calificaciones_estudiante(est, curso_id=curso.pk)
    return {
        'estudiante': est,
        'promedio': float(resumen['promedio']) if resumen['promedio'] is not None else None,
    }


def contexto_modo_calificacion(org) -> dict:
    return {
        'gamif_activa': gamificacion_activa(org),
        'usa_calificacion': modo_usa_calificacion(org),
        'usa_puntos': modo_usa_puntos(org),
    }
