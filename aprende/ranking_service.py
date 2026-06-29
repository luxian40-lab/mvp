"""Ranking de gamificación en el aula (por grupo de estudiantes)."""

from __future__ import annotations

from django.db.models import Count

from core.gamificacion import PerfilGamificacion
from core.gamificacion_modo import (
    gamificacion_activa,
    modo_usa_calificacion,
    modo_usa_puntos,
    ranking_calificaciones_cliente,
)
from core.models import Curso, Estudiante, ModuloCompletado
from core.models_extras import GrupoEstudiantes


def _grupo_para_ranking(estudiante: Estudiante, curso: Curso | None = None) -> GrupoEstudiantes | None:
    """Grupo preferido: vinculado al curso, si no el primero activo del estudiante."""
    qs = estudiante.grupos.filter(activo=True)
    if curso:
        por_curso = qs.filter(cursos=curso).first()
        if por_curso:
            return por_curso
    return qs.first()


def ranking_puntos_grupo(
    grupo: GrupoEstudiantes,
    *,
    limite: int = 50,
) -> list[dict]:
    ids = list(grupo.estudiantes.filter(activo=True).values_list('pk', flat=True))
    if not ids:
        return []

    perfiles = (
        PerfilGamificacion.objects.filter(estudiante_id__in=ids, estudiante__activo=True)
        .select_related('estudiante')
        .order_by('-puntos_totales', '-nivel', 'estudiante__nombre')[:limite]
    )
    out: list[dict] = []
    for pos, p in enumerate(perfiles, start=1):
        out.append({
            'posicion': pos,
            'estudiante_id': p.estudiante_id,
            'nombre': p.estudiante.nombre,
            'puntos': p.puntos_totales,
            'nivel': p.nivel,
            'racha': p.racha_dias_actual,
        })
    return out


def ranking_calificacion_grupo(
    grupo: GrupoEstudiantes,
    cliente,
    curso_id: int | None = None,
    *,
    limite: int = 50,
) -> list[dict]:
    global_rank = ranking_calificaciones_cliente(cliente, curso_id=curso_id, limite=500)
    ids = set(grupo.estudiantes.filter(activo=True).values_list('pk', flat=True))
    filtrado = [r for r in global_rank if r['estudiante_id'] in ids][:limite]
    for i, row in enumerate(filtrado, start=1):
        row['posicion'] = i
    return filtrado


def ranking_avance_grupo_curso(
    grupo: GrupoEstudiantes,
    curso: Curso,
    *,
    limite: int = 50,
) -> list[dict]:
    """Ranking por módulos completados en un curso (competitivo por avance)."""
    estudiantes = list(
        grupo.estudiantes.filter(activo=True).order_by('nombre').values('pk', 'nombre')
    )
    if not estudiantes:
        return []

    ids = [e['pk'] for e in estudiantes]
    conteos = dict(
        ModuloCompletado.objects.filter(
            progreso__estudiante_id__in=ids,
            progreso__estudiante__activo=True,
            modulo__curso=curso,
        )
        .values('progreso__estudiante_id')
        .annotate(n=Count('id'))
        .values_list('progreso__estudiante_id', 'n')
    )

    filas = [
        {
            'estudiante_id': e['pk'],
            'nombre': e['nombre'],
            'modulos': conteos.get(e['pk'], 0),
        }
        for e in estudiantes
    ]
    filas.sort(key=lambda r: (-r['modulos'], r['nombre'].lower()))
    out: list[dict] = []
    for pos, row in enumerate(filas[:limite], start=1):
        out.append({**row, 'posicion': pos})
    return out


def _etiquetas_filas(filas: list[dict], modo: str) -> list[dict]:
    for f in filas:
        if modo == 'calificacion':
            f['valor'] = f.get('promedio')
            f['valor_unidad'] = '/5'
        elif modo == 'avance':
            f['valor'] = f.get('modulos', 0)
            f['valor_unidad'] = ' mód.'
        else:
            f['valor'] = f.get('puntos', 0)
            f['valor_unidad'] = ' pts'
    return filas


def resumen_ranking_aula(
    estudiante: Estudiante,
    curso: Curso | None = None,
) -> dict:
    cliente = getattr(estudiante, 'cliente', None)
    if not gamificacion_activa(cliente):
        return {
            'activo': False,
            'grupo': None,
            'filas': [],
            'modo': 'desactivado',
            'mi_posicion': None,
        }

    grupo = _grupo_para_ranking(estudiante, curso)
    if not grupo:
        return {
            'activo': True,
            'grupo': None,
            'filas': [],
            'modo': 'sin_grupo',
            'mi_posicion': None,
        }

    if modo_usa_calificacion(cliente):
        filas = ranking_calificacion_grupo(grupo, cliente, curso_id=curso.pk if curso else None)
        modo = 'calificacion'
    elif curso and modo_usa_puntos(cliente):
        filas = ranking_avance_grupo_curso(grupo, curso)
        modo = 'avance'
    else:
        filas = ranking_puntos_grupo(grupo)
        modo = 'puntos'

    filas = _etiquetas_filas(filas, modo)

    mi_posicion = next(
        (f['posicion'] for f in filas if f['estudiante_id'] == estudiante.pk),
        None,
    )
    return {
        'activo': True,
        'grupo': grupo,
        'filas': filas,
        'top3': filas[:3],
        'modo': modo,
        'mi_posicion': mi_posicion,
        'curso': curso,
    }
