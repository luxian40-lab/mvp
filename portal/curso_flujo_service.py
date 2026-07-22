"""Embudo de avance por módulo (solo lectura) — portal B2B y Learning Analytics admin."""

from __future__ import annotations

from core.drip_schedule import max_modulo_alcanzado
from core.models import Curso, Modulo, ProgresoEstudiante


def _progresos_curso(
    *,
    curso: Curso,
    cliente_id: int | None = None,
    grupo_id: int | None = None,
) -> list:
    progresos_qs = ProgresoEstudiante.objects.filter(
        curso=curso,
        estudiante__activo=True,
    ).select_related('estudiante', 'estudiante__cliente', 'modulo_actual')

    if cliente_id:
        progresos_qs = progresos_qs.filter(estudiante__cliente_id=cliente_id)
    elif curso.cliente_id:
        progresos_qs = progresos_qs.filter(estudiante__cliente_id=curso.cliente_id)

    if grupo_id:
        progresos_qs = progresos_qs.filter(estudiante__grupos__id=grupo_id).distinct()

    return list(progresos_qs)


def _modulo_actual_numero(prog) -> int:
    """Número de módulo donde está el estudiante hoy (0 = sin iniciar). Completados → 0 aquí."""
    if prog.completado:
        return 0
    if prog.modulo_actual_id and prog.modulo_actual:
        return int(prog.modulo_actual.numero)
    return int(max_modulo_alcanzado(prog) or 0)


def _pct_float(cantidad: int, total: int, places: int = 3) -> float:
    """Porcentaje con hasta 3 decimales."""
    if total <= 0:
        return 0.0
    return round((cantidad / total) * 100.0, places)


def _pct_label(valor: float, places: int = 3) -> str:
    """
    Etiqueta ES tipo 1,0 … 1,888:
    al menos 1 decimal, hasta 3, sin ceros de relleno a la derecha.
    """
    raw = f'{float(valor):.{places}f}'.rstrip('0')
    if raw.endswith('.'):
        raw += '0'
    if '.' not in raw:
        raw += '.0'
    return raw.replace('.', ',')


def _bar_pct(cantidad: int, total: int) -> float:
    """Ancho = proporción de estudiantes del total (la barra crece con esa cantidad)."""
    if total <= 0 or cantidad <= 0:
        return 0.0
    return round((cantidad / total) * 100.0, 3)


def embudo_avance_por_curso(
    *,
    curso_id: int,
    cliente_id: int | None = None,
    grupo_id: int | None = None,
) -> dict | None:
    """
    Cuántos estudiantes alcanzaron cada módulo (histórico / acumulado).
    «Alcanzó M{n}» = máximo módulo >= n o curso completado.
    Usado en portal flujo del curso.
    """
    try:
        curso = Curso.objects.get(pk=curso_id, activo=True)
    except Curso.DoesNotExist:
        return None

    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    progresos = _progresos_curso(curso=curso, cliente_id=cliente_id, grupo_id=grupo_id)
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
        'modo': 'historico',
    }


def embudo_posicion_hoy_por_curso(
    *,
    curso_id: int,
    cliente_id: int | None = None,
    grupo_id: int | None = None,
) -> dict | None:
    """
    Snapshot a día de hoy: cada estudiante cuenta en un solo bucket
    (sin iniciar / en Mn / completó). Learning Analytics.
    """
    try:
        curso = Curso.objects.get(pk=curso_id, activo=True)
    except Curso.DoesNotExist:
        return None

    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    progresos = _progresos_curso(curso=curso, cliente_id=cliente_id, grupo_id=grupo_id)
    total = len(progresos)

    por_modulo: dict[float, int] = {float(m.numero): 0 for m in modulos}
    completados = 0
    sin_iniciar = 0

    for prog in progresos:
        if prog.completado:
            completados += 1
            continue
        n = _modulo_actual_numero(prog)
        if n <= 0:
            sin_iniciar += 1
            continue
        key = float(n)
        if key in por_modulo:
            por_modulo[key] += 1
        else:
            # Módulo huérfano / número no en catálogo → tratar como sin iniciar visible
            sin_iniciar += 1

    max_bucket = max(
        [sin_iniciar, completados] + [por_modulo.get(float(m.numero), 0) for m in modulos],
        default=0,
    )

    pasos = []
    for mod in modulos:
        en_modulo = por_modulo.get(float(mod.numero), 0)
        pct = _pct_float(en_modulo, total)
        pasos.append({
            'modulo': mod,
            'numero': mod.numero,
            'titulo': mod.titulo,
            'estudiantes': en_modulo,
            'pct': pct,
            'pct_label': _pct_label(pct),
            'bar_pct': _bar_pct(en_modulo, total),
            'drop_pct': None,
        })

    sin_pct = _pct_float(sin_iniciar, total)
    comp_pct = _pct_float(completados, total)

    return {
        'curso': curso,
        'organizacion': curso.cliente,
        'total_inscritos': total,
        'completados': completados,
        'completados_pct': comp_pct,
        'completados_pct_label': _pct_label(comp_pct),
        'completados_bar_pct': _bar_pct(completados, total),
        'sin_iniciar': sin_iniciar,
        'sin_iniciar_pct': sin_pct,
        'sin_iniciar_pct_label': _pct_label(sin_pct),
        'sin_iniciar_bar_pct': _bar_pct(sin_iniciar, total),
        'max_bucket': max_bucket,
        'pasos': pasos,
        'modo': 'hoy',
    }


def embudo_curso_portal(org, curso_id: int) -> dict | None:
    """Embudo scoped a la organización del portal (acumulado histórico)."""
    try:
        curso = Curso.objects.get(pk=curso_id, cliente=org, activo=True)
    except Curso.DoesNotExist:
        return None
    return embudo_avance_por_curso(
        curso_id=curso.id,
        cliente_id=org.id if org else None,
    )
