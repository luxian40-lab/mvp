"""Asignación masiva de acceso a módulos (lista blanca por estudiante)."""

from __future__ import annotations

from django.db import transaction

from core.models import Cliente, Curso, Estudiante, HabilitacionModuloEstudiante, Modulo


def modulos_para_curso(cliente: Cliente, curso_id: int | None) -> list[Modulo]:
    if not curso_id:
        return []
    return list(
        Modulo.objects.filter(
            curso_id=curso_id,
            curso__cliente=cliente,
            curso__activo=True,
        ).order_by('numero')
    )


def habilitaciones_activas_modulo(cliente: Cliente, curso: Curso, modulo: Modulo):
    """Filas guardadas en BD con acceso activo a este módulo."""
    return (
        HabilitacionModuloEstudiante.objects.filter(
            estudiante__cliente=cliente,
            curso=curso,
            modulo=modulo,
            activo=True,
        )
        .select_related('estudiante', 'curso', 'modulo')
        .order_by('estudiante__nombre')
    )


def filas_matriz_modulo(cliente: Cliente, curso: Curso, modulo: Modulo) -> list[dict]:
    """Estudiantes del cliente con flag si tienen acceso activo al módulo."""
    habilitados = set(
        HabilitacionModuloEstudiante.objects.filter(
            estudiante__cliente=cliente,
            curso=curso,
            modulo=modulo,
            activo=True,
        ).values_list('estudiante_id', flat=True)
    )
    estudiantes = Estudiante.objects.filter(cliente=cliente, activo=True).order_by('nombre')
    return [
        {
            'estudiante': est,
            'habilitado': est.id in habilitados,
        }
        for est in estudiantes
    ]


@transaction.atomic
def sincronizar_habilitaciones_modulo(
    cliente: Cliente,
    curso: Curso,
    modulo: Modulo,
    estudiante_ids_seleccionados: set[int] | list[int],
) -> tuple[int, int]:
    """
    Crea o reactiva filas para los estudiantes marcados; desactiva el resto.
    Devuelve (habilitados_activos, desactivados).
    """
    if curso.cliente_id != cliente.id or modulo.curso_id != curso.id:
        raise ValueError('Curso o módulo fuera del cliente.')

    seleccionados = set(
        Estudiante.objects.filter(
            cliente=cliente,
            activo=True,
            pk__in=estudiante_ids_seleccionados,
        ).values_list('pk', flat=True)
    )

    existentes = {
        h.estudiante_id: h
        for h in HabilitacionModuloEstudiante.objects.filter(
            estudiante__cliente=cliente,
            curso=curso,
            modulo=modulo,
        )
    }

    desactivados = 0
    for est_id, fila in existentes.items():
        if est_id not in seleccionados and fila.activo:
            fila.activo = False
            fila.save(update_fields=['activo'])
            desactivados += 1

    for est_id in seleccionados:
        fila = existentes.get(est_id)
        if fila is None:
            HabilitacionModuloEstudiante.objects.create(
                estudiante_id=est_id,
                curso=curso,
                modulo=modulo,
                activo=True,
            )
        elif not fila.activo:
            fila.activo = True
            fila.save(update_fields=['activo'])

    return len(seleccionados), desactivados
