"""
Centro de Éxito del Programa — score de riesgo, predicción y señales
para el panel /portal/retencion/ (independiente de Nat comercial).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone

from core.utils_telefono import variantes_telefono

RIESGO_BAJO = 'bajo'
RIESGO_MEDIO = 'medio'
RIESGO_ALTO = 'alto'

# Umbrales del score 0–100 (más alto = más riesgo de abandono).
UMBRAL_MEDIO = 35
UMBRAL_ALTO = 65

DIAS_CURVA = (1, 5, 10, 15, 30)


def _nivel_riesgo(score: int) -> str:
    if score >= UMBRAL_ALTO:
        return RIESGO_ALTO
    if score >= UMBRAL_MEDIO:
        return RIESGO_MEDIO
    return RIESGO_BAJO


def _pct_completado(n_mods: int, total_mods: int) -> float:
    if total_mods <= 0:
        return 0.0
    return round(min(100.0, 100.0 * n_mods / total_mods), 1)


def _wa_stats_por_estudiante(
    progreso_qs,
    telefonos: set[str],
    *,
    ventana_dias: int = 90,
) -> dict[int, dict[str, Any]]:
    """Señales WhatsApp por estudiante: última, horas, días, recordatorios sin respuesta."""
    from core.models import WhatsappLog

    out: dict[int, dict[str, Any]] = defaultdict(lambda: {
        'ultimo_incoming': None,
        'ultimo_outgoing': None,
        'horas': [],
        'dias_semana': [],
        'recordatorios_ignorados': 0,
        'tiempos_respuesta_h': [],
    })
    if not telefonos:
        return out

    tel_to_est: dict[str, int] = {}
    for eid, tel in progreso_qs.values_list('estudiante_id', 'estudiante__telefono').distinct():
        for v in variantes_telefono(tel or ''):
            tel_to_est[v] = eid

    desde = timezone.now() - timedelta(days=ventana_dias)
    logs = (
        WhatsappLog.objects.filter(telefono__in=list(telefonos), fecha__gte=desde)
        .order_by('fecha')
        .values('telefono', 'fecha', 'tipo', 'es_audio')
    )

    # Por teléfono: secuencia para medir respuesta a envíos.
    por_tel: dict[str, list] = defaultdict(list)
    for row in logs:
        por_tel[row['telefono']].append(row)

    for tel, seq in por_tel.items():
        eid = tel_to_est.get(tel)
        if not eid:
            continue
        bucket = out[eid]
        last_out_ts = None
        for row in seq:
            f = row['fecha']
            if row['tipo'] == 'INCOMING':
                bucket['ultimo_incoming'] = f
                bucket['horas'].append(f.hour)
                bucket['dias_semana'].append(f.weekday())
                if last_out_ts is not None:
                    delta_h = (f - last_out_ts).total_seconds() / 3600
                    if 0 < delta_h < 72:
                        bucket['tiempos_respuesta_h'].append(delta_h)
                    last_out_ts = None
            else:
                bucket['ultimo_outgoing'] = f
                # Si ya había un envío pendiente sin respuesta > 72h, cuenta como ignorado.
                if last_out_ts is not None and (f - last_out_ts).total_seconds() > 72 * 3600:
                    bucket['recordatorios_ignorados'] += 1
                last_out_ts = f
        if last_out_ts is not None and (timezone.now() - last_out_ts).total_seconds() > 72 * 3600:
            bucket['recordatorios_ignorados'] += 1

    return out


def _favorito(counter: Counter, *, map_fn=None) -> str | None:
    if not counter:
        return None
    val, _ = counter.most_common(1)[0]
    if map_fn:
        return map_fn(val)
    return str(val)


def _hora_label(h: int) -> str:
    return f'{h:02d}:00'


_DIAS_ES = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')


def calcular_scores_riesgo(
    progreso_qs,
    *,
    ultima_act: dict[int, timezone.datetime],
    wa_stats: dict[int, dict],
    total_mods_por_curso: dict[int, int],
    promedio_grupo_pct: float,
) -> list[dict[str, Any]]:
    """Lista de estudiantes con score, nivel, predicción y explicación en texto."""
    now = timezone.now()
    filas: list[dict[str, Any]] = []

    for p in progreso_qs:
        est = p.estudiante
        eid = est.pk
        total_mods = total_mods_por_curso.get(p.curso_id, 0) or 0
        n_mods = getattr(p, 'n_mods', None)
        if n_mods is None:
            n_mods = p.modulos_completados.count()
        pct = _pct_completado(int(n_mods), total_mods)

        if p.completado:
            filas.append({
                'estudiante_id': eid,
                'nombre': est.nombre or est.cedula or f'#{eid}',
                'cedula': est.cedula or '',
                'curso_id': p.curso_id,
                'curso_nombre': getattr(p.curso, 'nombre', '') or '',
                'score': 0,
                'nivel': RIESGO_BAJO,
                'probabilidad_terminar': 96,
                'pct_completado': pct if pct else 100.0,
                'dias_sin_actividad': 0,
                'modulo_actual': None,
                'edad': est.edad,
                'rango_edad': est.rango_edad or '',
                'recordatorios_ignorados': 0,
                'razones': ['Completó el programa.'],
                'recomendacion': 'Celebrar avance o invitar a siguiente cohorte.',
                'completado': True,
            })
            continue

        ult = ultima_act.get(eid) or p.fecha_ultimo_avance
        dias_sin = int((now - ult).total_seconds() / 86400) if ult else 99
        wa = wa_stats.get(eid) or {}
        # Preferir telemetría explícita de recordatorios; fallback WhatsApp heurístico.
        try:
            from core.telemetria import recordatorios_ignorados_estudiante

            ignorados_tel = recordatorios_ignorados_estudiante(eid)
        except Exception:
            ignorados_tel = 0
        ignorados = ignorados_tel if ignorados_tel else int(wa.get('recordatorios_ignorados') or 0)
        abrio = bool(p.modulo_actual_id or n_mods > 0 or p.fecha_ultimo_avance)
        respondio_eval = False
        # Señal ligera: si hay módulos completados, suele haber pasado validación.
        if n_mods > 0:
            respondio_eval = True

        score = 0
        razones: list[str] = []

        if dias_sin >= 30:
            score += 40
            razones.append(f'Lleva {dias_sin} días sin actividad.')
        elif dias_sin >= 15:
            score += 30
            razones.append(f'Lleva {dias_sin} días sin actividad.')
        elif dias_sin >= 8:
            score += 20
            razones.append(f'Lleva {dias_sin} días sin actividad.')
        elif dias_sin >= 4:
            score += 10
            razones.append(f'Última actividad hace {dias_sin} días.')

        if not abrio:
            score += 18
            razones.append('Todavía no abrió ni avanzó en un módulo.')
        elif pct < 25:
            score += 12
            razones.append(f'Avance bajo ({pct}% del curso).')

        if promedio_grupo_pct > 0 and pct + 20 < promedio_grupo_pct:
            score += 12
            razones.append(
                f'Su grupo avanza más (promedio {promedio_grupo_pct}% vs {pct}% suyo).'
            )

        if ignorados >= 2:
            score += 12
            razones.append(f'Ignoró {ignorados} recordatorios (sin respuesta en 72 h).')
        elif ignorados == 1:
            score += 6
            razones.append('Ignoró 1 recordatorio reciente.')

        if not respondio_eval and abrio and dias_sin >= 5:
            score += 8
            razones.append('No hay registro de evaluación / avance formal.')

        edad = est.edad
        if edad and edad >= 50 and dias_sin >= 7:
            score += 5
            razones.append(f'Perfil 50+ ({edad} años) con pausa reciente — suele necesitar cápsulas cortas.')

        mod_act = None
        if p.modulo_actual_id:
            mod_act = {
                'numero': getattr(p.modulo_actual, 'numero', None),
                'titulo': (getattr(p.modulo_actual, 'titulo', None) or '')[:60],
            }
            if dias_sin >= 7:
                razones.append(
                    f'Se detuvo en el módulo {mod_act["numero"]}'
                    + (f' ({mod_act["titulo"]})' if mod_act['titulo'] else '')
                    + '.'
                )

        score = min(100, score)
        nivel = _nivel_riesgo(score)
        # Predicción heurística: parte de 88% y resta el score, con piso por avance.
        base_pred = 88 - int(score * 0.75)
        if pct >= 70:
            base_pred = max(base_pred, 70)
        if pct >= 40:
            base_pred = max(base_pred, 45)
        probabilidad = max(5, min(98, base_pred))

        if not razones:
            razones.append('Actividad reciente y avance alineado con el grupo.')

        if nivel == RIESGO_ALTO:
            rec = 'Enviar audio corto del facilitador + recordatorio personalizado por WhatsApp.'
        elif nivel == RIESGO_MEDIO:
            rec = 'Mensaje breve de reenganche y revisar si el módulo actual es demasiado largo.'
        else:
            rec = 'Mantener ritmo; no requiere intervención urgente.'

        filas.append({
            'estudiante_id': eid,
            'nombre': est.nombre or est.cedula or f'#{eid}',
            'cedula': est.cedula or '',
            'curso_id': p.curso_id,
            'curso_nombre': getattr(p.curso, 'nombre', '') or '',
            'score': score,
            'nivel': nivel,
            'probabilidad_terminar': probabilidad,
            'pct_completado': pct,
            'dias_sin_actividad': dias_sin if ult else None,
            'modulo_actual': mod_act,
            'edad': edad,
            'rango_edad': est.rango_edad or '',
            'recordatorios_ignorados': ignorados,
            'razones': razones[:5],
            'recomendacion': rec,
            'completado': False,
        })

    filas.sort(key=lambda r: (-r['score'], r['nombre']))
    return filas


def resumen_riesgo(filas: list[dict]) -> dict[str, Any]:
    activos = [f for f in filas if not f.get('completado')]
    bajo = sum(1 for f in activos if f['nivel'] == RIESGO_BAJO)
    medio = sum(1 for f in activos if f['nivel'] == RIESGO_MEDIO)
    alto = sum(1 for f in activos if f['nivel'] == RIESGO_ALTO)
    preds = [f['probabilidad_terminar'] for f in activos]
    return {
        'bajo': bajo,
        'medio': medio,
        'alto': alto,
        'total_en_curso': len(activos),
        'completados': sum(1 for f in filas if f.get('completado')),
        'probabilidad_promedio': round(sum(preds) / len(preds), 1) if preds else None,
    }


def mapa_abandono_modulos(progreso_qs, curso) -> list[dict[str, Any]]:
    """Transiciones M→M+1 con caídas — mapa visual para diseñador instruccional."""
    from core.models import Modulo, ModuloCompletado

    if not curso:
        return []
    modulos = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    if len(modulos) < 1:
        return []

    progreso_ids = list(progreso_qs.values_list('pk', flat=True))
    if not progreso_ids:
        return []

    comp_by_mod: dict[int, set[int]] = {}
    for row in ModuloCompletado.objects.filter(progreso_id__in=progreso_ids).values(
        'progreso_id', 'modulo_id'
    ):
        comp_by_mod.setdefault(row['modulo_id'], set()).add(row['progreso_id'])

    mapa: list[dict] = []
    max_caidas = 1
    for i, m in enumerate(modulos):
        set_n = comp_by_mod.get(m.pk, set())
        if i < len(modulos) - 1:
            nxt = modulos[i + 1]
            set_n1 = comp_by_mod.get(nxt.pk, set())
            caidas = len(set_n - set_n1) if set_n else 0
            tasa = round(caidas / len(set_n) * 100, 1) if set_n else 0.0
            siguiente = nxt.numero
        else:
            caidas = 0
            tasa = 0.0
            siguiente = None
        max_caidas = max(max_caidas, caidas or 1)
        mapa.append({
            'modulo_numero': m.numero,
            'titulo': (m.titulo or f'Módulo {m.numero}')[:72],
            'completaron': len(set_n),
            'caidas': caidas,
            'tasa_pct': tasa,
            'siguiente_numero': siguiente,
        })
    for row in mapa:
        row['barra_pct'] = round(100.0 * row['caidas'] / max_caidas, 1) if max_caidas else 0
    return mapa


def mapa_abandono_pasos(progreso_qs, curso) -> list[dict[str, Any]]:
    """Mapa fino por paso (requiere telemetría)."""
    try:
        from core.telemetria import mapa_abandono_por_paso

        return mapa_abandono_por_paso(progreso_qs, curso)
    except Exception:
        return []


def curva_abandono(progreso_qs, ultima_act: dict[int, timezone.datetime]) -> list[dict]:
    """% retenidos a los días 1, 5, 10, 15, 30 desde inscripción."""
    now = timezone.now()
    rows = list(progreso_qs.values('estudiante_id', 'fecha_inicio', 'completado', 'fecha_ultimo_avance'))
    if not rows:
        return [{'dia': d, 'retenidos_pct': None, 'base': 0} for d in DIAS_CURVA]

    out = []
    for dia in DIAS_CURVA:
        elegibles = 0
        retenidos = 0
        for r in rows:
            inicio = r['fecha_inicio']
            if not inicio:
                continue
            edad_dias = (now - inicio).days
            if edad_dias < dia:
                continue
            elegibles += 1
            if r['completado']:
                retenidos += 1
                continue
            ult = ultima_act.get(r['estudiante_id']) or r['fecha_ultimo_avance']
            if ult and (ult - inicio).days >= dia:
                retenidos += 1
            elif ult and (now - ult).days < 7 and edad_dias >= dia:
                # Aún activo cerca del día de corte.
                retenidos += 1
        pct = round(100.0 * retenidos / elegibles, 1) if elegibles else None
        out.append({'dia': dia, 'retenidos_pct': pct, 'base': elegibles})
    return out


def cohortes_mensuales(progreso_qs, ultima_act: dict) -> list[dict]:
    """Comparar meses de inscripción: tasa de finalización y deserción."""
    now = timezone.now()
    buckets: dict[str, dict] = {}
    for p in progreso_qs.select_related('estudiante'):
        if not p.fecha_inicio:
            continue
        key = p.fecha_inicio.strftime('%Y-%m')
        label = p.fecha_inicio.strftime('%b %Y')
        b = buckets.setdefault(key, {
            'clave': key,
            'etiqueta': label,
            'inscritos': 0,
            'completados': 0,
            'inactivos': 0,
        })
        b['inscritos'] += 1
        if p.completado:
            b['completados'] += 1
        else:
            ult = ultima_act.get(p.estudiante_id) or p.fecha_ultimo_avance
            if not ult or (now - ult).days >= 14:
                b['inactivos'] += 1

    orden = sorted(buckets.values(), key=lambda x: x['clave'])
    for b in orden:
        n = b['inscritos'] or 1
        b['tasa_completado_pct'] = round(100.0 * b['completados'] / n, 1)
        b['tasa_desercion_pct'] = round(100.0 * b['inactivos'] / n, 1)
    # Insight simple: mejor mes vs peor.
    insight = None
    if len(orden) >= 2:
        mejor = min(orden, key=lambda x: x['tasa_desercion_pct'])
        peor = max(orden, key=lambda x: x['tasa_desercion_pct'])
        if mejor['clave'] != peor['clave']:
            insight = (
                f"{mejor['etiqueta']} desertó menos ({mejor['tasa_desercion_pct']}%) "
                f"frente a {peor['etiqueta']} ({peor['tasa_desercion_pct']}%)."
            )
    return {'meses': orden[-6:], 'insight': insight}


def embudo_vivo(progreso_qs, ultima_act: dict) -> list[dict]:
    """Pasos más finos: entraron hoy → leyeron → … → finalizaron."""
    now = timezone.now()
    hoy0 = now.replace(hour=0, minute=0, second=0, microsecond=0)

    inscritos = 0
    entraron_hoy = 0
    leyeron = 0
    respondieron = 0
    listo = 0
    evaluacion = 0
    continuaron = 0
    finalizaron = 0

    for p in progreso_qs:
        inscritos += 1
        eid = p.estudiante_id
        ult = ultima_act.get(eid) or p.fecha_ultimo_avance
        n_mods = getattr(p, 'n_mods', 0) or 0
        if ult and ult >= hoy0:
            entraron_hoy += 1
        if p.modulo_actual_id or n_mods > 0 or p.fecha_ultimo_avance:
            leyeron += 1
        if n_mods > 0 or p.esperando_respuesta_evaluacion_paso:
            respondieron += 1
        if n_mods > 0 or (getattr(p, 'paso_actual_modulo', 1) or 1) > 1:
            listo += 1
        if n_mods > 0:
            evaluacion += 1
        if n_mods >= 2 or p.completado:
            continuaron += 1
        if p.completado:
            finalizaron += 1

    pasos = [
        ('Inscritos', inscritos),
        ('Entraron hoy', entraron_hoy),
        ('Leyeron / abrieron módulo', leyeron),
        ('Respondieron / interactuaron', respondieron),
        ('Escribieron listo / avanzaron', listo),
        ('Pasaron evaluación (módulo)', evaluacion),
        ('Continuaron (2+ módulos)', continuaron),
        ('Finalizaron', finalizaron),
    ]
    out = []
    prev = None
    for etiqueta, cant in pasos:
        pct_ant = round(cant / prev * 100, 1) if prev else None
        out.append({
            'etiqueta': etiqueta,
            'cantidad': cant,
            'pct_desde_anterior': pct_ant,
            'pct_del_total': round(cant / inscritos * 100, 1) if inscritos else 0.0,
        })
        prev = cant if cant else prev
    return out


def whatsapp_health_agregado(wa_stats: dict[int, dict], filas_riesgo: list[dict]) -> dict:
    """Salud WhatsApp del programa + muestra de alto riesgo."""
    horas: Counter = Counter()
    dias: Counter = Counter()
    tiempos: list[float] = []
    ultimos_dias: list[int] = []
    now = timezone.now()

    for eid, st in wa_stats.items():
        horas.update(st.get('horas') or [])
        dias.update(st.get('dias_semana') or [])
        tiempos.extend(st.get('tiempos_respuesta_h') or [])
        ui = st.get('ultimo_incoming')
        if ui:
            ultimos_dias.append(int((now - ui).total_seconds() / 86400))

    alto = [f for f in filas_riesgo if f['nivel'] == RIESGO_ALTO][:8]
    muestras = []
    for f in alto:
        st = wa_stats.get(f['estudiante_id']) or {}
        ui = st.get('ultimo_incoming')
        muestras.append({
            'nombre': f['nombre'],
            'estudiante_id': f['estudiante_id'],
            'dias_ultimo_mensaje': int((now - ui).total_seconds() / 86400) if ui else None,
            'hora_favorita': _favorito(Counter(st.get('horas') or []), map_fn=_hora_label),
            'dias_favoritos': [
                _DIAS_ES[d] for d, _ in Counter(st.get('dias_semana') or []).most_common(2)
            ],
        })

    return {
        'hora_favorita_programa': _favorito(horas, map_fn=_hora_label),
        'dias_favoritos_programa': [_DIAS_ES[d] for d, _ in dias.most_common(2)],
        'tiempo_promedio_respuesta_h': round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
        'mediana_dias_ultimo_mensaje': (
            sorted(ultimos_dias)[len(ultimos_dias) // 2] if ultimos_dias else None
        ),
        'muestras_alto_riesgo': muestras,
    }


def recomendaciones_programa(
    *,
    mapa: list[dict],
    resumen: dict,
    cohortes: dict,
    curva: list[dict],
    kpis: dict,
    comparativa: dict | None,
    mapa_pasos: list[dict] | None = None,
) -> list[dict]:
    """Reglas accionables para el coordinador (sin LLM)."""
    recs: list[dict] = []

    if resumen.get('alto'):
        recs.append({
            'prioridad': 'alta',
            'titulo': f"{resumen['alto']} personas en riesgo alto",
            'detalle': 'Priorice audio corto del facilitador y contacto hoy en su hora habitual de estudio.',
        })

    if mapa_pasos:
        peor_paso = max(mapa_pasos, key=lambda m: m.get('caidas') or 0)
        if peor_paso.get('caidas', 0) >= 2:
            media_txt = ' (tiene media/video)' if peor_paso.get('tiene_media') else ''
            recs.append({
                'prioridad': 'alta',
                'titulo': (
                    f"Paso {peor_paso.get('paso_orden')} del módulo "
                    f"{peor_paso.get('modulo_numero')}{media_txt}"
                ),
                'detalle': (
                    f"Desertan {peor_paso['caidas']} personas tras recibir este paso "
                    f"({peor_paso.get('titulo', '')}). Considere acortar o dividir el contenido."
                ),
            })

    if mapa:
        peor = max(mapa, key=lambda m: m.get('caidas') or 0)
        if peor.get('caidas', 0) >= 2:
            recs.append({
                'prioridad': 'alta',
                'titulo': f"Revisar módulo {peor['modulo_numero']}: {peor['titulo']}",
                'detalle': (
                    f"Desertan {peor['caidas']} personas hacia el siguiente módulo "
                    f"(tasa {peor['tasa_pct']}%). Considere partir el contenido en cápsulas más cortas."
                ),
            })

    if curva:
        caidas_curva = []
        prev = None
        for p in curva:
            if p['retenidos_pct'] is None:
                continue
            if prev is not None:
                caidas_curva.append((p['dia'], prev - p['retenidos_pct']))
            prev = p['retenidos_pct']
        if caidas_curva:
            dia_crit, drop = max(caidas_curva, key=lambda x: x[1])
            if drop >= 8:
                recs.append({
                    'prioridad': 'media',
                    'titulo': f'Momento crítico alrededor del día {dia_crit}',
                    'detalle': f'La retención cae ~{drop:.0f} puntos en esa ventana. Programe reenganche preventivo.',
                })

    insight = (cohortes or {}).get('insight')
    if insight:
        recs.append({
            'prioridad': 'media',
            'titulo': 'Comparación de cohortes',
            'detalle': insight + ' Revise qué cambió en contenidos o acompañamiento.',
        })

    if comparativa and comparativa.get('tu_pct') is not None and comparativa.get('eki_pct') is not None:
        if comparativa['tu_pct'] + 10 < comparativa['eki_pct']:
            recs.append({
                'prioridad': 'media',
                'titulo': 'Por debajo del promedio eki',
                'detalle': (
                    f"Su certificación ({comparativa['tu_pct']}%) está bajo el promedio eki "
                    f"({comparativa['eki_pct']}%). Enfoque el rediseño en el módulo de mayor abandono."
                ),
            })

    if kpis.get('tiempo_promedio_modulo_dias') and kpis['tiempo_promedio_modulo_dias'] > 10:
        recs.append({
            'prioridad': 'baja',
            'titulo': 'Ritmo lento entre módulos',
            'detalle': (
                f"Promedio {kpis['tiempo_promedio_modulo_dias']} días entre cierres. "
                "Valide si el drip o la carga cognitiva están frenando."
            ),
        })

    if not recs:
        recs.append({
            'prioridad': 'baja',
            'titulo': 'Programa estable',
            'detalle': 'No hay alertas fuertes. Mantenga el acompañamiento y revise retención semanalmente.',
        })
    return recs[:6]


def comparativa_eki(org, *, curso_id: int | None, pct_certificacion: float) -> dict:
    """Tu curso/org vs promedio anonimizado de la plataforma."""
    from core.models import ProgresoEstudiante
    from core.models_certificados import Certificado

    # Promedio eki: % certificados / inscritos en otros clientes (muestra reciente).
    otros = (
        ProgresoEstudiante.objects.exclude(estudiante__cliente=org)
        .values('estudiante__cliente_id')
        .annotate(n=Count('id'))
        .filter(n__gte=5)[:40]
    )
    cliente_ids = [r['estudiante__cliente_id'] for r in otros]
    if not cliente_ids:
        return {
            'tu_pct': pct_certificacion,
            'eki_pct': None,
            'etiqueta_tu': 'Su programa',
            'disponible': False,
        }

    inscritos = ProgresoEstudiante.objects.filter(estudiante__cliente_id__in=cliente_ids).count()
    certs = Certificado.objects.filter(
        estudiante__cliente_id__in=cliente_ids, emitido=True,
    ).values('estudiante_id', 'curso_id').distinct().count()
    eki_pct = round(100.0 * certs / inscritos, 1) if inscritos else None
    return {
        'tu_pct': pct_certificacion,
        'eki_pct': eki_pct,
        'etiqueta_tu': 'Su curso' if curso_id else 'Su programa',
        'disponible': eki_pct is not None,
        'delta': round(pct_certificacion - eki_pct, 1) if eki_pct is not None else None,
    }


def automatizaciones_sugeridas(resumen: dict, mapa: list[dict]) -> list[dict]:
    """Tarjetas de reglas inteligentes (diseño; ejecución = fase posterior)."""
    reglas = [
        {
            'si': 'Riesgo alto + sin actividad ≥ 7 días',
            'entonces': 'Enviar audio corto del facilitador',
            'estado': 'sugerida',
        },
        {
            'si': 'Riesgo medio + recordatorio ignorado',
            'entonces': 'Reenviar en hora favorita (WhatsApp Health)',
            'estado': 'sugerida',
        },
    ]
    if mapa:
        peor = max(mapa, key=lambda m: m.get('caidas') or 0)
        if peor.get('caidas'):
            reglas.insert(0, {
                'si': f'Abandonó tras módulo {peor["modulo_numero"]} + riesgo alto',
                'entonces': 'Enviar cápsula / video corto del siguiente paso',
                'estado': 'sugerida',
            })
    if resumen.get('alto', 0) == 0:
        reglas.append({
            'si': 'Sin riesgo alto esta semana',
            'entonces': 'Mantener drip estándar; no saturar el canal',
            'estado': 'ok',
        })
    return reglas
