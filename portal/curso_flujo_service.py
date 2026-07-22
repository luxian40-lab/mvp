"""Embudo de avance por módulo (solo lectura) — portal B2B y Learning Analytics admin."""

from __future__ import annotations

from core.drip_schedule import max_modulo_alcanzado
from core.models import Curso, Modulo, ProgresoEstudiante


def embudo_avance_por_curso(
    *,
    curso_id: int,
    cliente_id: int | None = None,
    grupo_id: int | None = None,
) -> dict | None:
    """
    Cuántos estudiantes alcanzaron cada módulo.
    «Alcanzó M{n}» = máximo módulo >= n o curso completado.
    """
    try:
        curso = Curso.objects.get(pk=curso_id, activo=True)
    except Curso.DoesNotExist:
        return None

    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    progresos_qs = ProgresoEstudiante.objects.filter(
        curso=curso,
        estudiante__activo=True,
    ).select_related('estudiante', 'estudiante__cliente')

    if cliente_id:
        progresos_qs = progresos_qs.filter(estudiante__cliente_id=cliente_id)
    elif curso.cliente_id:
        progresos_qs = progresos_qs.filter(estudiante__cliente_id=curso.cliente_id)

    if grupo_id:
        progresos_qs = progresos_qs.filter(estudiante__grupos__id=grupo_id).distinct()

    progresos = list(progresos_qs)
    total = len(progresos)

    pasos = []
    prev = total
    for mod in modulos:
        alcanzaron = 0
        for prog in progresos:
            max_n = max_modulo_alcanzado(prog) or 0
            if prog.completado or float(max_n) >= float(mod.numero):
                alcanzaron += 1
        drop = None
        if prev > 0 and alcanzaron < prev:
            drop = round((1 - alcanzaron / prev) * 100, 1)
        pasos.append({
            'modulo': mod,
            'numero': mod.numero,
            'titulo': mod.titulo,
            'estudiantes': alcanzaron,
            'pct': round(alcanzaron / total * 100, 1) if total else 0.0,
            'drop_pct': drop,
        })
        prev = alcanzaron

    completados = sum(1 for p in progresos if p.completado)
    sin_iniciar = sum(
        1 for p in progresos if (max_modulo_alcanzado(p) or 0) == 0 and not p.completado
    )

    return {
        'curso': curso,
        'organizacion': curso.cliente,
        'total_inscritos': total,
        'completados': completados,
        'sin_iniciar': sin_iniciar,
        'pasos': pasos,
    }


def embudo_curso_portal(org, curso_id: int) -> dict | None:
    """Embudo scoped a la organización del portal."""
    try:
        curso = Curso.objects.get(pk=curso_id, cliente=org, activo=True)
    except Curso.DoesNotExist:
        return None
    return embudo_avance_por_curso(
        curso_id=curso.id,
        cliente_id=org.id if org else None,
    )
