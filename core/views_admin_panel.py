"""Panel ejecutivo = Inicio del admin (/admin/)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.timesince import timesince

from core.infra_monitor import header_health_strip
from core.models import Campana, Cliente, Curso, Estudiante, ProgresoEstudiante
from core.views_cobertura_admin import get_cobertura_global


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


def _nodo_status(ok: bool, warn: bool = False) -> str:
    if warn:
        return 'warn'
    return 'ok' if ok else 'empty'


def _build_ecosistema(
    *,
    cursos_activos: int,
    est_activos: int,
    empresas: int,
    campanas_enviadas: int,
    campanas_7d: int,
    certs: int,
    avance: float,
    eventos_ia: int,
    sin_progreso: int,
) -> dict[str, Any]:
    """
    Grafo fijo del ecosistema eki para el home.
    Nodos con contador/estado y aristas fijas (sin motor de grafos).
    """
    nodos = [
        {
            'id': 'studio',
            'label': 'Studio',
            'value': f'{cursos_activos} cursos' if cursos_activos else 'Sin datos',
            'status': _nodo_status(cursos_activos > 0),
            'url': 'https://studio.eki.technology/studio/',
            'external': True,
            'x': 70,
            'y': 48,
        },
        {
            'id': 'aprende',
            'label': 'Aprende',
            'value': f'{est_activos} est.' if est_activos else 'Sin datos',
            'status': _nodo_status(est_activos > 0, warn=sin_progreso >= 5),
            'url': 'https://aprende.eki.technology/aprende/',
            'external': True,
            'x': 210,
            'y': 48,
        },
        {
            'id': 'empresas',
            'label': 'Empresas',
            'value': f'{empresas} activas' if empresas else 'Sin datos',
            'status': _nodo_status(empresas > 0),
            'url': '/admin/core/cliente/',
            'external': False,
            'x': 350,
            'y': 48,
        },
        {
            'id': 'campanas',
            'label': 'Campañas',
            'value': (
                f'{campanas_enviadas} enviadas'
                if campanas_enviadas
                else 'Sin datos'
            ),
            'status': _nodo_status(campanas_enviadas > 0, warn=campanas_enviadas > 0 and campanas_7d == 0),
            'url': '/admin/core/campana/',
            'external': False,
            'x': 490,
            'y': 48,
        },
        {
            'id': 'ia',
            'label': 'IA',
            'value': f'{eventos_ia} eventos' if eventos_ia else 'Sin datos',
            'status': _nodo_status(eventos_ia > 0),
            'url': '/admin/ai-ops/eventos/',
            'external': False,
            'x': 140,
            'y': 168,
        },
        {
            'id': 'impacto',
            'label': 'Impacto',
            'value': (
                f'{certs} certs · {int(round(avance))}%'
                if certs or avance
                else 'Sin datos'
            ),
            'status': _nodo_status(certs > 0 or avance > 0, warn=avance > 0 and avance < 30),
            'url': '/admin/dashboard/?tab=retencion',
            'external': False,
            'x': 400,
            'y': 168,
        },
    ]
    # Aristas: Studio→Aprende→Empresas→Campañas→Impacto; Studio/Aprende→IA; Empresas→Impacto
    edges = [
        ('studio', 'aprende'),
        ('aprende', 'empresas'),
        ('empresas', 'campanas'),
        ('campanas', 'impacto'),
        ('studio', 'ia'),
        ('aprende', 'ia'),
        ('empresas', 'impacto'),
        ('ia', 'impacto'),
    ]
    by_id = {n['id']: n for n in nodos}
    aristas = []
    for a, b in edges:
        na, nb = by_id[a], by_id[b]
        aristas.append({'x1': na['x'], 'y1': na['y'], 'x2': nb['x'], 'y2': nb['y']})
    return {'nodos': nodos, 'aristas': aristas}


def build_panel_snapshot() -> dict[str, Any]:
    """KPIs y bloques del Panel (Inicio) con datos reales."""
    now = timezone.now()
    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    hace_7 = now - timedelta(days=7)

    est_activos = Estudiante.objects.filter(activo=True).count()
    est_ayer = Estudiante.objects.filter(activo=True, fecha_registro__date__lte=ayer).count()
    activos_7d = (
        Estudiante.objects.filter(activo=True)
        .filter(
            Q(progresos__fecha_ultimo_avance__gte=hace_7)
            | Q(
                mensajes_whatsapp__tipo='INCOMING',
                mensajes_whatsapp__fecha__gte=hace_7,
            )
        )
        .distinct()
        .count()
    )

    try:
        from core.models_certificados import Certificado

        certs = Certificado.objects.filter(emitido=True).count()
        certs_ayer = Certificado.objects.filter(
            emitido=True, fecha_emision__date__lte=ayer
        ).count()
        certs_7d = Certificado.objects.filter(
            emitido=True, fecha_emision__gte=hace_7
        ).count()
    except Exception:
        certs = 0
        certs_ayer = 0
        certs_7d = 0

    campanas_enviadas = Campana.objects.filter(ejecutada=True).count()
    campanas_7d = Campana.objects.filter(ejecutada=True, fecha_creacion__gte=hace_7).count()
    avance = _avg_avance_pct()
    empresas = Cliente.objects.filter(activo=True).count()
    empresas_ayer = Cliente.objects.filter(
        activo=True, fecha_registro__date__lte=ayer
    ).count()

    # Misma fuente que el mapa Leaflet (cache 45s)
    mapa = {
        'total_estudiantes': est_activos,
        'departamentos_distintos': 0,
        'municipios_distintos': 0,
        'con_municipio_mapeado': 0,
        'generated_at': '',
    }
    cobertura = []
    depts_con_estudiantes = 0
    try:
        geo = get_cobertura_global(force=False)
        mapa = {
            'total_estudiantes': geo.get('total_estudiantes') or est_activos,
            'departamentos_distintos': geo.get('departamentos_distintos') or 0,
            'municipios_distintos': geo.get('municipios_distintos') or 0,
            'con_municipio_mapeado': geo.get('con_municipio_mapeado') or 0,
            'generated_at': geo.get('generated_at') or '',
        }
        top = geo.get('por_departamento') or []
        max_n = top[0]['cantidad'] if top else 1
        cobertura = [
            {
                'nombre': d['departamento'],
                'n': d['cantidad'],
                'pct': int(round(d['cantidad'] / max_n * 100)) if max_n else 0,
            }
            for d in top[:8]
        ]
        depts_con_estudiantes = mapa['departamentos_distintos']
    except Exception:
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
        depts_con_estudiantes = len(dept_rows)
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
    if depts_con_estudiantes or mapa.get('con_municipio_mapeado'):
        insights.append(
            {
                'nivel': 'info',
                'texto': (
                    f'Mapa live: {mapa.get("con_municipio_mapeado", 0)} estudiantes '
                    f'en mapa · {mapa.get("municipios_distintos", 0)} municipios · '
                    f'{depts_con_estudiantes} departamentos.'
                ),
                'cta': 'Ampliar cobertura',
                'url': '/admin/cobertura/',
            }
        )
    else:
        insights.append(
            {
                'nivel': 'warn',
                'texto': (
                    'Pocos estudiantes con municipio/departamento DANE. '
                    'Sin geo el mapa queda vacío aunque haya activos.'
                ),
                'cta': 'Ver estudiantes',
                'url': '/admin/core/estudiante/',
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

    ecosistema = _build_ecosistema(
        cursos_activos=cursos_activos,
        est_activos=est_activos,
        empresas=empresas,
        campanas_enviadas=campanas_enviadas,
        campanas_7d=campanas_7d,
        certs=certs,
        avance=float(avance or 0),
        eventos_ia=len(actividad),
        sin_progreso=sin_progreso,
    )

    return {
        'kpis': [
            {
                'label': 'Estudiantes activos',
                'value': est_activos,
                'delta': _pct_delta(est_activos, est_ayer),
                'note': f'{activos_7d} con actividad en 7 días',
                'tone': 'purple',
            },
            {
                'label': 'Certificados emitidos',
                'value': certs,
                'delta': _pct_delta(certs, certs_ayer),
                'note': f'{certs_7d} en 7 días' if certs_7d else None,
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
        'activos_7d': activos_7d,
        'depts_activos': depts_con_estudiantes,
        'depts_meta': 32,
        'actividad': actividad,
        'insights': insights,
        'espacios': espacios,
        'acciones': acciones,
        'atajos': atajos,
        'ecosistema': ecosistema,
        'health': header_health_strip(force=False),
    }


@staff_member_required
def admin_panel_view(request):
    """Compat: el Panel vive en Inicio (/admin/)."""
    return redirect('admin:index')
