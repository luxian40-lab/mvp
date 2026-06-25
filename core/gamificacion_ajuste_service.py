"""Ajuste manual de puntos y notas de gamificación (cursos híbridos / presencial)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from core.gamificacion import PerfilGamificacion
from core.gamificacion_actions import obtener_posicion_estudiante
from core.gamificacion_modo import (
    MODO_GAMIFICACION_CHOICES,
    get_modo_gamificacion,
    modo_usa_calificacion,
    registrar_nota_gamificacion,
    resumen_calificaciones_estudiante,
)
from core.models import Cliente, Curso, Estudiante


def _modo_label(modo: str) -> str:
    return dict(MODO_GAMIFICACION_CHOICES).get(modo, modo)


def filas_estudiantes_gamificacion(cliente: Cliente) -> tuple[list[dict], str]:
    """Lista estudiantes con puntos y/o promedio según modo de la org."""
    modo = get_modo_gamificacion(cliente)
    usa_notas = modo_usa_calificacion(cliente)
    filas = []

    estudiantes = Estudiante.objects.filter(cliente=cliente, activo=True).order_by('nombre')
    perfiles = {
        p.estudiante_id: p
        for p in PerfilGamificacion.objects.filter(estudiante__in=estudiantes)
    }

    for est in estudiantes:
        perfil = perfiles.get(est.pk)
        promedio = None
        num_notas = 0
        if usa_notas:
            resumen = resumen_calificaciones_estudiante(est)
            num_notas = resumen['cantidad']
            if resumen['promedio'] is not None:
                promedio = float(resumen['promedio'])

        filas.append({
            'estudiante': est,
            'puntos': perfil.puntos_totales if perfil else 0,
            'nivel': perfil.nivel if perfil else 1,
            'promedio': promedio,
            'num_notas': num_notas,
        })

    return filas, modo


def ajustar_puntos_estudiantes(
    estudiante_ids: set[int],
    delta: int,
    motivo: str,
    cliente: Cliente,
) -> list[dict]:
    if not estudiante_ids:
        raise ValueError('Marque al menos un estudiante.')
    if delta == 0:
        raise ValueError('Indique puntos distintos de cero (use + para sumar, − para restar).')

    motivo = (motivo or '').strip()
    if not motivo:
        raise ValueError('Escriba un motivo (ej. taller presencial, participación en campo).')

    resultados = []
    qs = Estudiante.objects.filter(pk__in=estudiante_ids, cliente=cliente, activo=True)
    if not qs.exists():
        raise ValueError('Ningún estudiante válido para este cliente.')

    for est in qs:
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=est)
        antes = perfil.puntos_totales
        aplicados = perfil.ajustar_puntos_manual(delta, motivo)
        perfil.refresh_from_db()
        obtener_posicion_estudiante(est)
        resultados.append({
            'estudiante': est,
            'antes': antes,
            'despues': perfil.puntos_totales,
            'aplicados': aplicados,
        })

    return resultados


def registrar_nota_manual_estudiante(
    estudiante_id: int,
    nota_raw: str,
    cliente: Cliente,
    *,
    curso_id: int | None = None,
    detalle: str = '',
    peso_raw: str = '',
) -> dict:
    try:
        est = Estudiante.objects.get(pk=estudiante_id, cliente=cliente, activo=True)
    except Estudiante.DoesNotExist:
        raise ValueError('Estudiante no válido para este cliente.')

    try:
        nota = Decimal(str(nota_raw).replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError('Nota inválida. Use un número entre 1 y 5 (ej. 4 o 3.5).')

    curso = None
    if curso_id:
        try:
            curso = Curso.objects.get(pk=curso_id, cliente=cliente, activo=True)
        except Curso.DoesNotExist:
            raise ValueError('Curso no válido para este cliente.')

    peso = None
    if peso_raw:
        try:
            peso = Decimal(str(peso_raw).replace(',', '.'))
        except (InvalidOperation, ValueError):
            raise ValueError('Peso inválido.')

    detalle = (detalle or 'Evaluación manual (equipo)').strip()[:200]
    registrar_nota_gamificacion(
        est,
        nota,
        'manual',
        curso=curso,
        detalle=detalle,
        peso=peso,
    )
    resumen = resumen_calificaciones_estudiante(est, curso_id=curso.pk if curso else None)
    promedio = float(resumen['promedio']) if resumen['promedio'] is not None else None

    return {
        'estudiante': est,
        'nota': float(nota),
        'promedio': promedio,
        'cantidad': resumen['cantidad'],
    }
