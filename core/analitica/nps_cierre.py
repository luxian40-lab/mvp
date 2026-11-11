"""NPS de la nota 1–10 al cerrar el curso (misma regla que el portal).

Promotores 9–10, pasivos 7–8, detractores 1–6.
NPS = porcentaje de promotores menos porcentaje de detractores.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from django.db.models import Count, Q


def _pct(parte: int, total: int) -> int:
    if not total:
        return 0
    return round(parte * 100 / total)


def nps_nota_cierre(
    *,
    cliente_id: Optional[int] = None,
    curso_id: Optional[int] = None,
    grupo_id: Optional[int] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    solo_activos: bool = True,
) -> dict:
    """Agrega NotaCierreCurso con filtros del admin.

    Retorna ``{n, nps, promotores, pasivos, detractores, pct_*, por_nota}``.
    ``nps`` es None si no hay notas (no se inventa 0).
    """
    from core.models import NotaCierreCurso

    qs = NotaCierreCurso.objects.all()
    if solo_activos:
        qs = qs.filter(estudiante__activo=True)
    if cliente_id:
        qs = qs.filter(estudiante__cliente_id=cliente_id)
    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    if grupo_id:
        qs = qs.filter(estudiante__grupos__id=grupo_id).distinct()
    if fecha_inicio:
        qs = qs.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha__date__lte=fecha_fin)

    fila = qs.aggregate(
        n=Count('id'),
        promotores=Count('id', filter=Q(nota__gte=9)),
        pasivos=Count('id', filter=Q(nota__gte=7, nota__lte=8)),
        detractores=Count('id', filter=Q(nota__lte=6)),
    )
    n = int(fila['n'] or 0)
    promotores = int(fila['promotores'] or 0)
    pasivos = int(fila['pasivos'] or 0)
    detractores = int(fila['detractores'] or 0)

    por_nota_map = {i: 0 for i in range(1, 11)}
    for row in qs.values('nota').annotate(total=Count('id')):
        nota = int(row['nota'] or 0)
        if 1 <= nota <= 10:
            por_nota_map[nota] = int(row['total'] or 0)
    por_nota = [{'nota': i, 'n': por_nota_map[i]} for i in range(1, 11)]

    if not n:
        return {
            'n': 0,
            'nps': None,
            'promotores': 0,
            'pasivos': 0,
            'detractores': 0,
            'pct_promotores': 0,
            'pct_pasivos': 0,
            'pct_detractores': 0,
            'por_nota': por_nota,
        }
    return {
        'n': n,
        'nps': round((promotores - detractores) * 100 / n),
        'promotores': promotores,
        'pasivos': pasivos,
        'detractores': detractores,
        'pct_promotores': _pct(promotores, n),
        'pct_pasivos': _pct(pasivos, n),
        'pct_detractores': _pct(detractores, n),
        'por_nota': por_nota,
    }


def nps_por_curso(
    *,
    cliente_id: Optional[int] = None,
    grupo_id: Optional[int] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    solo_activos: bool = True,
    limite: int = 40,
) -> list[dict]:
    """NPS agregado por curso (filtro org/grupo/fechas). Orden: más notas primero."""
    from core.models import NotaCierreCurso

    qs = NotaCierreCurso.objects.all()
    if solo_activos:
        qs = qs.filter(estudiante__activo=True)
    if cliente_id:
        qs = qs.filter(estudiante__cliente_id=cliente_id)
    if grupo_id:
        qs = qs.filter(estudiante__grupos__id=grupo_id).distinct()
    if fecha_inicio:
        qs = qs.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha__date__lte=fecha_fin)

    filas = (
        qs.values('curso_id', 'curso__nombre')
        .annotate(
            n=Count('id'),
            promotores=Count('id', filter=Q(nota__gte=9)),
            pasivos=Count('id', filter=Q(nota__gte=7, nota__lte=8)),
            detractores=Count('id', filter=Q(nota__lte=6)),
        )
        .order_by('-n', 'curso__nombre')[:limite]
    )
    out = []
    for f in filas:
        n = int(f['n'] or 0)
        promotores = int(f['promotores'] or 0)
        pasivos = int(f['pasivos'] or 0)
        detractores = int(f['detractores'] or 0)
        out.append(
            {
                'curso_id': f['curso_id'],
                'nombre': f['curso__nombre'] or f'Curso {f["curso_id"]}',
                'n': n,
                'nps': round((promotores - detractores) * 100 / n) if n else None,
                'promotores': promotores,
                'pasivos': pasivos,
                'detractores': detractores,
                'pct_promotores': _pct(promotores, n),
                'pct_pasivos': _pct(pasivos, n),
                'pct_detractores': _pct(detractores, n),
            }
        )
    return out


def nps_campos_contexto(
    *,
    cliente_id: Optional[int] = None,
    curso_id: Optional[int] = None,
    grupo_id: Optional[int] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
) -> dict:
    """Claves listas para el contexto / payload del Pulso admin."""
    data = nps_nota_cierre(
        cliente_id=cliente_id,
        curso_id=curso_id,
        grupo_id=grupo_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
    por_curso = []
    if not curso_id:
        por_curso = nps_por_curso(
            cliente_id=cliente_id,
            grupo_id=grupo_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
    return {
        'nps': data['nps'],
        'nps_n': data['n'],
        'nps_promotores': data['promotores'],
        'nps_pasivos': data['pasivos'],
        'nps_detractores': data['detractores'],
        'nps_pct_promotores': data['pct_promotores'],
        'nps_pct_pasivos': data['pct_pasivos'],
        'nps_pct_detractores': data['pct_detractores'],
        'nps_por_nota': data['por_nota'],
        'nps_por_curso': por_curso,
    }
