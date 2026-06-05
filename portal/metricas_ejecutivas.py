"""Métricas ejecutivas y learning analytics del portal (una organización, sin mapa/cobertura)."""
from datetime import datetime, timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.models import Curso, Estudiante, ProgresoEstudiante, WhatsappLog


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _filtros_base(org, curso_id=None, grupo_id=None, desde=None, hasta=None):
    desde_dt = _parse_date(desde)
    hasta_dt = _parse_date(hasta)
    if desde_dt and hasta_dt and desde_dt > hasta_dt:
        desde_dt, hasta_dt = hasta_dt, desde_dt

    estudiantes_q = Estudiante.objects.filter(cliente=org, activo=True)
    if curso_id:
        estudiantes_q = estudiantes_q.filter(progresos__curso_id=curso_id).distinct()
    if desde_dt:
        estudiantes_q = estudiantes_q.filter(fecha_registro__date__gte=desde_dt)
    if hasta_dt:
        estudiantes_q = estudiantes_q.filter(fecha_registro__date__lte=hasta_dt)
    if grupo_id:
        estudiantes_q = estudiantes_q.filter(grupos__id=grupo_id).distinct()

    progreso_q = ProgresoEstudiante.objects.filter(estudiante__cliente=org)
    if curso_id:
        progreso_q = progreso_q.filter(curso_id=curso_id)
    if desde_dt:
        progreso_q = progreso_q.filter(fecha_inicio__date__gte=desde_dt)
    if hasta_dt:
        progreso_q = progreso_q.filter(fecha_inicio__date__lte=hasta_dt)
    if grupo_id:
        progreso_q = progreso_q.filter(estudiante__grupos__id=grupo_id).distinct()

    telefonos = estudiantes_q.exclude(telefono='').values_list('telefono', flat=True)
    whatsapp_q = WhatsappLog.objects.filter(
        Q(estudiante__cliente=org) | Q(telefono__in=telefonos)
    ).distinct()
    if desde_dt:
        whatsapp_q = whatsapp_q.filter(fecha__date__gte=desde_dt)
    if hasta_dt:
        whatsapp_q = whatsapp_q.filter(fecha__date__lte=hasta_dt)

    return estudiantes_q, progreso_q, whatsapp_q, desde_dt, hasta_dt


