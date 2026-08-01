"""Agregación geográfica de estudiantes para el portal (cobertura del curso)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from core.models import Curso, Estudiante, ProgresoEstudiante

from .geo_catalogo import (
    _centroides_municipios,
    clave_departamento,
    jitter_coordenada,
    resolver_ubicacion,
)


def estudiantes_cobertura_queryset(org, curso_id: int | None = None):
    """
    org=None: todos los estudiantes activos (mapa global admin).
    curso_id: un curso concreto.
    None + org: participantes inscritos en al menos un curso activo del cliente.
    """
    if org is None:
        return Estudiante.objects.filter(activo=True)

    qs = Estudiante.objects.filter(cliente=org, activo=True)
    if curso_id:
        qs = qs.filter(
            id__in=ProgresoEstudiante.objects.filter(curso_id=curso_id).values('estudiante_id'),
        )
    else:
        curso_ids = Curso.objects.filter(cliente=org, activo=True).values_list('pk', flat=True)
        if curso_ids:
            qs = qs.filter(
                id__in=ProgresoEstudiante.objects.filter(curso_id__in=curso_ids).values('estudiante_id'),
            ).distinct()
        else:
            qs = qs.none()
    return qs


def _cursos_por_estudiante(org, estudiante_ids: list[int]) -> dict[int, list[str]]:
    if not estudiante_ids:
        return {}
    filas = (
        ProgresoEstudiante.objects.filter(
            estudiante_id__in=estudiante_ids,
            curso__cliente=org,
            curso__activo=True,
        )
        .select_related('curso')
        .order_by('curso__orden', 'curso__nombre')
    )
    out: dict[int, list[str]] = defaultdict(list)
    for p in filas:
        nombre = p.curso.nombre
        if nombre not in out[p.estudiante_id]:
            out[p.estudiante_id].append(nombre)
    return out


def resumen_por_curso(org) -> list[dict[str, Any]]:
    """Métricas territoriales por cada curso activo (para tabla comparativa)."""
    items = []
    for curso in Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre'):
        r = resumen_cobertura_geografica(org, curso.pk, include_por_curso=False)
        items.append({
            'curso_id': curso.pk,
            'nombre': curso.nombre,
            'total_estudiantes': r['total_estudiantes'],
            'con_municipio_mapeado': r['con_municipio_mapeado'],
            'municipios_distintos': r['municipios_distintos'],
            'departamentos_distintos': r['departamentos_distintos'],
        })
    return items


def resumen_cobertura_geografica(
    org,
    curso_id: int | None = None,
    *,
    include_por_curso: bool = True,
    include_puntos: bool = True,
) -> dict[str, Any]:
    """Resumen territorial + mapa municipal (coroplético por municipio).

    Con org=None agrega todos los estudiantes activos (sin filtrar por cliente).
    """
    qs = estudiantes_cobertura_queryset(org, curso_id)
    est_ids = list(qs.values_list('id', flat=True))
    cursos_est = (
        _cursos_por_estudiante(org, est_ids) if org is not None and not curso_id else {}
    )

    total = len(est_ids)
    con_depto = 0
    con_muni = 0
    con_muni_mapeado = 0

    dept_counter: Counter[str] = Counter()
    dept_clave_counter: Counter[str] = Counter()
    muni_clave_counter: Counter[str] = Counter()
    puntos: list[dict[str, Any]] = []
    agrupado_muni: dict[str, dict[str, Any]] = defaultdict(
        lambda: {'cantidad': 0, 'nombres': [], 'municipio': '', 'departamento': '', 'lat': None, 'lng': None},
    )

    for est in qs.only('id', 'nombre', 'departamento', 'municipio', 'region'):
        raw_d = (est.departamento or '').strip()
        raw_m = (est.municipio or '').strip()
        if raw_d:
            con_depto += 1
        if raw_m:
            con_muni += 1

        ubic = resolver_ubicacion(raw_m, raw_d)
        dept = ubic.departamento
        muni = ubic.municipio
        c_dept = ubic.clave_departamento
        c_muni = ubic.clave_municipio

        if dept:
            dept_counter[dept] += 1
        if c_dept:
            dept_clave_counter[c_dept] += 1

        lat, lng = None, None
        if ubic.nivel == 'municipio' and c_muni:
            con_muni_mapeado += 1
            muni_clave_counter[c_muni] += 1
            row = _centroides_municipios().get(c_muni)
            if row:
                lat, lng = float(row['lat']), float(row['lng'])
                lat, lng = jitter_coordenada(est.id, lat, lng)
            bucket = agrupado_muni[c_muni]
            bucket['municipio'] = muni
            bucket['departamento'] = dept
            bucket['lat'] = lat
            bucket['lng'] = lng
            bucket['cantidad'] += 1
            if len(bucket['nombres']) < 12:
                bucket['nombres'].append(est.nombre)

        if include_puntos:
            puntos.append({
                'estudiante_id': est.id,
                'nombre': est.nombre,
                'departamento': dept or None,
                'departamento_clave': c_dept or None,
                'municipio': muni or None,
                'municipio_clave': c_muni or None,
                'region': (est.region or '').strip() or None,
                'cursos': cursos_est.get(est.id, []),
                'mapeado': ubic.nivel == 'municipio',
                'metodo': ubic.metodo,
                'lat': lat,
                'lng': lng,
            })

    por_departamento = [
        {
            'departamento': dep,
            'clave': clave_departamento(dep),
            'cantidad': cnt,
            'porcentaje': round(cnt / total * 100, 1) if total else 0,
        }
        for dep, cnt in dept_counter.most_common()
    ]

    por_municipio_list = []
    for clave, cnt in muni_clave_counter.most_common():
        row = _centroides_municipios().get(clave, {})
        por_municipio_list.append({
            'clave': clave,
            'municipio': row.get('municipio', ''),
            'departamento': row.get('departamento', ''),
            'cantidad': cnt,
        })

    top_municipios = [
        {'municipio': f"{m['municipio']}, {m['departamento']}", 'cantidad': m['cantidad']}
        for m in por_municipio_list[:15]
    ]

    marcadores_municipio = sorted(
        [
            {
                'clave': clave,
                'municipio': v['municipio'],
                'departamento': v['departamento'],
                'lat': v['lat'],
                'lng': v['lng'],
                'cantidad': v['cantidad'],
                'nombres': v['nombres'],
            }
            for clave, v in agrupado_muni.items()
            if v.get('lat') is not None
        ],
        key=lambda x: -x['cantidad'],
    )

    if org is None:
        cursos_activos = Curso.objects.filter(activo=True).count()
        por_curso = []
        filtro = 'global_todos_estudiantes'
    else:
        cursos_activos = Curso.objects.filter(cliente=org, activo=True).count()
        por_curso = (
            resumen_por_curso(org) if include_por_curso and cursos_activos >= 1 else []
        )
        filtro = 'curso' if curso_id else 'todos_cursos'

    return {
        'filtro': filtro,
        'curso_id': curso_id,
        'total_estudiantes': total,
        'con_departamento': con_depto,
        'con_municipio': con_muni,
        'con_municipio_mapeado': con_muni_mapeado,
        'departamentos_distintos': len(dept_counter),
        'municipios_distintos': len(muni_clave_counter),
        'por_departamento': por_departamento,
        'por_departamento_clave': dict(dept_clave_counter),
        'por_municipio_clave': dict(muni_clave_counter),
        'por_municipio': por_municipio_list,
        'por_curso': por_curso,
        'cursos_activos': cursos_activos,
        'max_departamento': max(dept_clave_counter.values(), default=0),
        'max_municipio': max(muni_clave_counter.values(), default=0),
        'top_municipios': top_municipios,
        'marcadores_municipio': marcadores_municipio,
        'puntos': puntos,
    }
