"""Métricas por empresa / Nati: cálculo, metas y semáforos."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.utils_telefono import normalizar_telefono, variantes_telefono

DEFAULT_METAS_EDUCATIVA = {
    "finalizacion": Decimal("70"),
    "inicio": Decimal("80"),
    "max_no_iniciados": Decimal("20"),
    "lecturas": Decimal("60"),
    "verde_desde": Decimal("80"),
    "amarillo_desde": Decimal("50"),
}

DEFAULT_METAS_NATI = {
    "lectura": Decimal("60"),
    "respuesta": Decimal("70"),
    "verde_desde": Decimal("80"),
    "amarillo_desde": Decimal("50"),
}


def calcular_semaforo(valor, meta, modo: str = "mayor_es_mejor") -> str:
    """Clasifica verde / amarillo / rojo según meta."""
    if valor is None or meta is None:
        return "gris"
    try:
        v = float(valor)
        m = float(meta)
    except (TypeError, ValueError):
        return "gris"
    if m <= 0 and modo == "mayor_es_mejor":
        return "gris"

    if modo == "mayor_es_mejor":
        if v >= m:
            return "verde"
        if v >= m * 0.7:
            return "amarillo"
        return "rojo"

    if v <= m:
        return "verde"
    if v <= m * 1.3:
        return "amarillo"
    return "rojo"


def semaforo_label(color: str) -> str:
    return {
        "verde": "Meta cumplida",
        "amarillo": "En alerta",
        "rojo": "Crítico",
        "gris": "Sin datos",
    }.get(color, "Sin datos")


def _parse_fecha(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def resolver_metas_educativa(cliente_id: int | None, curso_id: int | None = None) -> dict:
    from core.models import MetaMetricaEmpresa

    base = {k: float(v) for k, v in DEFAULT_METAS_EDUCATIVA.items()}
    if not cliente_id:
        return {
            "finalizacion": base["finalizacion"],
            "inicio": base["inicio"],
            "max_no_iniciados": base["max_no_iniciados"],
            "lecturas": base["lecturas"],
            "_verde_desde": base["verde_desde"],
            "_amarillo_desde": base["amarillo_desde"],
            "_origen": "sistema",
        }

    meta = None
    if curso_id:
        meta = (
            MetaMetricaEmpresa.objects.filter(
                cliente_id=cliente_id, curso_id=curso_id, activa=True
            ).first()
        )
    if not meta:
        meta = (
            MetaMetricaEmpresa.objects.filter(
                cliente_id=cliente_id, curso__isnull=True, activa=True
            ).first()
        )

    if meta:
        return {
            "finalizacion": float(meta.meta_finalizacion_porcentaje),
            "inicio": float(meta.meta_inicio_porcentaje),
            "max_no_iniciados": float(meta.meta_max_no_iniciados_porcentaje),
            "lecturas": float(meta.meta_min_lectura_mensajes_porcentaje),
            "_verde_desde": float(meta.verde_desde),
            "_amarillo_desde": float(meta.amarillo_desde),
            "_origen": f"meta_{meta.pk}",
        }
    return {
        "finalizacion": base["finalizacion"],
        "inicio": base["inicio"],
        "max_no_iniciados": base["max_no_iniciados"],
        "lecturas": base["lecturas"],
        "_verde_desde": base["verde_desde"],
        "_amarillo_desde": base["amarillo_desde"],
        "_origen": "sistema",
    }


def resolver_metas_nati(cliente_id: int | None) -> dict:
    from core.models import MetaMetricaNati

    base = {k: float(v) for k, v in DEFAULT_METAS_NATI.items()}
    if not cliente_id:
        return {**base, "_origen": "sistema"}

    meta = MetaMetricaNati.objects.filter(cliente_id=cliente_id, activa=True).first()
    if meta:
        return {
            "lectura": float(meta.meta_lectura_porcentaje),
            "respuesta": float(meta.meta_respuesta_porcentaje),
            "_verde_desde": float(meta.verde_desde),
            "_amarillo_desde": float(meta.amarillo_desde),
            "_origen": f"meta_nati_{meta.pk}",
        }
    return {**base, "_origen": "sistema"}


def _pct(num: int, den: int) -> float:
    if not den:
        return 0.0
    return round(num / den * 100, 1)


def _formato_modulo_actual(progreso, mods_comp: int = 0, total_mods: int = 0) -> str:
    if progreso.completado:
        return "Curso completado"
    if progreso.modulo_actual_id and progreso.modulo_actual:
        m = progreso.modulo_actual
        return f"M{m.numero} · {m.titulo}"
    if mods_comp > 0 and total_mods:
        return f"En curso ({mods_comp}/{total_mods} módulos)"
    return "Sin iniciar"


def _estado_progreso(progreso, avance_pct: int) -> str:
    if progreso.completado:
        return "Completado"
    if avance_pct > 0:
        return "En curso"
    return "Sin avance"


def listar_progreso_estudiantes(
    progreso_q,
    limite: int = 200,
    *,
    modulo_hasta_numero: int | None = None,
    usar_drip_calendario: bool = True,
) -> list[dict]:
    """Detalle por inscripción: estudiante + curso + módulo actual."""
    from core.drip_schedule import (
        avance_sobre_modulos,
        estudiante_llego_hasta_modulo,
        max_modulo_alcanzado,
        modulos_para_metricas,
    )

    if modulo_hasta_numero is not None:
        usar_drip_calendario = False

    rows = []
    qs = (
        progreso_q.select_related("estudiante", "estudiante__cliente", "curso", "modulo_actual")
        .annotate(
            total_mods=Count("curso__modulos", distinct=True),
            mods_comp=Count("modulos_completados", distinct=True),
        )
        .order_by("estudiante__nombre", "curso__nombre")[:limite]
    )
    for p in qs:
        if modulo_hasta_numero is not None and not estudiante_llego_hasta_modulo(p, modulo_hasta_numero):
            continue
        total_mods = p.total_mods or 0
        mods_comp = p.mods_comp or 0
        avance = round(mods_comp / total_mods * 100) if total_mods else 0
        mods_drip = modulos_para_metricas(
            p.estudiante,
            p.curso,
            modulo_hasta_numero=modulo_hasta_numero,
            usar_drip_calendario=usar_drip_calendario,
        )
        comps_drip, total_drip, avance_drip = avance_sobre_modulos(p, mods_drip)
        rows.append(
            {
                "estudiante_id": p.estudiante_id,
                "nombre": p.estudiante.nombre,
                "cedula": p.estudiante.cedula or "",
                "telefono": p.estudiante.telefono or "",
                "organizacion": p.estudiante.cliente.nombre if p.estudiante.cliente_id else "-",
                "curso": p.curso.nombre if p.curso_id else "-",
                "modulo_actual": _formato_modulo_actual(p, mods_comp, total_mods),
                "modulo_numero": p.modulo_actual.numero if p.modulo_actual_id else None,
                "modulos_completados": mods_comp,
                "modulos_total": total_mods,
                "avance_pct": avance,
                "modulos_completados_drip": comps_drip,
                "modulos_total_drip": total_drip,
                "avance_pct_drip": avance_drip,
                "max_modulo_alcanzado": max_modulo_alcanzado(p),
                "estado": _estado_progreso(p, avance_drip if total_drip else avance),
                "completado": p.completado,
            }
        )
    return rows


def _posicion_modulo_dashboard(progreso) -> int | str:
    """Módulo «actual» del estudiante para agrupar (0 = sin iniciar, 'completado' = curso listo)."""
    from core.drip_schedule import max_modulo_alcanzado

    if progreso.completado:
        return 'completado'
    mods_comp = progreso.modulos_completados.count() if hasattr(progreso, 'modulos_completados') else 0
    if mods_comp == 0 and not progreso.modulo_actual_id:
        return 0
    if progreso.modulo_actual_id and progreso.modulo_actual:
        return int(progreso.modulo_actual.numero)
    return max_modulo_alcanzado(progreso) or 0


def calcular_distribucion_por_modulo(progreso_q, curso) -> list[dict]:
    """
    Cajas por módulo: cuántos estudiantes están en M1, M2… y su avance promedio
    calculado solo sobre M1..Mn (en M1 antes de M2 → 100% si ya cerraron M1).
    """
    from core.models import Modulo
    from core.drip_schedule import avance_sobre_modulos

    if not curso:
        return []

    mods = list(Modulo.objects.filter(curso=curso).order_by('numero'))
    if not mods:
        return []

    buckets: dict[int | str, dict] = {
        0: {'modulo': 0, 'etiqueta': 'Sin iniciar', 'estudiantes': 0, 'avance_sum': 0},
        'completado': {
            'modulo': 999,
            'etiqueta': 'Curso completado',
            'estudiantes': 0,
            'avance_sum': 0,
        },
    }
    for m in mods:
        buckets[m.numero] = {
            'modulo': m.numero,
            'etiqueta': f'M{m.numero} · {(m.titulo or "")[:36]}',
            'estudiantes': 0,
            'avance_sum': 0,
        }

    qs = progreso_q.select_related('modulo_actual', 'curso').prefetch_related('modulos_completados')
    for p in qs:
        pos = _posicion_modulo_dashboard(p)
        if pos not in buckets:
            pos = int(pos) if pos else 0
        if pos not in buckets:
            continue
        if pos == 'completado':
            mods_subset = mods
        elif pos == 0:
            mods_subset = [mods[0]] if mods else []
        else:
            mods_subset = [m for m in mods if m.numero <= int(pos)]
        _, _, pct = avance_sobre_modulos(p, mods_subset)
        buckets[pos]['estudiantes'] += 1
        buckets[pos]['avance_sum'] += pct

    out = []
    if buckets[0]['estudiantes']:
        n = buckets[0]['estudiantes']
        out.append({
            **buckets[0],
            'promedio_avance_pct': round(buckets[0]['avance_sum'] / n, 1),
        })
    for m in mods:
        b = buckets[m.numero]
        if not b['estudiantes']:
            continue
        n = b['estudiantes']
        out.append({
            **b,
            'promedio_avance_pct': round(b['avance_sum'] / n, 1),
        })
    if buckets['completado']['estudiantes']:
        n = buckets['completado']['estudiantes']
        out.append({
            **buckets['completado'],
            'promedio_avance_pct': round(buckets['completado']['avance_sum'] / n, 1),
        })
    return out


def calcular_metricas_empresa(
    *,
    cliente_id: int | None = None,
    curso_id: int | None = None,
    grupo_id: int | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    modulo_hasta_numero: int | None = None,
    usar_drip_calendario: bool = True,
) -> dict[str, Any]:
    from core.drip_schedule import modulos_para_metricas
    from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante, WhatsappLog
    from core.models_extras import GrupoEstudiantes

    desde_dt = _parse_fecha(desde)
    hasta_dt = _parse_fecha(hasta) or timezone.localdate()

    cliente = None
    if cliente_id:
        cliente = Cliente.objects.filter(pk=cliente_id).first()
    curso = None
    if curso_id:
        curso = Curso.objects.filter(pk=curso_id).first()
    grupo = None
    if grupo_id:
        grupo = GrupoEstudiantes.objects.filter(pk=grupo_id).first()

    progreso_q = ProgresoEstudiante.objects.select_related("estudiante", "curso")
    if cliente_id:
        progreso_q = progreso_q.filter(estudiante__cliente_id=cliente_id)
    if curso_id:
        progreso_q = progreso_q.filter(curso_id=curso_id)
    if grupo_id:
        progreso_q = progreso_q.filter(estudiante__grupos__id=grupo_id).distinct()
    if desde_dt:
        progreso_q = progreso_q.filter(fecha_inicio__date__gte=desde_dt)
    if hasta_dt:
        progreso_q = progreso_q.filter(fecha_inicio__date__lte=hasta_dt)

    if modulo_hasta_numero is not None:
        usar_drip_calendario = False
        from core.drip_schedule import estudiante_llego_hasta_modulo

        cohorte_ids = [
            p.pk
            for p in progreso_q.select_related('modulo_actual', 'curso')
            if estudiante_llego_hasta_modulo(p, modulo_hasta_numero)
        ]
        progreso_q = progreso_q.filter(pk__in=cohorte_ids)

    progreso_q = progreso_q.annotate(n_mods=Count("modulos_completados", distinct=True))

    total_inscritos = progreso_q.count()
    finalizados = progreso_q.filter(completado=True).count()
    en_curso = progreso_q.filter(completado=False, n_mods__gt=0).count()
    no_iniciados = progreso_q.filter(completado=False, n_mods=0).count()

    # Avance sin N+1: annotate n_mods + mapa total módulos por curso;
    # drip usa un prefetch de ModuloCompletado (1 query).
    from collections import defaultdict

    from core.models import Modulo, ModuloCompletado

    progresos = list(progreso_q.select_related("estudiante", "curso")[:5000])
    curso_ids = {p.curso_id for p in progresos if p.curso_id}
    total_mods_por_curso: dict[int, int] = {}
    mods_ordenados_por_curso: dict[int, list] = defaultdict(list)
    if curso_ids:
        for m in Modulo.objects.filter(curso_id__in=curso_ids).order_by("curso_id", "numero"):
            mods_ordenados_por_curso[m.curso_id].append(m)
        for cid, mods in mods_ordenados_por_curso.items():
            total_mods_por_curso[cid] = len(mods)

    prog_ids = [p.pk for p in progresos]
    comps_por_prog: dict[int, set[int]] = defaultdict(set)
    if prog_ids:
        for pid, mid in ModuloCompletado.objects.filter(
            progreso_id__in=prog_ids
        ).values_list("progreso_id", "modulo_id"):
            comps_por_prog[pid].add(mid)

    avance_sum = 0.0
    avance_drip_sum = 0.0
    for p in progresos:
        tm = total_mods_por_curso.get(p.curso_id, 0)
        nm = getattr(p, "n_mods", 0) or 0
        avance_sum += (100.0 * nm / tm) if tm else 0.0

        mods_drip = modulos_para_metricas(
            p.estudiante,
            p.curso,
            modulo_hasta_numero=modulo_hasta_numero,
            usar_drip_calendario=usar_drip_calendario,
        )
        total_drip = len(mods_drip)
        if not total_drip:
            pct_drip = 0
        else:
            ids = {m.id for m in mods_drip}
            comps = len(ids & comps_por_prog.get(p.pk, set()))
            pct_drip = round(comps / total_drip * 100)
        avance_drip_sum += pct_drip
    prom_avance = round(avance_sum / total_inscritos, 1) if total_inscritos else 0.0
    prom_avance_drip = round(avance_drip_sum / total_inscritos, 1) if total_inscritos else 0.0

    whatsapp_q = WhatsappLog.objects.all()
    if desde_dt:
        whatsapp_q = whatsapp_q.filter(fecha__date__gte=desde_dt)
    if hasta_dt:
        whatsapp_q = whatsapp_q.filter(fecha__date__lte=hasta_dt)

    estudiantes_scope = Estudiante.objects.filter(activo=True)
    if cliente_id:
        estudiantes_scope = estudiantes_scope.filter(cliente_id=cliente_id)
    if curso_id:
        estudiantes_scope = estudiantes_scope.filter(progresos__curso_id=curso_id).distinct()
    if grupo_id:
        estudiantes_scope = estudiantes_scope.filter(grupos__id=grupo_id).distinct()

    hace_30 = timezone.now() - timedelta(days=30)
    activos_30d = 0
    if telefonos := list(estudiantes_scope.exclude(telefono='').values_list('telefono', flat=True)):
        tels_variantes = set()
        for tel in telefonos:
            t = normalizar_telefono(tel)
            if t:
                tels_variantes.add(t)
                tels_variantes.update(variantes_telefono(tel))
        if tels_variantes:
            activos_30d = (
                WhatsappLog.objects.filter(
                    telefono__in=list(tels_variantes),
                    fecha__gte=hace_30,
                )
                .values('telefono')
                .distinct()
                .count()
            )

    telefonos = set()
    for tel in estudiantes_scope.exclude(telefono="").values_list("telefono", flat=True):
        t = normalizar_telefono(tel)
        if t:
            telefonos.add(t)
            telefonos.update(variantes_telefono(tel))

    if telefonos:
        whatsapp_q = whatsapp_q.filter(
            Q(estudiante__in=estudiantes_scope) | Q(telefono__in=list(telefonos))
        ).distinct()

    wa_sent = whatsapp_q.filter(tipo="SENT")
    mensajes_enviados = wa_sent.count()
    mensajes_delivered = wa_sent.filter(estado__iexact="DELIVERED").count()
    mensajes_read = wa_sent.filter(estado__iexact="READ").count()

    no_ini_ids = list(
        progreso_q.filter(completado=False, n_mods=0).values_list("estudiante_id", flat=True)
    )
    no_ini_tels = set()
    for tel in Estudiante.objects.filter(id__in=no_ini_ids).exclude(telefono="").values_list(
        "telefono", flat=True
    ):
        no_ini_tels.update(variantes_telefono(tel))

    mensajes_a_no_iniciados = (
        wa_sent.filter(telefono__in=list(no_ini_tels)).count() if no_ini_tels else 0
    )

    pct_final = _pct(finalizados, total_inscritos)
    pct_curso = _pct(en_curso, total_inscritos)
    pct_no_ini = _pct(no_iniciados, total_inscritos)
    pct_inicio = round(100 - pct_no_ini, 1) if total_inscritos else 0.0
    pct_lectura = _pct(mensajes_read, mensajes_enviados)

    metas = resolver_metas_educativa(cliente_id, curso_id)
    metas_pub = {
        k: metas[k]
        for k in ("finalizacion", "inicio", "max_no_iniciados", "lecturas")
    }

    semaforos = {
        "finalizacion": calcular_semaforo(pct_final, metas["finalizacion"], "mayor_es_mejor"),
        "inicio": calcular_semaforo(pct_inicio, metas["inicio"], "mayor_es_mejor"),
        "no_iniciados": calcular_semaforo(pct_no_ini, metas["max_no_iniciados"], "menor_es_mejor"),
        "lectura": calcular_semaforo(pct_lectura, metas["lecturas"], "mayor_es_mejor"),
        "mensajes_sin_inicio": calcular_semaforo(
            _pct(mensajes_a_no_iniciados, max(no_iniciados, 1)),
            100,
            "menor_es_mejor",
        ),
    }

    series_temporal = []
    if desde_dt and hasta_dt:
        wa_dia = (
            wa_sent.annotate(dia=TruncDate("fecha"))
            .values("dia")
            .annotate(total=Count("id"))
            .order_by("dia")
        )
        avance_dia = (
            ProgresoEstudiante.objects.filter(
                id__in=progreso_q.values("id"),
                fecha_ultimo_avance__isnull=False,
            )
            .annotate(dia=TruncDate("fecha_ultimo_avance"))
            .values("dia")
            .annotate(total=Count("id"))
            .order_by("dia")
        )
        wa_map = {r["dia"]: r["total"] for r in wa_dia}
        av_map = {r["dia"]: r["total"] for r in avance_dia}
        d = desde_dt
        while d <= hasta_dt:
            series_temporal.append(
                {
                    "fecha": d.isoformat(),
                    "mensajes_enviados": wa_map.get(d, 0),
                    "avances": av_map.get(d, 0),
                }
            )
            d += timedelta(days=1)

    drip_contexto = None
    if curso:
        from core.models import Modulo

        mods_curso = list(Modulo.objects.filter(curso=curso).order_by("numero"))
        if modulo_hasta_numero is not None:
            mods_filtrados = [m for m in mods_curso if m.numero <= modulo_hasta_numero]
        else:
            mods_filtrados = mods_curso
        drip_contexto = {
            "modulo_hasta_numero": modulo_hasta_numero,
            "usar_drip_calendario": usar_drip_calendario,
            "modulos_curso": [
                {"id": m.id, "numero": m.numero, "titulo": m.titulo} for m in mods_curso
            ],
            "modulos_en_denominador": len(mods_filtrados),
            "etiqueta_denominador": (
                f"Avance M1–M{modulo_hasta_numero} · cohorte que llegó a M{modulo_hasta_numero}"
                if modulo_hasta_numero
                else ("Drip hoy" if usar_drip_calendario else "Todos los módulos")
            ),
            "filtro_cohorte": (
                f"Solo estudiantes que alcanzaron módulo {modulo_hasta_numero} o más"
                if modulo_hasta_numero
                else None
            ),
        }

    return {
        "cliente": {"id": cliente.id, "nombre": cliente.nombre} if cliente else None,
        "curso": {"id": curso.id, "nombre": curso.nombre} if curso else None,
        "grupo": {"id": grupo.id, "nombre": grupo.nombre} if grupo else None,
        "drip": drip_contexto,
        "periodo": {
            "desde": desde_dt.isoformat() if desde_dt else None,
            "hasta": hasta_dt.isoformat() if hasta_dt else None,
        },
        "metas": metas_pub,
        "metas_origen": metas.get("_origen", "sistema"),
        "resumen": {
            "total_inscritos": total_inscritos,
            "finalizados": finalizados,
            "en_curso": en_curso,
            "no_iniciados": no_iniciados,
            "mensajes_enviados": mensajes_enviados,
            "mensajes_delivered": mensajes_delivered,
            "mensajes_read": mensajes_read,
            "mensajes_a_no_iniciados": mensajes_a_no_iniciados,
            "promedio_avance_pct": prom_avance,
            "promedio_avance_drip_pct": prom_avance_drip,
            "activos_ultimos_30_dias": activos_30d,
        },
        "porcentajes": {
            "finalizacion": pct_final,
            "en_curso": pct_curso,
            "no_iniciados": pct_no_ini,
            "inicio": pct_inicio,
            "lectura": pct_lectura,
            "relacion_no_iniciados_mensajes": round(
                no_iniciados / mensajes_enviados, 3
            )
            if mensajes_enviados
            else 0,
        },
        "semaforos": semaforos,
        "semaforo_labels": {k: semaforo_label(v) for k, v in semaforos.items()},
        "series": {
            "por_estado": [
                {"estado": "Sin avance", "total": no_iniciados},
                {"estado": "En curso", "total": en_curso},
                {"estado": "Completado", "total": finalizados},
            ],
            "mensajes_vs_no_iniciados": [
                {"metrica": "No iniciados", "total": no_iniciados},
                {"metrica": "Mensajes enviados", "total": mensajes_enviados},
            ],
            "temporal": series_temporal,
        },
        "progreso_estudiantes": listar_progreso_estudiantes(
            progreso_q,
            modulo_hasta_numero=modulo_hasta_numero,
            usar_drip_calendario=usar_drip_calendario,
        ),
        "distribucion_modulos": calcular_distribucion_por_modulo(progreso_q, curso),
    }


def calcular_metricas_nati(
    *,
    cliente_id: int | None = None,
    desde: str | None = None,
    hasta: str | None = None,
) -> dict[str, Any]:
    from core.models import Cliente, DocumentoRAGComercial, WhatsappLog

    desde_dt = _parse_fecha(desde)
    hasta_dt = _parse_fecha(hasta) or timezone.localdate()

    cliente = Cliente.objects.filter(pk=cliente_id).first() if cliente_id else None

    wa_q = WhatsappLog.objects.filter(agente_usado="BOT_COMERCIAL")
    if desde_dt:
        wa_q = wa_q.filter(fecha__date__gte=desde_dt)
    if hasta_dt:
        wa_q = wa_q.filter(fecha__date__lte=hasta_dt)
    if cliente_id:
        wa_q = wa_q.filter(
            Q(estudiante__cliente_id=cliente_id)
            | Q(estudiante__isnull=True)
        )

    sent = wa_q.filter(tipo="SENT")
    incoming = wa_q.filter(tipo="INCOMING")
    mensajes_enviados = sent.count()
    mensajes_recibidos = incoming.count()
    mensajes_read = sent.filter(estado__iexact="READ").count()
    mensajes_delivered = sent.filter(estado__iexact="DELIVERED").count()
    conversaciones = wa_q.values("telefono").distinct().count()

    rag_q = DocumentoRAGComercial.objects.filter(estado="indexado")
    if cliente_id:
        rag_q = rag_q.filter(Q(cliente_id=cliente_id) | Q(cliente__isnull=True))
    docs_indexados = rag_q.count()
    chunks = sum(rag_q.values_list("chunks_indexados", flat=True)[:500]) or 0

    pct_lectura = _pct(mensajes_read, mensajes_enviados)
    pct_respuesta = _pct(mensajes_enviados, max(mensajes_recibidos, 1))

    metas = resolver_metas_nati(cliente_id)
    metas_pub = {"lectura": metas["lectura"], "respuesta": metas["respuesta"]}

    semaforos = {
        "lectura": calcular_semaforo(pct_lectura, metas["lectura"], "mayor_es_mejor"),
        "respuesta": calcular_semaforo(pct_respuesta, metas["respuesta"], "mayor_es_mejor"),
    }

    series_temporal = []
    if desde_dt and hasta_dt:
        sent_dia = (
            sent.annotate(dia=TruncDate("fecha"))
            .values("dia")
            .annotate(enviados=Count("id"), leidos=Count("id", filter=Q(estado__iexact="READ")))
            .order_by("dia")
        )
        inc_dia = (
            incoming.annotate(dia=TruncDate("fecha"))
            .values("dia")
            .annotate(recibidos=Count("id"))
            .order_by("dia")
        )
        sm = {r["dia"]: r for r in sent_dia}
        im = {r["dia"]: r["recibidos"] for r in inc_dia}
        d = desde_dt
        while d <= hasta_dt:
            row = sm.get(d, {})
            series_temporal.append(
                {
                    "fecha": d.isoformat(),
                    "enviados": row.get("enviados", 0),
                    "leidos": row.get("leidos", 0),
                    "recibidos": im.get(d, 0),
                }
            )
            d += timedelta(days=1)

    return {
        "cliente": {"id": cliente.id, "nombre": cliente.nombre} if cliente else None,
        "periodo": {
            "desde": desde_dt.isoformat() if desde_dt else None,
            "hasta": hasta_dt.isoformat() if hasta_dt else None,
        },
        "metas": metas_pub,
        "metas_origen": metas.get("_origen", "sistema"),
        "resumen": {
            "mensajes_enviados": mensajes_enviados,
            "mensajes_recibidos": mensajes_recibidos,
            "mensajes_delivered": mensajes_delivered,
            "mensajes_read": mensajes_read,
            "conversaciones_unicas": conversaciones,
            "documentos_rag_indexados": docs_indexados,
            "chunks_rag": chunks,
        },
        "porcentajes": {
            "lectura": pct_lectura,
            "respuesta": pct_respuesta,
        },
        "semaforos": semaforos,
        "semaforo_labels": {k: semaforo_label(v) for k, v in semaforos.items()},
        "series": {"temporal": series_temporal},
    }
