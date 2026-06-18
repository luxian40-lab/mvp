"""Ajuste de avance por estudiante/curso (sin eliminar al estudiante)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Count

from core.module_steps import reset_progreso_pasos_modulo
from core.models import (
    Curso,
    Estudiante,
    Examen,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
    RespuestaEjercicio,
    ResultadoExamen,
)
from core.models_certificados import Certificado


def modulos_curso_ordenados(curso: Curso) -> list[Modulo]:
    return list(curso.modulos.order_by('numero'))


def resumen_avance(estudiante: Estudiante, curso: Curso) -> dict:
    """Estado actual del estudiante en un curso."""
    progreso = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso)
        .select_related('modulo_actual')
        .first()
    )
    if not progreso:
        return {
            'tiene_progreso': False,
            'modulo_actual': None,
            'modulos_completados': 0,
            'total_modulos': curso.modulos.count(),
            'completado': False,
            'tiene_certificado': Certificado.objects.filter(
                estudiante=estudiante, curso=curso,
            ).exists(),
        }

    completados = progreso.modulos_completados.count()
    return {
        'tiene_progreso': True,
        'progreso': progreso,
        'modulo_actual': progreso.modulo_actual,
        'modulos_completados': completados,
        'total_modulos': curso.modulos.count(),
        'completado': progreso.completado,
        'tiene_certificado': Certificado.objects.filter(
            estudiante=estudiante, curso=curso,
        ).exists(),
    }


def filas_avance_curso(cliente, curso: Curso) -> list[dict]:
    """Todos los estudiantes activos del cliente con resumen de avance en el curso."""
    estudiantes = Estudiante.objects.filter(cliente=cliente, activo=True).order_by('nombre')
    progresos = {
        p.estudiante_id: p
        for p in ProgresoEstudiante.objects.filter(
            curso=curso,
            estudiante__cliente=cliente,
        ).select_related('modulo_actual')
    }
    completados_por_est = {
        row['progreso_id']: row['n']
        for row in ModuloCompletado.objects.filter(
            progreso__curso=curso,
            progreso__estudiante__cliente=cliente,
        ).values('progreso_id').annotate(n=Count('id'))
    }

    cert_est_ids = set(
        Certificado.objects.filter(curso=curso, estudiante__cliente=cliente)
        .values_list('estudiante_id', flat=True)
    )

    filas = []
    for est in estudiantes:
        prog = progresos.get(est.id)
        if prog:
            filas.append({
                'estudiante': est,
                'progreso': prog,
                'modulo_actual': prog.modulo_actual,
                'modulos_completados': completados_por_est.get(prog.id, 0),
                'completado': prog.completado,
                'tiene_certificado': est.id in cert_est_ids,
            })
        else:
            filas.append({
                'estudiante': est,
                'progreso': None,
                'modulo_actual': None,
                'modulos_completados': 0,
                'completado': False,
                'tiene_certificado': est.id in cert_est_ids,
            })
    return filas


@transaction.atomic
def ajustar_avance_hasta_modulo(
    estudiante: Estudiante,
    curso: Curso,
    modulo_destino: Modulo,
    *,
    quitar_certificado: bool = True,
    quitar_resultado_examen: bool = True,
) -> dict:
    """
    Deja al estudiante en `modulo_destino`: borra completados de ese módulo en adelante,
    mantiene los anteriores. Al escribir *listo* retoma desde ese módulo.
    """
    if modulo_destino.curso_id != curso.id:
        raise ValueError('El módulo no pertenece al curso.')
    if estudiante.cliente_id and curso.cliente_id and estudiante.cliente_id != curso.cliente_id:
        raise ValueError('Estudiante y curso de clientes distintos.')

    progreso, _ = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso,
        defaults={'completado': False, 'modulo_actual': modulo_destino},
    )

    eliminados = ModuloCompletado.objects.filter(
        progreso=progreso,
        modulo__numero__gte=modulo_destino.numero,
    ).delete()[0]

    modulo_ids_reset = list(
        curso.modulos.filter(numero__gte=modulo_destino.numero).values_list('id', flat=True)
    )
    if modulo_ids_reset:
        RespuestaEjercicio.objects.filter(
            estudiante=estudiante,
            ejercicio__modulo_id__in=modulo_ids_reset,
        ).delete()

    progreso.modulo_actual = modulo_destino
    progreso.completado = False
    progreso.fecha_completado = None
    reset_progreso_pasos_modulo(progreso, save=False)
    progreso.save(
        update_fields=[
            'modulo_actual',
            'completado',
            'fecha_completado',
            'paso_actual_modulo',
            'esperando_respuesta_evaluacion_paso',
            'paso_evaluacion_paso',
        ]
    )

    cert_borrados = 0
    if quitar_certificado:
        cert_borrados = Certificado.objects.filter(
            estudiante=estudiante, curso=curso,
        ).delete()[0]

    examen_borrados = 0
    if quitar_resultado_examen:
        examen = Examen.objects.filter(curso=curso).first()
        if examen:
            examen_borrados = ResultadoExamen.objects.filter(
                estudiante=estudiante, examen=examen,
            ).delete()[0]

    if estudiante.estado_chat != 'ACTIVO' or estudiante.estado_onboarding != 'completado':
        estudiante.estado_chat = 'ACTIVO'
        estudiante.estado_onboarding = 'completado'
        estudiante.save(update_fields=['estado_chat', 'estado_onboarding'])

    return {
        'estudiante': estudiante,
        'modulo_destino': modulo_destino,
        'completados_eliminados': eliminados,
        'certificados_eliminados': cert_borrados,
        'resultados_examen_eliminados': examen_borrados,
    }


@transaction.atomic
def reiniciar_avance_curso(
    estudiante: Estudiante,
    curso: Curso,
    *,
    quitar_certificado: bool = True,
    quitar_resultado_examen: bool = True,
) -> dict:
    """Borra todo el avance del curso y deja al estudiante en el primer módulo."""
    primer = curso.modulos.order_by('numero').first()
    if not primer:
        raise ValueError('El curso no tiene módulos.')

    progreso = ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso).first()
    eliminados = 0
    if progreso:
        eliminados = progreso.modulos_completados.all().delete()[0]
        RespuestaEjercicio.objects.filter(
            estudiante=estudiante,
            ejercicio__modulo__curso=curso,
        ).delete()

    resultado = ajustar_avance_hasta_modulo(
        estudiante,
        curso,
        primer,
        quitar_certificado=quitar_certificado,
        quitar_resultado_examen=quitar_resultado_examen,
    )
    resultado['completados_eliminados'] = eliminados
    return resultado


@transaction.atomic
def ajustar_avance_estudiantes(
    estudiante_ids: set[int] | list[int],
    curso: Curso,
    modulo_destino: Modulo | None,
    *,
    reiniciar: bool = False,
    quitar_certificado: bool = True,
    quitar_resultado_examen: bool = True,
) -> list[dict]:
    """Aplica ajuste masivo a varios estudiantes del mismo curso."""
    estudiantes = Estudiante.objects.filter(
        pk__in=estudiante_ids,
        activo=True,
    )
    if curso.cliente_id:
        estudiantes = estudiantes.filter(cliente_id=curso.cliente_id)

    resultados = []
    for est in estudiantes:
        if reiniciar:
            resultados.append(reiniciar_avance_curso(
                est, curso,
                quitar_certificado=quitar_certificado,
                quitar_resultado_examen=quitar_resultado_examen,
            ))
        elif modulo_destino:
            resultados.append(ajustar_avance_hasta_modulo(
                est, curso, modulo_destino,
                quitar_certificado=quitar_certificado,
                quitar_resultado_examen=quitar_resultado_examen,
            ))
    return resultados
