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
    activos_7d: int,
    empresas: int,
    campanas_enviadas: int,
    campanas_7d: int,
    certs: int,
    avance: float,
    eventos_ia: int,
    eventos_ia_total: int,
    sin_progreso: int,
) -> dict[str, Any]:
    """
    Hub visual del ecosistema eki (Inicio).

    Regla de producto: Studio NO se conecta a Aprende (productos separados).
    Campo WhatsApp es el ancla operativo. Contadores con etiquetas honestas.
    """
    nodos = [
        {
            'id': 'studio',
            'label': 'Studio',
            'metric_label': 'Cursos admin (proxy)',
            'value': f'{cursos_activos} cursos' if cursos_activos else 'Sin datos',
            'status': _nodo_status(cursos_activos > 0),
            'url': 'https://studio.eki.technology/studio/',
            'external': True,
            'icon': 'palette',
            'x': 8,
            'y': 14,
            'z': 8,
            'island': True,
        },
        {
            'id': 'aprende',
            'label': 'Aprende',
            'metric_label': 'Aula web',
            'value': 'Entrar al aula',
            'status': 'ok',
            'url': 'https://aprende.eki.technology/aprende/',
            'external': True,
            'icon': 'menu_book',
            'x': 26,
            'y': 26,
            'z': 18,
            'island': False,
        },
        {
            'id': 'portal',
            'label': 'Portal',
            'metric_label': 'Clientes B2B',
            'value': f'{empresas} orgs' if empresas else 'Entrar',
            'status': _nodo_status(empresas > 0),
            'url': 'https://app.eki.technology/portal/',
            'external': True,
            'icon': 'storefront',
            'x': 42,
            'y': 12,
            'z': 14,
            'island': False,
        },
        {
            'id': 'campo',
            'label': 'Campo',
            'metric_label': 'Estudiantes WA activos',
            'value': (
                f'{est_activos} · {activos_7d} en 7d'
                if est_activos
                else 'Sin datos'
            ),
            'status': _nodo_status(est_activos > 0, warn=sin_progreso >= 5),
            'url': '/admin/core/estudiante/',
            'external': False,
            'icon': 'sms',
            'x': 50,
            'y': 46,
            'z': 48,
            'island': False,
            'anchor': True,
        },
        {
            'id': 'empresas',
            'label': 'Empresas',
            'metric_label': 'Clientes admin',
            'value': f'{empresas} activas' if empresas else 'Sin datos',
            'status': _nodo_status(empresas > 0),
            'url': '/admin/core/cliente/',
            'external': False,
            'icon': 'apartment',
            'x': 70,
            'y': 16,
            'z': 16,
            'island': False,
        },
        {
            'id': 'campanas',
            'label': 'Campañas',
            'metric_label': 'Envíos ejecutados',
            'value': (
                f'{campanas_enviadas} · {campanas_7d} en 7d'
                if campanas_enviadas
                else 'Sin datos'
            ),
            'status': _nodo_status(
                campanas_enviadas > 0,
                warn=campanas_enviadas > 0 and campanas_7d == 0,
            ),
            'url': '/admin/core/campana/',
            'external': False,
            'icon': 'campaign',
            'x': 90,
            'y': 34,
            'z': 22,
            'island': False,
        },
        {
            'id': 'nat',
            'label': 'Nat',
            'metric_label': 'Bot comercial',
            'value': 'CRM / Knowledge',
            'status': 'ok',
            'url': '/admin/dashboard/?tab=commercial',
            'external': False,
            'icon': 'handshake',
            'x': 90,
            'y': 62,
            'z': 18,
            'island': False,
        },
        {
            'id': 'ia',
            'label': 'IA',
            'metric_label': 'Eventos recientes',
            'value': (
                f'{eventos_ia} en feed'
                + (f' · {eventos_ia_total} total' if eventos_ia_total > eventos_ia else '')
                if eventos_ia or eventos_ia_total
                else 'Sin datos'
            ),
            'status': _nodo_status(eventos_ia > 0 or eventos_ia_total > 0),
            'url': '/admin/ai-ops/eventos/',
            'external': False,
            'icon': 'psychology',
            'x': 26,
            'y': 74,
            'z': 12,
            'island': False,
        },
        {
            'id': 'certs',
            'label': 'Certificados',
            'metric_label': 'Emitidos',
            'value': f'{certs} emitidos' if certs else 'Sin datos',
            'status': _nodo_status(certs > 0),
            'url': '/admin/envio-certificados/',
            'external': False,
            'icon': 'workspace_premium',
            'x': 54,
            'y': 78,
            'z': 16,
            'island': False,
        },
        {
            'id': 'impacto',
            'label': 'Éxito',
            'metric_label': 'Centro · avance',
            'value': (
                f'{int(round(avance))}% avance'
                if avance
                else 'Retención'
            ),
            'status': _nodo_status(
                certs > 0 or avance > 0,
                warn=avance > 0 and avance < 30,
            ),
            'url': '/admin/dashboard/?tab=retencion',
            'external': False,
            'icon': 'trending_up',
            'x': 74,
            'y': 80,
            'z': 20,
            'island': False,
        },
        {
            'id': 'infra',
            'label': 'Infra',
            'metric_label': 'Salud plataforma',
            'value': 'Monitor',
            'status': 'ok',
            'url': '/admin/infra/',
            'external': False,
            'icon': 'monitor_heart',
            'x': 8,
            'y': 78,
            'z': 6,
            'island': True,
        },
        {
            'id': 'cobertura',
            'label': 'Cobertura',
            'metric_label': 'Mapa territorial',
            'value': f'{empresas} orgs' if empresas else 'Ver mapa',
            'status': _nodo_status(est_activos > 0 or empresas > 0),
            'url': '/admin/cobertura/',
            'external': False,
            'icon': 'map',
            'x': 12,
            'y': 48,
            'z': 14,
            'island': False,
        },
    ]
    # Studio e Infra aislados: sin aristas. Studio ↛ Aprende.
    edges = [
        ('campo', 'aprende'),
        ('campo', 'portal'),
        ('campo', 'empresas'),
        ('campo', 'campanas'),
        ('campo', 'certs'),
        ('campo', 'impacto'),
        ('campo', 'cobertura'),
        ('cobertura', 'empresas'),
        ('aprende', 'ia'),
        ('portal', 'empresas'),
        ('empresas', 'campanas'),
        ('campanas', 'nat'),
        ('empresas', 'impacto'),
        ('certs', 'impacto'),
        ('ia', 'impacto'),
        ('nat', 'impacto'),
    ]
    by_id = {n['id']: n for n in nodos}
    aristas = []
    for a, b in edges:
        if a in ('studio', 'infra') or b in ('studio', 'infra'):
            continue
        if {a, b} == {'studio', 'aprende'}:
            continue
        na, nb = by_id[a], by_id[b]
        aristas.append(
            {
                'from': a,
                'to': b,
                'x1': na['x'],
                'y1': na['y'],
                'x2': nb['x'],
                'y2': nb['y'],
            }
        )
    return {
        'nodos': nodos,
        'aristas': aristas,
        'nota': (
            'Studio e Infra sin conexiones. '
            'Studio no se conecta a Aprende. '
            'Campo WhatsApp es el centro operativo.'
        ),
    }


