"""NPS de la nota 1–10 al cerrar el curso (misma regla que el portal).

Promotores 9–10, pasivos 7–8, detractores 1–6.
NPS = porcentaje de promotores menos porcentaje de detractores.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from django.db.models import Count, Q


def nps_nota_cierre(
    *,
    cliente_id: Optional[int] = None,
    curso_id: Optional[int] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    solo_activos: bool = True,
) -> dict:
    """Agrega NotaCierreCurso con filtros del admin.

    Retorna ``{n, nps, promotores, pasivos, detractores}``.
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
    if not n:
        return {
            'n': 0,
            'nps': None,
            'promotores': 0,
            'pasivos': 0,
            'detractores': 0,
        }
    return {
        'n': n,
        'nps': round((promotores - detractores) * 100 / n),
        'promotores': promotores,
        'pasivos': pasivos,
        'detractores': detractores,
    }


def nps_campos_contexto(
    *,
    cliente_id: Optional[int] = None,
    curso_id: Optional[int] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
) -> dict:
    """Claves listas para el contexto / payload del Pulso admin."""
    data = nps_nota_cierre(
        cliente_id=cliente_id,
        curso_id=curso_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
    return {
        'nps': data['nps'],
        'nps_n': data['n'],
        'nps_promotores': data['promotores'],
        'nps_pasivos': data['pasivos'],
        'nps_detractores': data['detractores'],
    }
