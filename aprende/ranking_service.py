"""Ranking de gamificación en el aula (general del curso; helpers por grupo quedan por si se reactivan)."""

from __future__ import annotations

from core.gamificacion import PerfilGamificacion
from core.gamificacion_modo import (
    gamificacion_activa,
    curso_usa_calificacion,
    curso_usa_puntos,
    ranking_calificaciones_cliente,
)
from core.models import Curso, Estudiante
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
    estudiantes = list(
        grupo.estudiantes.filter(activo=True).order_by('nombre').values('pk', 'nombre')
    )
    if not estudiantes:
        return []

    ids = [e['pk'] for e in estudiantes]
    perfiles = {
        p.estudiante_id: p
        for p in PerfilGamificacion.objects.filter(estudiante_id__in=ids).select_related('estudiante')
    }

    filas = []
    for e in estudiantes:
        perfil = perfiles.get(e['pk'])
        filas.append({
            'estudiante_id': e['pk'],
            'nombre': e['nombre'],
            'puntos': perfil.puntos_totales if perfil else 0,
            'nivel': perfil.nivel if perfil else 1,
            'racha': perfil.racha_dias_actual if perfil else 0,
        })

    filas.sort(key=lambda r: (-r['puntos'], -r['nivel'], r['nombre'].lower()))
    out: list[dict] = []
    for pos, row in enumerate(filas[:limite], start=1):
        out.append({**row, 'posicion': pos})
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


def _etiquetas_filas(filas: list[dict], modo: str) -> list[dict]:
    for f in filas:
        if modo == 'calificacion':
            f['valor'] = f.get('promedio')
            f['valor_unidad'] = '/5'
        elif modo == 'puntos':
            f['valor'] = f.get('puntos', 0)
            f['valor_unidad'] = ' pts'
    return filas


def _filas_puntos_curso(curso: Curso, *, limite: int = 100) -> list[dict]:
    from core.models import ProgresoEstudiante

    ids = list(
        ProgresoEstudiante.objects.filter(curso=curso, estudiante__activo=True)
        .values_list('estudiante_id', flat=True)
        .distinct()
    )
    perfiles = {
        p.estudiante_id: p
        for p in PerfilGamificacion.objects.filter(estudiante_id__in=ids).select_related('estudiante')
    }
    nombres = {
        e['pk']: e['nombre']
        for e in Estudiante.objects.filter(pk__in=ids).values('pk', 'nombre')
    }
    filas_raw = []
    for eid in ids:
        perfil = perfiles.get(eid)
        filas_raw.append({
            'estudiante_id': eid,
            'nombre': nombres.get(eid, '—'),
            'puntos': perfil.puntos_totales if perfil else 0,
            'nivel': perfil.nivel if perfil else 1,
            'racha': perfil.racha_dias_actual if perfil else 0,
        })
    filas_raw.sort(key=lambda r: (-r['puntos'], -r['nivel'], r['nombre'].lower()))
    out: list[dict] = []
    for pos, row in enumerate(filas_raw[:limite], start=1):
        out.append({**row, 'posicion': pos})
    return out


def ranking_curso_profesor(cliente, curso: Curso, *, limite: int = 100) -> dict:
    """Un solo ranking general del curso (sin tablas por grupo, por ahora)."""
    ranking_activo = gamificacion_activa(cliente) or (
        curso is not None and getattr(curso, 'es_modo_clases', lambda: False)()
    )
    if not ranking_activo:
        return {
            'activo': False,
            'grupo': None,
            'filas': [],
            'top3': [],
            'modo': 'desactivado',
            'ambito': 'curso',
            'curso': curso,
            'grupos': [],
        }

    if curso_usa_calificacion(cliente, curso):
        modo = 'calificacion'
        filas = _etiquetas_filas(
            ranking_calificaciones_cliente(cliente, curso_id=curso.pk, limite=limite),
            modo,
        )
    elif curso_usa_puntos(cliente, curso):
        modo = 'puntos'
        filas = _etiquetas_filas(_filas_puntos_curso(curso, limite=limite), modo)
    else:
        return {
            'activo': False,
            'grupo': None,
            'filas': [],
            'top3': [],
            'modo': 'desactivado',
            'ambito': 'curso',
            'curso': curso,
            'grupos': [],
        }

    return {
        'activo': True,
        'grupo': None,
        'filas': filas,
        'top3': filas[:3],
        'modo': modo,
        'ambito': 'curso',
        'curso': curso,
        # Por ahora no mostramos ranking por grupo (sigue disponible en helpers).
        'grupos': [],
        'mi_posicion': None,
        'mi_puntos': None,
        'lider_puntos': filas[0].get('puntos', 0) if filas and modo == 'puntos' else None,
        'puntos_para_subir': None,
    }


def resumen_ranking_aula(
    estudiante: Estudiante,
    curso: Curso | None = None,
) -> dict:
    """
    Ranking del aula para el estudiante.

    Por ahora: un solo ranking **general del curso** (no por grupo).
    Sin curso: vacío (la UI de ranking vive en la pestaña del curso).
    """
    cliente = getattr(estudiante, 'cliente', None)
    ranking_activo = gamificacion_activa(cliente) or (
        curso is not None and getattr(curso, 'es_modo_clases', lambda: False)()
    )
    if not ranking_activo:
        return {
            'activo': False,
            'grupo': None,
            'filas': [],
            'modo': 'desactivado',
            'ambito': 'curso',
            'mi_posicion': None,
            'curso': curso,
        }

    if curso is None:
        return {
            'activo': True,
            'grupo': None,
            'filas': [],
            'top3': [],
            'modo': 'sin_curso',
            'ambito': 'curso',
            'mi_posicion': None,
            'curso': None,
        }

    if curso_usa_calificacion(cliente, curso):
        modo = 'calificacion'
        filas = ranking_calificaciones_cliente(cliente, curso_id=curso.pk, limite=100)
    elif curso_usa_puntos(cliente, curso):
        modo = 'puntos'
        filas = _filas_puntos_curso(curso, limite=100)
    else:
        return {
            'activo': False,
            'grupo': None,
            'filas': [],
            'modo': 'desactivado',
            'ambito': 'curso',
            'mi_posicion': None,
            'curso': curso,
        }

    filas = _etiquetas_filas(filas, modo)

    mi_posicion = next(
        (f['posicion'] for f in filas if f['estudiante_id'] == estudiante.pk),
        None,
    )
    mi_fila = next((f for f in filas if f['estudiante_id'] == estudiante.pk), None)
    lider_puntos = filas[0].get('puntos', 0) if filas and modo == 'puntos' else None
    mi_puntos = mi_fila.get('puntos', 0) if mi_fila and modo == 'puntos' else None
    puntos_para_subir = None
    if mi_fila and modo == 'puntos' and mi_posicion and mi_posicion > 1:
        anterior = next((f for f in filas if f['posicion'] == mi_posicion - 1), None)
        if anterior:
            puntos_para_subir = max(0, anterior.get('puntos', 0) - mi_fila.get('puntos', 0) + 1)

    return {
        'activo': True,
        'grupo': None,
        'filas': filas,
        'top3': filas[:3],
        'modo': modo,
        'ambito': 'curso',
        'mi_posicion': mi_posicion,
        'mi_puntos': mi_puntos,
        'lider_puntos': lider_puntos,
        'puntos_para_subir': puntos_para_subir,
        'curso': curso,
    }
