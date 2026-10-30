"""Ajuste de avance por estudiante/curso (sin eliminar al estudiante)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Count

from core.module_steps import pasos_activos_qs, reset_progreso_pasos_modulo
from core.models import (
    Curso,
    Estudiante,
    Examen,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    ProgresoEstudiante,
    RespuestaEjercicio,
    ResultadoExamen,
)
from core.models_certificados import Certificado


def modulos_curso_ordenados(curso: Curso) -> list[Modulo]:
    return list(curso.modulos.order_by('numero'))


def _etiqueta_paso(paso: PasoModulo, idx: int) -> str:
    sec = getattr(paso, 'seccion', None)
    if sec:
        sec_lbl = f'Sec.{sec.orden}'
        if (sec.titulo or '').strip():
            sec_lbl = f'{sec_lbl} {(sec.titulo or "").strip()[:40]}'
    else:
        sec_lbl = 'Sec.?'
    micro = (paso.titulo or '').strip()
    if not micro:
        micro = (paso.contenido or '').strip().replace('\n', ' ')[:45]
    if not micro:
        micro = f'Paso {paso.orden}'
    return f'{sec_lbl} · micro #{paso.orden} — {micro}'


def opciones_pasos_por_modulo(curso: Curso) -> dict[str, list[dict]]:
    """
    Mapa modulo_id → opciones de microcontenido para el selector admin.
    idx es el índice 1-based que usa ProgresoEstudiante.paso_actual_modulo.
    """
    out: dict[str, list[dict]] = {}
    for mod in curso.modulos.order_by('numero'):
        opts = []
        for i, paso in enumerate(pasos_activos_qs(mod), start=1):
            opts.append({
                'id': paso.id,
                'idx': i,
                'label': _etiqueta_paso(paso, i),
            })
        out[str(mod.id)] = opts
    return out


def etiqueta_paso_actual(progreso: ProgresoEstudiante | None) -> str:
    """Texto corto sección/micro del progreso actual (para la tabla admin)."""
    if not progreso or not progreso.modulo_actual_id:
        return ''
    mod = progreso.modulo_actual
    try:
        qs = list(pasos_activos_qs(mod))
    except Exception:
        return ''
    if not qs:
        return 'Sin microcontenidos'
    if getattr(progreso, 'esperando_respuesta_evaluacion_paso', False) and getattr(
        progreso, 'paso_evaluacion_paso_id', None
    ):
        paso = getattr(progreso, 'paso_evaluacion_paso', None)
        if paso and paso.modulo_id == mod.id:
            try:
                idx = next(i for i, p in enumerate(qs, start=1) if p.id == paso.id)
            except StopIteration:
                idx = paso.orden
            return _etiqueta_paso(paso, idx) + ' (eval.)'
    idx = getattr(progreso, 'paso_actual_modulo', None) or 0
    if idx > len(qs):
        return 'Módulo listo para cerrar'
    if 1 <= idx <= len(qs):
        return _etiqueta_paso(qs[idx - 1], idx)
    return ''


def resumen_avance(estudiante: Estudiante, curso: Curso) -> dict:
    """Estado actual del estudiante en un curso."""
    progreso = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso)
        .select_related('modulo_actual', 'paso_evaluacion_paso', 'paso_evaluacion_paso__seccion')
        .first()
    )
    if not progreso:
        return {
            'tiene_progreso': False,
            'modulo_actual': None,
            'paso_actual_label': '',
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
        'paso_actual_label': etiqueta_paso_actual(progreso),
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
        ).select_related(
            'modulo_actual',
            'paso_evaluacion_paso',
            'paso_evaluacion_paso__seccion',
        )
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
                'paso_actual_label': etiqueta_paso_actual(prog),
                'modulos_completados': completados_por_est.get(prog.id, 0),
                'completado': prog.completado,
                'tiene_certificado': est.id in cert_est_ids,
            })
        else:
            filas.append({
                'estudiante': est,
                'progreso': None,
                'modulo_actual': None,
                'paso_actual_label': '',
                'modulos_completados': 0,
                'completado': False,
                'tiene_certificado': est.id in cert_est_ids,
            })
    return filas


def _indice_paso_activo(modulo: Modulo, paso: PasoModulo) -> int:
    """Índice 1-based del paso en la lista activa del módulo."""
    if paso.modulo_id != modulo.id:
        raise ValueError('El microcontenido no pertenece al módulo destino.')
    ids = list(pasos_activos_qs(modulo).values_list('id', flat=True))
    try:
        return ids.index(paso.id) + 1
    except ValueError as exc:
        raise ValueError(
            'Ese microcontenido no está activo o su sección está inactiva.'
        ) from exc


@transaction.atomic
def ajustar_avance_hasta_modulo(
    estudiante: Estudiante,
    curso: Curso,
    modulo_destino: Modulo,
    *,
    paso_destino: PasoModulo | None = None,
    quitar_certificado: bool = True,
    quitar_resultado_examen: bool = True,
) -> dict:
    """
    Deja al estudiante en `modulo_destino` (y opcionalmente en un microcontenido):
    borra completados de ese módulo en adelante, mantiene los anteriores.
    Al escribir *listo* retoma desde ese módulo/paso.
    """
    if modulo_destino.curso_id != curso.id:
        raise ValueError('El módulo no pertenece al curso.')
    if estudiante.cliente_id and curso.cliente_id and estudiante.cliente_id != curso.cliente_id:
        raise ValueError('Estudiante y curso de clientes distintos.')

    paso_idx = 1
    if paso_destino is not None:
        paso_idx = _indice_paso_activo(modulo_destino, paso_destino)

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
    if paso_destino is None:
        reset_progreso_pasos_modulo(progreso, save=False)
        paso_idx = progreso.paso_actual_modulo or 1
    else:
        progreso.paso_actual_modulo = paso_idx
        progreso.esperando_respuesta_evaluacion_paso = False
        progreso.paso_evaluacion_paso = None
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
        'paso_destino': paso_destino,
        'paso_actual_modulo': paso_idx,
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
    paso_destino: PasoModulo | None = None,
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
                paso_destino=paso_destino,
                quitar_certificado=quitar_certificado,
                quitar_resultado_examen=quitar_resultado_examen,
            ))
    return resultados
