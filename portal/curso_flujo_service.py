"""Embudo de avance por módulo (solo lectura) para el portal B2B."""

from __future__ import annotations

from core.drip_schedule import max_modulo_alcanzado
from core.models import Curso, Modulo, ProgresoEstudiante


def embudo_curso_portal(org, curso_id: int) -> dict | None:
    """
    Cuántos estudiantes alcanzaron cada módulo (sin modificar el curso).
    «Alcanzó M{n}» = máximo módulo >= n o curso completado.
    """
    try:
        curso = Curso.objects.get(pk=curso_id, cliente=org, activo=True)
    except Curso.DoesNotExist:
        return None

    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    progresos = list(
        ProgresoEstudiante.objects.filter(
            curso=curso,
            estudiante__cliente=org,
            estudiante__activo=True,
        ).select_related('estudiante')
    )
    total = len(progresos)

    pasos = []
    for mod in modulos:
        alcanzaron = 0
        for prog in progresos:
            max_n = max_modulo_alcanzado(prog) or 0
            if prog.completado or float(max_n) >= float(mod.numero):
                alcanzaron += 1
        pasos.append({
            'modulo': mod,
            'numero': mod.numero,
            'titulo': mod.titulo,
            'estudiantes': alcanzaron,
            'pct': round(alcanzaron / total * 100, 1) if total else 0.0,
        })

    completados = sum(1 for p in progresos if p.completado)
    sin_iniciar = sum(1 for p in progresos if (max_modulo_alcanzado(p) or 0) == 0 and not p.completado)

    return {
        'curso': curso,
        'total_inscritos': total,
        'completados': completados,
        'sin_iniciar': sin_iniciar,
        'pasos': pasos,
    }