def resumen_ejecutivo_portal(org, curso_id=None, grupo_id=None, desde=None, hasta=None):
    """KPIs y gráficos ejecutivos (sin datos geográficos — eso va en Cobertura)."""
    estudiantes_q, progreso_q, whatsapp_q, desde_dt, hasta_dt = _filtros_base(
        org, curso_id, grupo_id, desde, hasta
    )

    progreso_filter_q = Q(progresoestudiante__id__in=progreso_q.values('id'))
    progreso_por_curso_qs = Curso.objects.filter(cliente=org, activo=True)
    if curso_id:
        progreso_por_curso_qs = progreso_por_curso_qs.filter(id=curso_id)

    progreso_por_curso = []
    for curso in progreso_por_curso_qs.annotate(
        total_estudiantes=Count('progresoestudiante', filter=progreso_filter_q, distinct=True),
        completados=Count(
            'progresoestudiante',
            filter=progreso_filter_q & Q(progresoestudiante__completado=True),
            distinct=True,
        ),
    ).order_by('orden', 'nombre'):
        total = curso.total_estudiantes or 0
        comp = curso.completados or 0
        pct = round(comp / total * 100, 1) if total else 0
        progreso_por_curso.append({
            'nombre': curso.nombre,
            'total_estudiantes': total,
            'completados': comp,
            'pct': pct,
        })

    total_estudiantes = estudiantes_q.count()
    total_cursos = progreso_por_curso_qs.count()
    cursos_completados = progreso_q.filter(completado=True).count()
    total_inscripciones = progreso_q.count()
    tasa_completacion = (
        round(cursos_completados / total_inscripciones * 100, 1) if total_inscripciones else 0
    )

    total_certificados = 0
    try:
        from core.models_certificados import Certificado

        cert_q = Certificado.objects.filter(estudiante__cliente=org)
        if curso_id:
            cert_q = cert_q.filter(curso_id=curso_id)
        if desde_dt:
            cert_q = cert_q.filter(fecha_emision__date__gte=desde_dt)
        if hasta_dt:
            cert_q = cert_q.filter(fecha_emision__date__lte=hasta_dt)
        total_certificados = cert_q.count()
    except Exception:
        pass

    puntos_promedio = 0
    try:
        from core.gamificacion import PerfilGamificacion

        puntos_promedio = (
            PerfilGamificacion.objects.filter(estudiante__in=estudiantes_q)
            .aggregate(avg=Avg('puntos_totales'))['avg']
            or 0
        )
    except Exception:
        pass

    hoy = hasta_dt or timezone.localdate()
    hace_7 = hoy - timedelta(days=6)
    mensajes_por_dia = (
        whatsapp_q.filter(fecha__date__gte=hace_7, fecha__date__lte=hoy)
        .annotate(dia=TruncDate('fecha'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    mensajes_map = {m['dia']: int(m['total']) for m in mensajes_por_dia}
    chart_labels = []
    chart_values = []
    for i in range(7):
        dia = hoy - timedelta(days=6 - i)
        chart_labels.append(dia.strftime('%d/%m'))
        chart_values.append(mensajes_map.get(dia, 0))

    return {
        'total_estudiantes': total_estudiantes,
        'total_cursos': total_cursos,
        'tasa_completacion': tasa_completacion,
        'cursos_completados': cursos_completados,
        'total_inscripciones': total_inscripciones,
        'total_certificados': total_certificados,
        'progreso_por_curso': progreso_por_curso,
        'total_mensajes_whatsapp': whatsapp_q.count(),
        'mensajes_enviados': whatsapp_q.filter(tipo='SENT').count(),
        'mensajes_recibidos': whatsapp_q.filter(tipo='INCOMING').count(),
        'wa_entregados': whatsapp_q.filter(tipo='SENT', estado__iexact='DELIVERED').count(),
        'wa_leidos': whatsapp_q.filter(tipo='SENT', estado__iexact='READ').count(),
        'total_audios': whatsapp_q.filter(es_audio=True).count(),
        'total_agentes_ia': whatsapp_q.filter(agente_usado__isnull=False).exclude(agente_usado='').count(),
        'puntos_promedio': round(float(puntos_promedio), 1),
        'chart_mensajes_labels': chart_labels,
        'chart_mensajes_values': chart_values,
    }


def detalle_estudiantes_learning(org, curso_id=None, grupo_id=None, desde=None, hasta=None, limite=150):
    """Tabla detalle por estudiante (Learning Analytics / reportes B2B del admin)."""
    estudiantes_q, progreso_q, _, _, _ = _filtros_base(org, curso_id, grupo_id, desde, hasta)

    est_ids = list(estudiantes_q.values_list('id', flat=True)[:limite])
    if not est_ids:
        return []

    puntos_map = {}
    try:
        from core.gamificacion import PerfilGamificacion

        puntos_map = dict(
            PerfilGamificacion.objects.filter(estudiante_id__in=est_ids).values_list(
                'estudiante_id', 'puntos_totales'
            )
        )
    except Exception:
        pass

    progresos = (
        progreso_q.filter(estudiante_id__in=est_ids)
        .select_related('estudiante', 'curso', 'modulo_actual')
        .prefetch_related('estudiante__grupos')
        .annotate(
            total_mods=Count('curso__modulos', distinct=True),
            mods_comp=Count('modulos_completados', distinct=True),
        )
        .order_by('estudiante__nombre', 'curso__nombre')
    )

    filas = []
    seen = set()
    for progreso in progresos:
        est = progreso.estudiante
        seen.add(est.id)
        total_mods = progreso.total_mods or 0
        mods_comp = progreso.mods_comp or 0
        avance = round(mods_comp / total_mods * 100) if total_mods else 0
        if progreso.completado:
            estado = 'Completado'
            modulo_txt = 'Curso completado'
        elif progreso.modulo_actual_id and progreso.modulo_actual:
            estado = 'En curso'
            m = progreso.modulo_actual
            modulo_txt = f'M{m.numero} · {m.titulo}'
        elif avance > 0:
            estado = 'En curso'
            modulo_txt = f'En curso ({mods_comp}/{total_mods} módulos)'
        else:
            estado = 'Sin avance'
            modulo_txt = 'Sin iniciar'
        grupos_txt = ', '.join(sorted(g.nombre for g in est.grupos.all())) or '—'
        filas.append({
            'estudiante_id': est.id,
            'nombre': est.nombre,
            'cedula': est.cedula or '—',
            'telefono': (est.telefono or '').strip() or '—',
            'grupos': grupos_txt,
            'curso': progreso.curso.nombre if progreso.curso_id else '—',
            'modulo_actual': modulo_txt,
            'modulos_completados': f'{mods_comp}/{total_mods}' if total_mods else '—',
            'estado_avance': estado,
            'avance': avance,
            'puntos': puntos_map.get(est.id, 0),
        })

    for est in estudiantes_q.filter(id__in=est_ids).exclude(id__in=seen):
        grupos_txt = ', '.join(sorted(g.nombre for g in est.grupos.all())) or '—'
        filas.append({
            'estudiante_id': est.id,
            'nombre': est.nombre,
            'cedula': est.cedula or '—',
            'telefono': (est.telefono or '').strip() or '—',
            'grupos': grupos_txt,
            'curso': '—',
            'modulo_actual': '—',
            'modulos_completados': '—',
            'estado_avance': 'Sin inscripción',
            'avance': 0,
            'puntos': puntos_map.get(est.id, 0),
        })

    return filas
