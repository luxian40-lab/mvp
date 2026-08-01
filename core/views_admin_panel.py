"""Panel ejecutivo = Inicio del admin (/admin/)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.timesince import timesince

from core.infra_monitor import header_health_strip
from core.models import Campana, Cliente, Curso, Estudiante, ProgresoEstudiante


def _pct_delta(hoy: int, ayer: int) -> int | None:
    if ayer <= 0:
        return None if hoy == 0 else 100
    return int(round(((hoy - ayer) / ayer) * 100))


def _relativo(dt) -> str:
    if not dt:
        return ''
    try:
        return f'Hace {timesince(dt, timezone.now()).split(",")[0]}'
    except Exception:
        return ''


def _avg_avance_pct() -> float:
    """% promedio de avance (muestra acotada; evita Avg sobre property)."""
    qs = (
        ProgresoEstudiante.objects.annotate(
            done=Count('modulos_completados', distinct=True),
            total=Count('curso__modulos', distinct=True),
        )
        .filter(total__gt=0)
        .values_list('done', 'total')[:400]
    )
    rows = list(qs)
    if not rows:
        total_p = ProgresoEstudiante.objects.count()
        if not total_p:
            return 0.0
        done = ProgresoEstudiante.objects.filter(completado=True).count()
        return (done / total_p) * 100.0
    return sum((d / t) * 100.0 for d, t in rows) / len(rows)


def build_panel_snapshot() -> dict[str, Any]:
    """KPIs y bloques del Panel (Inicio) con datos reales."""
    now = timezone.now()
    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    hace_7 = now - timedelta(days=7)

    est_activos = Estudiante.objects.filter(activo=True).count()
    est_ayer = Estudiante.objects.filter(activo=True, fecha_registro__date__lte=ayer).count()

    try:
        from core.models_certificados import Certificado

        certs = Certificado.objects.filter(emitido=True).count()
        certs_ayer = Certificado.objects.filter(
            emitido=True, fecha_emision__date__lte=ayer
        ).count()
    except Exception:
        certs = 0
        certs_ayer = 0

    campanas_enviadas = Campana.objects.filter(ejecutada=True).count()
    campanas_7d = Campana.objects.filter(ejecutada=True, fecha_creacion__gte=hace_7).count()
    avance = _avg_avance_pct()
    empresas = Cliente.objects.filter(activo=True).count()
    empresas_ayer = Cliente.objects.filter(
        activo=True, fecha_registro__date__lte=ayer
    ).count()

    mapa = {
        'total_estudiantes': est_activos,
        'departamentos_distintos': 0,
        'municipios_distintos': 0,
        'con_municipio_mapeado': 0,
    }
    dept_rows = list(
        Estudiante.objects.filter(activo=True)
        .exclude(departamento__isnull=True)
        .exclude(departamento='')
        .values('departamento')
        .annotate(n=Count('id'))
        .order_by('-n')[:8]
    )
    max_dept = max((d['n'] for d in dept_rows), default=1)
    cobertura = [
        {
            'nombre': d['departamento'],
            'n': d['n'],
            'pct': int(round(d['n'] / max_dept * 100)),
        }
        for d in dept_rows
    ]
    depts_con_estudiantes = (
        Estudiante.objects.filter(activo=True)
        .exclude(departamento__isnull=True)
        .exclude(departamento='')
        .values('departamento')
        .distinct()
        .count()
    )
    mapa['departamentos_distintos'] = depts_con_estudiantes
    # municipios / mapeados: el mapa Leaflet los carga vía API global (async)
    actividad = []
    try:
        from core.models import EventoIA

        for ev in EventoIA.objects.order_by('-created_at')[:6]:
            actividad.append(
                {
                    'texto': (ev.tipo or 'evento').replace('_', ' '),
                    'cuando': ev.created_at,
                    'relativo': _relativo(ev.created_at),
                }
            )
    except Exception:
        pass
    if not actividad:
        try:
            from core.models import EstudianteEventoAprendizaje

            for ev in EstudianteEventoAprendizaje.objects.select_related('estudiante').order_by(
                '-created_at'
            )[:6]:
                nombre = ''
                if ev.estudiante_id:
                    nombre = (ev.estudiante.nombre or '')[:40]
                actividad.append(
                    {
                        'texto': f"{ev.tipo.replace('_', ' ')}"
                        + (f' · {nombre}' if nombre else ''),
                        'cuando': ev.created_at,
                        'relativo': _relativo(ev.created_at),
                    }
                )
        except Exception:
            pass

    insights = []
    cursos_activos = Curso.objects.filter(activo=True).count()
    sin_progreso = (
        Estudiante.objects.filter(activo=True)
        .annotate(np=Count('progresos'))
        .filter(np=0)
        .count()
    )
    if sin_progreso >= 5:
        insights.append(
            {
                'nivel': 'warn',
                'texto': f'{sin_progreso} estudiantes activos sin progreso de curso.',
                'cta': 'Ver estudiantes',
                'url': '/admin/core/estudiante/',
            }
        )
    if depts_con_estudiantes:
        insights.append(
            {
                'nivel': 'info',
                'texto': (
                    f'Cobertura territorial: {depts_con_estudiantes} departamentos '
                    f'con estudiantes activos (mapa global abajo).'
                ),
                'cta': 'Ampliar cobertura',
                'url': '/admin/cobertura/',
            }
        )
    if cursos_activos:
        insights.append(
            {
                'nivel': 'ok',
                'texto': f'{cursos_activos} cursos activos en catálogo.',
                'cta': 'Ver cursos',
                'url': '/admin/core/curso/',
            }
        )

    espacios = [
        {
            'key': 'aprende',
            'nombre': 'Aprende',
            'desc': 'Aula web y avance de estudiantes',
            'metrics': [
                {'label': 'Cursos', 'value': cursos_activos},
                {'label': 'Estudiantes', 'value': est_activos},
                {'label': 'Avance', 'value': f'{int(round(avance))}%'},
            ],
            'url': 'https://aprende.eki.technology/aprende/',
            'tone': 'green',
            'external': True,
        },
        {
            'key': 'studio',
            'nombre': 'Studio',
            'desc': 'Catálogo, creadores y checkout',
            'metrics': [
                {'label': 'Cursos', 'value': cursos_activos},
                {'label': 'Activos', 'value': cursos_activos},
                {'label': 'Vitrina', 'value': 'Live'},
            ],
            'url': 'https://studio.eki.technology/studio/',
            'tone': 'purple',
            'external': True,
        },
        {
            'key': 'portal',
            'nombre': 'Portal',
            'desc': 'Coordinadores B2B y programas',
            'metrics': [
                {'label': 'Empresas', 'value': empresas},
                {'label': 'Estudiantes', 'value': est_activos},
                {'label': 'Activas', 'value': empresas},
            ],
            'url': 'https://app.eki.technology/portal/',
            'tone': 'blue',
            'external': True,
        },
        {
            'key': 'exito',
            'nombre': 'Centro de Éxito',
            'desc': 'Riesgo, retención e intervenciones',
            'metrics': [
                {'label': 'Insights', 'value': len(insights) or '—'},
                {'label': 'Depts', 'value': depts_con_estudiantes},
                {'label': 'Certs', 'value': certs},
            ],
            'url': '/admin/dashboard/?tab=retencion',
            'tone': 'gold',
            'external': False,
        },
    ]

    acciones = [
        {'label': 'Nuevo curso', 'url': '/admin/core/curso/add/', 'icon': 'school'},
        {'label': 'Nueva campaña', 'url': '/admin/core/campana/add/', 'icon': 'campaign'},
        {'label': 'Nueva empresa', 'url': '/admin/core/cliente/add/', 'icon': 'apartment'},
        {'label': 'Emitir certificados', 'url': '/admin/envio-certificados/', 'icon': 'verified'},
        {'label': 'Dashboard', 'url': '/admin/dashboard/', 'icon': 'dashboard'},
        {'label': 'Logs IA', 'url': '/admin/ai-ops/eventos/', 'icon': 'psychology'},
    ]

    atajos = [
        {'label': 'Ajustar avance', 'url': '/admin/ajustar-avance/', 'icon': 'tune'},
        {'label': 'Conversaciones', 'url': '/admin/conversaciones/', 'icon': 'chat'},
        {'label': 'Push WhatsApp', 'url': '/admin/push-estudiantes/', 'icon': 'send'},
        {'label': 'Certificados', 'url': '/admin/envio-certificados/', 'icon': 'verified'},
        {'label': 'Reportes', 'url': '/admin/dashboard/', 'icon': 'bar_chart'},
        {'label': 'Infra', 'url': '/admin/infra/', 'icon': 'monitor_heart'},
        {'label': 'Estudiantes', 'url': '/admin/core/estudiante/', 'icon': 'group'},
    ]

    return {
        'kpis': [
            {
                'label': 'Estudiantes activos',
                'value': est_activos,
                'delta': _pct_delta(est_activos, est_ayer),
                'tone': 'purple',
            },
            {
                'label': 'Certificados emitidos',
                'value': certs,
                'delta': _pct_delta(certs, certs_ayer),
                'tone': 'green',
            },
            {
                'label': 'Campañas enviadas',
                'value': campanas_enviadas,
                'delta': None,
                'note': f'{campanas_7d} en 7 días' if campanas_7d else None,
                'tone': 'blue',
            },
            {
                'label': 'Avance promedio',
                'value': f'{int(round(float(avance or 0)))}%',
                'delta': None,
                'tone': 'purple',
            },
            {
                'label': 'Empresas activas',
                'value': empresas,
                'delta': _pct_delta(empresas, empresas_ayer)
                if empresas != empresas_ayer
                else None,
                'tone': 'gold',
            },
        ],
        'cobertura': cobertura,
        'mapa': mapa,
        'depts_activos': depts_con_estudiantes,
        'depts_meta': 32,
        'actividad': actividad,
        'insights': insights,
        'espacios': espacios,
        'acciones': acciones,
        'atajos': atajos,
        'health': header_health_strip(force=False),
    }


@staff_member_required
def admin_panel_view(request):
    """Compat: el Panel vive en Inicio (/admin/)."""
    return redirect('admin:index')