def build_panel_snapshot(*, force: bool = False) -> dict[str, Any]:
    """KPIs y bloques del Panel (Inicio). Cache corto para no pesar /admin/."""
    from django.core.cache import cache

    cache_key = 'admin_panel_snapshot_v6'
    if not force:
        cached = cache.get(cache_key)
        if cached:
            return cached
    snap = _build_panel_snapshot_uncached()
    cache.set(cache_key, snap, 45)
    return snap


def _build_panel_snapshot_uncached() -> dict[str, Any]:
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
                'url': '/admin/core/estudiante/?eki_progreso=sin',
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

    acciones = []
    try:
        from core.models import EnvioLog

        n_fallos = EnvioLog.objects.filter(
            estado__in=('FALLIDO', 'ERROR', 'FAILED'),
            fecha_envio__gte=hace_7,
        ).count()
        if n_fallos >= 1:
            acciones.append(
                {
                    'label': f'Envíos fallidos ({n_fallos})',
                    'url': '/admin/core/enviolog/?estado__exact=FALLIDO',
                    'icon': 'error',
                    'destacada': True,
                }
            )
    except Exception:
        pass

    campanas_hoy = Campana.objects.filter(
        ejecutada=False,
        fecha_programada__date=hoy,
    ).count()
    if campanas_hoy:
        acciones.append(
            {
                'label': f'Campañas hoy ({campanas_hoy})',
                'url': '/admin/core/campana/',
                'icon': 'schedule',
                'destacada': True,
            }
        )

    if sin_progreso >= 5:
        acciones.append(
            {
                'label': f'Sin progreso ({sin_progreso})',
                'url': '/admin/core/estudiante/?eki_progreso=sin',
                'icon': 'person_off',
                'destacada': True,
            }
        )

    acciones.extend([
        {'label': 'Nuevo curso', 'url': '/admin/core/curso/add/', 'icon': 'school'},
        {'label': 'Nueva campaña', 'url': '/admin/core/campana/add/', 'icon': 'campaign'},
        {'label': 'Nueva empresa', 'url': '/admin/core/cliente/add/', 'icon': 'apartment'},
        {'label': 'Certificados', 'url': '/admin/envio-certificados/', 'icon': 'verified'},
        {'label': 'Estudiantes', 'url': '/admin/core/estudiante/', 'icon': 'group'},
        {'label': 'Conversaciones', 'url': '/admin/conversaciones/', 'icon': 'chat'},
        {'label': 'Dashboard', 'url': '/admin/dashboard/', 'icon': 'dashboard'},
        {'label': 'Infra', 'url': '/admin/infra/', 'icon': 'monitor_heart'},
    ])
    # Atajos fusionados en acciones (una sola fila de CTAs).
    atajos = []

    eventos_ia_total = 0
    try:
        from core.models import EventoIA

        eventos_ia_total = EventoIA.objects.count()
    except Exception:
        pass

    ecosistema = _build_ecosistema(
        cursos_activos=cursos_activos,
        est_activos=est_activos,
        activos_7d=activos_7d,
        empresas=empresas,
        campanas_enviadas=campanas_enviadas,
        campanas_7d=campanas_7d,
        certs=certs,
        avance=float(avance or 0),
        eventos_ia=len(actividad),
        eventos_ia_total=eventos_ia_total,
        sin_progreso=sin_progreso,
    )

    def _kpi(label, value, *, delta=None, note=None, tone='purple'):
        item = {
            'label': label,
            'value': value,
            'delta': delta,
            'note': note,
            'tone': tone,
        }
        if delta is None:
            item['delta_dir'] = 'flat'
        elif delta > 0:
            item['delta_dir'] = 'up'
        elif delta < 0:
            item['delta_dir'] = 'down'
        else:
            item['delta_dir'] = 'flat'
        return item

    return {
        'kpis': [
            _kpi(
                'Estudiantes activos',
                est_activos,
                delta=_pct_delta(est_activos, est_ayer),
                note=f'{activos_7d} activos 7d',
                tone='purple',
            ),
            _kpi(
                'Certificados',
                certs,
                delta=_pct_delta(certs, certs_ayer),
                note=f'{certs_7d} en 7d' if certs_7d else None,
                tone='green',
            ),
            _kpi(
                'Campañas',
                campanas_enviadas,
                delta=None,
                note=f'{campanas_7d} en 7d' if campanas_7d else 'Sin envíos 7d',
                tone='blue',
            ),
            _kpi(
                'Avance medio',
                f'{int(round(float(avance or 0)))}%',
                delta=None,
                note='Muestra',
                tone='purple',
            ),
            _kpi(
                'Empresas',
                empresas,
                delta=(
                    _pct_delta(empresas, empresas_ayer)
                    if empresas != empresas_ayer
                    else None
                ),
                note=None,
                tone='gold',
            ),
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
        'actualizado': timezone.localtime(now).strftime('%H:%M'),
    }


def unfold_dashboard_callback(request, context):
    """
    Unfold DASHBOARD_CALLBACK nativo: inyecta el Panel ejecutivo en /admin/.
    Reemplaza el monkeypatch de AdminSite.index + el tag eki_panel_snap.
    """
    from django.urls import reverse

    context.update(
        {
            'snap': build_panel_snapshot(),
            'conversaciones_url': reverse('conversaciones'),
            'dashboard_url': reverse('dashboard_unificado'),
            'dashboard_control_url': reverse('dashboard_unificado'),
            'dashboard_analytics_url': reverse('dashboard_analytics'),
        }
    )
    return context


@staff_member_required
def admin_panel_view(request):
    """Compat: el Panel vive en Inicio (/admin/)."""
    return redirect('admin:index')
