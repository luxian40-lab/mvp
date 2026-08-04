"""Métricas de retención y Centro de Éxito del Programa (portal B2B)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from core.utils_telefono import normalizar_telefono, variantes_telefono

from . import centro_exito

DIAS_ESTUDIANTE_ACTIVO = 7

ESTADOS_SIN_ONBOARDING = frozenset({
    'ESPERANDO_HABEAS_DATA',
    'ESPERANDO_CEDULA',
    'CONFIRMANDO_DATOS',
    'ESPERANDO_AYUDA_MODIFICAR',
    'ESPERANDO_CORRECCION_DATOS',
    'nuevo',
    'esperando_tipo_doc',
    'esperando_cedula_legacy',
    'esperando_nombre',
})


def _parse_fecha(s: str | None):
    if not s:
        return None
    from datetime import datetime

    try:
        return datetime.strptime(s.strip()[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _progreso_qs(org, *, curso_id=None, grupo_id=None, desde=None, hasta=None):
    from core.models import ProgresoEstudiante

    qs = ProgresoEstudiante.objects.filter(estudiante__cliente=org)
    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    if grupo_id:
        qs = qs.filter(estudiante__grupos__id=grupo_id).distinct()
    desde_dt = _parse_fecha(desde)
    hasta_dt = _parse_fecha(hasta)
    if desde_dt:
        qs = qs.filter(fecha_inicio__date__gte=desde_dt)
    if hasta_dt:
        qs = qs.filter(fecha_inicio__date__lte=hasta_dt)
    return qs


def _telefonos_scope(progreso_qs):
    tels: set[str] = set()
    for tel in progreso_qs.values_list('estudiante__telefono', flat=True).distinct():
        if not tel:
            continue
        t = normalizar_telefono(tel)
        if t:
            tels.add(t)
        tels.update(variantes_telefono(tel))
    return tels


def _ultima_actividad_por_estudiante(progreso_qs, telefonos: set[str]) -> dict[int, timezone.datetime]:
    """Estudiante_id → última fecha de avance o mensaje WhatsApp entrante."""
    from core.models import WhatsappLog

    out: dict[int, timezone.datetime] = {}
    for row in progreso_qs.values('estudiante_id', 'fecha_ultimo_avance'):
        eid = row['estudiante_id']
        ts = row['fecha_ultimo_avance']
        if ts and (eid not in out or ts > out[eid]):
            out[eid] = ts

    if not telefonos:
        return out

    hace_90 = timezone.now() - timedelta(days=90)
    tel_to_est = {}
    for eid, tel in progreso_qs.values_list('estudiante_id', 'estudiante__telefono').distinct():
        for v in variantes_telefono(tel or ''):
            tel_to_est[v] = eid

    logs = (
        WhatsappLog.objects.filter(
            telefono__in=list(telefonos),
            fecha__gte=hace_90,
            tipo='INCOMING',
        )
        .values('telefono', 'fecha')
        .order_by('telefono', '-fecha')
    )
    seen: set[str] = set()
    for log in logs:
        tel = log['telefono']
        if tel in seen:
            continue
        seen.add(tel)
        eid = tel_to_est.get(tel)
        if not eid:
            continue
        f = log['fecha']
        if eid not in out or f > out[eid]:
            out[eid] = f
    return out


def _embudo_modulos(progreso_qs, curso) -> list[dict]:
    from core.models import Modulo, ModuloCompletado

    if not curso:
        return []

    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    if not modulos:
        return []

    progreso_ids = list(progreso_qs.values_list('pk', flat=True))
    if not progreso_ids:
        return []

    completados_por_mod: dict[int, set[int]] = {m.pk: set() for m in modulos}
    for row in (
        ModuloCompletado.objects.filter(progreso_id__in=progreso_ids)
        .values('progreso_id', 'modulo_id')
        .distinct()
    ):
        mid = row['modulo_id']
        if mid in completados_por_mod:
            completados_por_mod[mid].add(row['progreso_id'])

    pasos: list[dict] = []
    prev_count: int | None = None
    for m in modulos:
        count = len(completados_por_mod.get(m.pk, set()))
        pct = round(count / prev_count * 100, 1) if prev_count else None
        pasos.append({
            'tipo': 'modulo',
            'numero': m.numero,
            'etiqueta': f'Módulo {m.numero} completado',
            'titulo': (m.titulo or '')[:48],
            'cantidad': count,
            'pct_desde_anterior': pct,
        })
        prev_count = count
    return pasos


def _modulo_mayor_abandono(progreso_qs, curso) -> dict | None:
    from core.models import Modulo, ModuloCompletado

    if not curso:
        return None

    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    if len(modulos) < 2:
        return None

    progreso_ids = list(progreso_qs.values_list('pk', flat=True))
    if not progreso_ids:
        return None

    comp_by_mod: dict[int, set[int]] = {}
    for row in ModuloCompletado.objects.filter(progreso_id__in=progreso_ids).values(
        'progreso_id', 'modulo_id'
    ):
        comp_by_mod.setdefault(row['modulo_id'], set()).add(row['progreso_id'])

    peor: dict | None = None
    for i, m in enumerate(modulos[:-1]):
        nxt = modulos[i + 1]
        set_n = comp_by_mod.get(m.pk, set())
        if not set_n:
            continue
        set_n1 = comp_by_mod.get(nxt.pk, set())
        caidas = len(set_n - set_n1)
        tasa = round(caidas / len(set_n) * 100, 1)
        if peor is None or caidas > peor['caidas']:
            peor = {
                'modulo_numero': m.numero,
                'modulo_titulo': m.titulo or f'Módulo {m.numero}',
                'siguiente_numero': nxt.numero,
                'caidas': caidas,
                'tasa_pct': tasa,
            }
    return peor


def _tiempo_promedio_modulo_dias(progreso_qs) -> float | None:
    """Promedio de días entre módulos completados (1 query, sin N+1)."""
    from collections import defaultdict

    from core.models import ModuloCompletado

    progreso_ids = list(progreso_qs.values_list('pk', flat=True)[:3000])
    if not progreso_ids:
        return None

    by_prog: dict[int, list] = defaultdict(list)
    for pid, fecha in (
        ModuloCompletado.objects.filter(progreso_id__in=progreso_ids)
        .order_by('progreso_id', 'fecha_completado')
        .values_list('progreso_id', 'fecha_completado')
    ):
        by_prog[pid].append(fecha)

    deltas: list[float] = []
    for fechas in by_prog.values():
        for i in range(1, len(fechas)):
            delta = (fechas[i] - fechas[i - 1]).total_seconds() / 86400
            if 0 < delta < 365:
                deltas.append(delta)
    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 1)


def analitica_retencion_portal(
    org,
    *,
    curso_id: int | None = None,
    grupo_id: int | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    dias_activo: int = DIAS_ESTUDIANTE_ACTIVO,
    force: bool = False,
) -> dict[str, Any]:
    """Snapshot Centro de Éxito. Cache corto para no recalcular WA/scores en cada hit."""
    from django.core.cache import cache

    cache_key = (
        f'ce:ret:v3:{getattr(org, "pk", org)}:{curso_id or 0}:{grupo_id or 0}:'
        f'{desde or ""}:{hasta or ""}:{dias_activo}'
    )
    if not force:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    data = _analitica_retencion_portal_uncached(
        org,
        curso_id=curso_id,
        grupo_id=grupo_id,
        desde=desde,
        hasta=hasta,
        dias_activo=dias_activo,
    )
    cache.set(cache_key, data, 90)
    return data


def _analitica_retencion_portal_uncached(
    org,
    *,
    curso_id: int | None = None,
    grupo_id: int | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    dias_activo: int = DIAS_ESTUDIANTE_ACTIVO,
) -> dict[str, Any]:
    from core.models import Curso
    from core.models_certificados import Certificado

    curso = Curso.objects.filter(pk=curso_id, cliente=org).first() if curso_id else None
    progreso_qs = _progreso_qs(org, curso_id=curso_id, grupo_id=grupo_id, desde=desde, hasta=hasta)
    progreso_qs = progreso_qs.select_related('estudiante', 'curso', 'modulo_actual').annotate(
        n_mods=Count('modulos_completados', distinct=True),
    )

    inscritos = progreso_qs.count()
    now = timezone.now()
    umbral_activo = now - timedelta(days=max(1, dias_activo))

    telefonos = _telefonos_scope(progreso_qs)
    ultima_act = _ultima_actividad_por_estudiante(progreso_qs, telefonos)

    estudiante_ids = set(progreso_qs.values_list('estudiante_id', flat=True))

    aceptan_datos = progreso_qs.exclude(
        estudiante__estado_chat__in=ESTADOS_SIN_ONBOARDING
    ).count()

    comienzan = progreso_qs.filter(
        Q(n_mods__gt=0) | Q(fecha_ultimo_avance__isnull=False) | Q(modulo_actual__isnull=False)
    ).count()

    completados_curso = progreso_qs.filter(completado=True).count()

    certificados_q = Certificado.objects.filter(estudiante__cliente=org, emitido=True)
    if curso_id:
        certificados_q = certificados_q.filter(curso_id=curso_id)
    if grupo_id:
        certificados_q = certificados_q.filter(estudiante__grupos__id=grupo_id).distinct()
    certificados = certificados_q.filter(
        estudiante_id__in=estudiante_ids,
    ).values('estudiante_id', 'curso_id').distinct().count()

    activos = 0
    inactivos = 0
    dias_sin_respuesta: list[float] = []

    for p in progreso_qs:
        if p.completado:
            continue
        eid = p.estudiante_id
        ult = ultima_act.get(eid) or p.fecha_ultimo_avance
        if ult and ult >= umbral_activo:
            activos += 1
        else:
            inactivos += 1
            if ult:
                dias_sin_respuesta.append((now - ult).total_seconds() / 86400)

    tiempo_promedio_abandono = (
        round(sum(dias_sin_respuesta) / len(dias_sin_respuesta), 1) if dias_sin_respuesta else None
    )
    tiempo_promedio_modulo = _tiempo_promedio_modulo_dias(progreso_qs)

    pct_certificacion = round(certificados / inscritos * 100, 1) if inscritos else 0.0
    pct_activos = round(activos / inscritos * 100, 1) if inscritos else 0.0

    modulo_abandono = _modulo_mayor_abandono(progreso_qs, curso)

    embudo: list[dict] = [
        {
            'tipo': 'paso',
            'etiqueta': 'Inscripciones (filtro)',
            'cantidad': inscritos,
            'pct_desde_anterior': None,
        },
        {
            'tipo': 'paso',
            'etiqueta': 'Aceptaron datos (onboarding)',
            'cantidad': aceptan_datos,
            'pct_desde_anterior': round(aceptan_datos / inscritos * 100, 1) if inscritos else None,
        },
        {
            'tipo': 'paso',
            'etiqueta': 'Comenzaron el curso',
            'cantidad': comienzan,
            'pct_desde_anterior': round(comienzan / aceptan_datos * 100, 1) if aceptan_datos else None,
        },
    ]
    embudo.extend(_embudo_modulos(progreso_qs, curso))
    embudo.append({
        'tipo': 'paso',
        'etiqueta': 'Certificados emitidos',
        'cantidad': certificados,
        'pct_desde_anterior': round(certificados / inscritos * 100, 1) if inscritos else None,
    })

    embudo_max = inscritos or 1
    for paso in embudo:
        paso['pct_del_total'] = round(paso['cantidad'] / embudo_max * 100, 1)

    # —— Centro de Éxito (score, predicción, mapa, cohortes, etc.) ——
    total_mods_por_curso: dict[int, int] = {}
    curso_ids = set(progreso_qs.values_list('curso_id', flat=True))
    if curso_ids:
        from core.models import Modulo

        for row in (
            Modulo.objects.filter(curso_id__in=curso_ids)
            .values('curso_id')
            .annotate(n=Count('id'))
        ):
            total_mods_por_curso[row['curso_id']] = row['n']

    pcts = []
    for p in progreso_qs:
        if p.completado:
            continue
        tm = total_mods_por_curso.get(p.curso_id, 0)
        nm = getattr(p, 'n_mods', 0) or 0
        if tm:
            pcts.append(100.0 * nm / tm)
    promedio_grupo_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0.0

    wa_stats = centro_exito._wa_stats_por_estudiante(progreso_qs, telefonos)
    filas_riesgo = centro_exito.calcular_scores_riesgo(
        progreso_qs,
        ultima_act=ultima_act,
        wa_stats=wa_stats,
        total_mods_por_curso=total_mods_por_curso,
        promedio_grupo_pct=promedio_grupo_pct,
    )
    resumen_riesgo = centro_exito.resumen_riesgo(filas_riesgo)
    mapa = centro_exito.mapa_abandono_modulos(progreso_qs, curso)
    mapa_pasos = centro_exito.mapa_abandono_pasos(progreso_qs, curso)
    curva = centro_exito.curva_abandono(progreso_qs, ultima_act)
    cohortes = centro_exito.cohortes_mensuales(progreso_qs, ultima_act)
    vivo = centro_exito.embudo_vivo(progreso_qs, ultima_act, wa_stats=wa_stats)
    comparativa = centro_exito.comparativa_eki(
        org, curso_id=curso_id, pct_certificacion=pct_certificacion,
    )
    kpis = {
        'inscritos': inscritos,
        'activos': activos,
        'inactivos': inactivos,
        'certificados': certificados,
        'completados_curso': completados_curso,
        'pct_certificacion': pct_certificacion,
        'pct_activos': pct_activos,
        'tiempo_promedio_abandono_dias': tiempo_promedio_abandono,
        'tiempo_promedio_modulo_dias': tiempo_promedio_modulo,
        'modulo_mayor_abandono': modulo_abandono,
    }
    recomendaciones = centro_exito.recomendaciones_programa(
        mapa=mapa,
        resumen=resumen_riesgo,
        cohortes=cohortes,
        curva=curva,
        kpis=kpis,
        comparativa=comparativa,
        mapa_pasos=mapa_pasos,
    )
    wa_health = centro_exito.whatsapp_health_agregado(wa_stats, filas_riesgo)
    automatizaciones = centro_exito.automatizaciones_sugeridas(resumen_riesgo, mapa)

    alto_detalle = [f for f in filas_riesgo if f['nivel'] == 'alto'][:40]
    medio_detalle = [f for f in filas_riesgo if f['nivel'] == 'medio'][:20]

    return {
        'curso': curso,
        'dias_activo': dias_activo,
        'kpis': kpis,
        'embudo': embudo,
        'embudo_vivo': vivo,
        'requiere_curso_para_modulos': curso is None,
        'riesgo': {
            'resumen': resumen_riesgo,
            'alto': alto_detalle,
            'medio': medio_detalle,
        },
        'mapa_abandono': mapa,
        'mapa_abandono_pasos': mapa_pasos,
        'curva_abandono': curva,
        'cohortes': cohortes,
        'comparativa_eki': comparativa,
        'recomendaciones': recomendaciones,
        'whatsapp_health': wa_health,
        'automatizaciones': automatizaciones,
    }
