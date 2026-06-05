import json

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Count
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (
    Campana,
    Curso,
    Estudiante,
    MetaMetricaEmpresa,
    ProgresoEstudiante,
    SolicitudSoporte,
)
from core.models_extras import GrupoEstudiantes
from core.drip_schedule import max_modulo_alcanzado
from core.metricas_empresa import calcular_metricas_empresa
from .capabilities import categorias_pqrs_portal, modulos_portal, requiere_modulo
from .metricas_ejecutivas import detalle_estudiantes_learning, resumen_ejecutivo_portal
from .ranking_portal import ranking_portal
from .exports import filas_reenganche_sin_modulo, respuesta_excel_plantilla, validar_filtros_export
from .gei_exports import respuesta_excel_fichas_gei
from .gei_service import analitica_gei, parse_filtros_gei
from .nat_service import analitica_nat
from .middleware import PORTAL_SESSION_KEY
from .utils import limpiar_numero_whatsapp


def _portal_org(request):
    if not getattr(request, 'portal_usuario', None):
        return None
    return request.portal_usuario.organizacion


def portal_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'portal_usuario', None):
            return redirect('/portal/login/')
        return view_func(request, *args, **kwargs)

    return wrapper


def _filtrar_pqrs_por_tipo_proyecto(queryset, org):
    categorias = categorias_pqrs_portal(org)
    if categorias is None:
        return queryset
    return queryset.filter(categoria__in=categorias)


def portal_login(request):
    if getattr(request, 'portal_usuario', None):
        return redirect('/portal/dashboard/')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user and not user.is_staff:
            try:
                portal_usuario = user.portal_usuario
                request.session[PORTAL_SESSION_KEY] = portal_usuario.pk
                return redirect('/portal/dashboard/')
            except Exception:
                error = 'Tu usuario no tiene organización asignada.'
        else:
            error = 'Credenciales incorrectas.'
    return render(request, 'portal/login.html', {'error': error})


def portal_logout(request):
    request.session.pop(PORTAL_SESSION_KEY, None)
    return redirect('/portal/login/')


@portal_login_required
def dashboard(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    mods = modulos_portal(org)
    total_estudiantes = Estudiante.objects.filter(cliente=org).count()
    total_cursos = Curso.objects.filter(cliente=org, activo=True).count()
    total_grupos = GrupoEstudiantes.objects.filter(cliente=org, activo=True).count()
    completados = ProgresoEstudiante.objects.filter(
        curso__cliente=org,
        completado=True,
    ).count()
    en_progreso = ProgresoEstudiante.objects.filter(
        curso__cliente=org,
        completado=False,
    ).count()
    cursos = Curso.objects.filter(cliente=org, activo=True).annotate(
        modulos_count=Count('modulos', distinct=True),
        estudiantes_count=Count('progresoestudiante__estudiante', distinct=True),
    ).order_by('orden')
    grupos = GrupoEstudiantes.objects.filter(cliente=org, activo=True).annotate(
        estudiantes_count=Count('estudiantes', distinct=True),
        cursos_count=Count('cursos', distinct=True),
    ).order_by('nombre')
    resumen_general = {}
    ranking_data = {'activa': False, 'ranking': []}
    if mods['cursos']:
        resumen_general = calcular_metricas_empresa(cliente_id=org.pk).get('resumen', {})
        ranking_data = ranking_portal(org, limite=15)

    gei_resumen = _resumen_gei_portal(org) if mods['gei'] else None
    nat_resumen = analitica_nat(org) if mods['nat'] else None

    return render(request, 'portal/dashboard.html', {
        'org': org,
        'portal_modulos': mods,
        'gei_resumen': gei_resumen,
        'nat_resumen': nat_resumen,
        'total_estudiantes': total_estudiantes,
        'total_cursos': total_cursos,
        'total_grupos': total_grupos,
        'completados': completados,
        'en_progreso': en_progreso,
        'cursos': cursos,
        'grupos': grupos,
        'resumen_general': resumen_general,
        'ranking': ranking_data,
    })


def _resumen_gei_portal(org):
    try:
        from formulario.models import FichaGEI
    except ImportError:
        return None
    qs = FichaGEI.objects.filter(cliente_id=org.pk)
    total = qs.count()
    if not total:
        return {'total': 0, 'completas': 0, 'promedio_pct': 0}
    fichas = list(qs.order_by('-fecha_update')[:500])
    completas = sum(1 for f in fichas if f.completitud_pct >= 100)
    promedio = round(sum(f.completitud_pct for f in fichas) / len(fichas), 1)
    return {'total': total, 'completas': completas, 'promedio_pct': promedio}


@portal_login_required
@requiere_modulo('gei')
def portal_gei(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    filtros = parse_filtros_gei(request, org)
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    data = analitica_gei(org, filtros, page=page)
    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('nombre')

    ctx = {
        'org': org,
        'cursos': cursos,
        'filtros': filtros,
        **data,
        'dist_chart_labels': json.dumps(data.get('dist_chart_labels', []), ensure_ascii=False),
        'dist_chart_values': json.dumps(data.get('dist_chart_values', [])),
        'vars_chart_labels': json.dumps(data.get('vars_chart_labels', []), ensure_ascii=False),
        'vars_chart_values': json.dumps(data.get('vars_chart_values', [])),
    }
    return render(request, 'portal/gei.html', ctx)


@portal_login_required
@requiere_modulo('gei')
def portal_gei_exportar(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')
    filtros = parse_filtros_gei(request, org)
    slug = (org.nombre or 'org')[:24].replace(' ', '_')
    return respuesta_excel_fichas_gei(org, filtros, nombre_archivo=f'gei_{slug}.xlsx')


@portal_login_required
@requiere_modulo('gei')
def portal_gei_detalle(request, ficha_id):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    try:
        from formulario.models import FichaGEI
    except ImportError:
        return redirect('/portal/gei/')

    ficha = get_object_or_404(
        FichaGEI.objects.select_related('estudiante', 'curso', 'resultado'),
        pk=ficha_id,
        cliente_id=org.pk,
    )
    resultado = getattr(ficha, 'resultado', None)
    variables = []
    for campo, label in (
        ('nombre_finca', 'Finca'),
        ('area_ha', 'Área (ha)'),
        ('num_plantas', 'Plantas'),
        ('fertilizante_kg', 'Fertilizante (kg)'),
        ('concentracion_n_pct', '% N'),
        ('combustible_gal', 'Combustible (gal)'),
        ('energia_kwh', 'Energía (kWh)'),
        ('residuos_ton', 'Residuos (ton)'),
        ('produccion_kg', 'Producción (kg)'),
        ('area_bosque_ha', 'Bosque (ha)'),
    ):
        val = getattr(ficha, campo, None)
        variables.append({'label': label, 'valor': val if val not in (None, '') else '—'})

    return render(request, 'portal/gei_detalle.html', {
        'org': org,
        'ficha': ficha,
        'resultado': resultado,
        'variables': variables,
    })


@portal_login_required
@requiere_modulo('nat')
def portal_nat(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    data = analitica_nat(org)
    pqrs = (
        SolicitudSoporte.objects.filter(estudiante__cliente=org)
        .select_related('estudiante')
    )
    pqrs = _filtrar_pqrs_por_tipo_proyecto(pqrs, org).order_by('-fecha_solicitud')[:20]

    return render(request, 'portal/nat.html', {
        'org': org,
        'pqrs_recientes': pqrs,
        **data,
    })


@portal_login_required
@requiere_modulo('cursos')
def campanas_lista(request):
    """Campañas y envíos de la organización (lectura; creación en admin eki)."""
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    campanas = (
        Campana.objects.filter(cliente=org)
        .annotate(dest_count=Count('destinatarios', distinct=True))
        .order_by('-fecha_creacion')[:50]
    )
    return render(request, 'portal/campanas.html', {
        'org': org,
        'campanas': campanas,
        'puede_gestionar': request.portal_usuario.rol == 'admin',
    })


@portal_login_required
@requiere_modulo('cursos')
def campana_detalle(request, campana_id):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    campana = get_object_or_404(
        Campana.objects.filter(cliente=org).prefetch_related('destinatarios'),
        pk=campana_id,
    )
    return render(request, 'portal/campana_detalle.html', {
        'org': org,
        'campana': campana,
        'puede_gestionar': request.portal_usuario.rol == 'admin',
    })


def _filtros_portal_cursos_grupos(org):
    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    grupos = GrupoEstudiantes.objects.filter(cliente=org, activo=True).order_by('nombre')
    return cursos, grupos


@portal_login_required
@requiere_modulo('cursos')
def estudiantes(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    lista = Estudiante.objects.filter(cliente=org).annotate(
        cursos_count=Count('progresos__curso', distinct=True),
    ).order_by('nombre')
    cursos, grupos = _filtros_portal_cursos_grupos(org)
    return render(request, 'portal/estudiantes.html', {
        'org': org,
        'estudiantes': lista,
        'cursos': cursos,
        'grupos': grupos,
    })


@portal_login_required
@requiere_modulo('cursos')
def estudiante_detalle(request, estudiante_id):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    estudiante = get_object_or_404(
        Estudiante.objects.select_related('cliente'),
        pk=estudiante_id,
        cliente=org,
    )
    progresos = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante)
        .select_related('curso', 'modulo_actual')
        .order_by('curso__nombre')
    )
    progreso_filas = []
    for p in progresos:
        progreso_filas.append({
            'progreso': p,
            'max_modulo': max_modulo_alcanzado(p),
            'avance_pct': p.porcentaje_avance(),
            'estado': (
                'Completado' if p.completado
                else ('En curso' if max_modulo_alcanzado(p) > 0 else 'Sin avance')
            ),
        })

    pqrs = _filtrar_pqrs_por_tipo_proyecto(
        SolicitudSoporte.objects.filter(estudiante=estudiante),
        org,
    ).order_by('-fecha_solicitud')[:20]

    grupos = estudiante.grupos.filter(cliente=org).order_by('nombre')

    return render(request, 'portal/estudiante_detalle.html', {
        'org': org,
        'estudiante': estudiante,
        'progreso_filas': progreso_filas,
        'pqrs': pqrs,
        'grupos': grupos,
    })


@portal_login_required
@requiere_modulo('cursos')
def exportar_estudiantes_excel(request):
    """Excel plantilla: estudiantes que no alcanzaron el módulo indicado."""
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    curso_id_int, grupo_id_int = validar_filtros_export(
        org,
        request.GET.get('curso'),
        request.GET.get('grupo'),
    )
    sin_modulo_raw = request.GET.get('sin_modulo') or request.GET.get('modulo') or ''
    sin_modulo = int(sin_modulo_raw) if str(sin_modulo_raw).isdigit() and int(sin_modulo_raw) > 0 else None

    if not sin_modulo:
        return redirect('/portal/estudiantes/?export_error=modulo')

    filas = filas_reenganche_sin_modulo(
        org,
        curso_id=curso_id_int,
        grupo_id=grupo_id_int,
        modulo_objetivo=sin_modulo,
    )
    slug = (org.nombre or 'org')[:30].replace(' ', '_')
    nombre = f'reenganche_sin_modulo_{sin_modulo}_{slug}.xlsx'
    return respuesta_excel_plantilla(filas, nombre_archivo=nombre)


@portal_login_required
@requiere_modulo('cursos')
def cursos_lista(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    lista = Curso.objects.filter(cliente=org).annotate(
        modulos_count=Count('modulos', distinct=True),
        estudiantes_count=Count('progresoestudiante__estudiante', distinct=True),
    ).order_by('orden')
    return render(request, 'portal/cursos.html', {
        'org': org,
        'cursos': lista,
    })


@portal_login_required
@requiere_modulo('cursos')
def metricas_empresa(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')
    puede_configurar = request.portal_usuario.rol == 'admin'

    curso_id = request.GET.get('curso') or None
    grupo_id = request.GET.get('grupo') or None
    desde = request.GET.get('desde') or None
    hasta = request.GET.get('hasta') or None
    modulo_hasta = request.GET.get('modulo_hasta') or None

    cursos, grupos = _filtros_portal_cursos_grupos(org)

    curso_id_int = int(curso_id) if curso_id and str(curso_id).isdigit() else None
    grupo_id_int = int(grupo_id) if grupo_id and str(grupo_id).isdigit() else None
    modulo_hasta_int = int(modulo_hasta) if modulo_hasta and str(modulo_hasta).isdigit() else None

    # Nunca permite que el cliente consulte métricas de otra organización.
    if curso_id_int and not cursos.filter(pk=curso_id_int).exists():
        curso_id_int = None
    if grupo_id_int and not grupos.filter(pk=grupo_id_int).exists():
        grupo_id_int = None

    metas_guardadas = False
    metas_error_lectura = None
    if request.method == 'POST' and not puede_configurar:
        metas_error_lectura = 'Su rol es de solo lectura. No puede modificar metas.'
    elif request.method == 'POST' and puede_configurar:
        meta, _created = MetaMetricaEmpresa.objects.get_or_create(
            cliente=org,
            curso=None,
        )
        for field_name in (
            'meta_finalizacion_porcentaje',
            'meta_inicio_porcentaje',
            'meta_max_no_iniciados_porcentaje',
            'meta_min_lectura_mensajes_porcentaje',
            'verde_desde',
            'amarillo_desde',
        ):
            raw_value = request.POST.get(field_name)
            if raw_value not in (None, ''):
                setattr(meta, field_name, raw_value)
        meta.activa = True
        meta.save()
        metas_guardadas = True

    metricas = calcular_metricas_empresa(
        cliente_id=org.pk,
        curso_id=curso_id_int,
        grupo_id=grupo_id_int,
        desde=desde,
        hasta=hasta,
        modulo_hasta_numero=modulo_hasta_int,
    )
    resumen = metricas.get('resumen', {})
    porcentajes = metricas.get('porcentajes', {})
    resumen_visual = {
        'iniciados': max(
            (resumen.get('total_inscritos') or 0)
            - (resumen.get('no_iniciados') or 0),
            0,
        ),
        'pendientes': (resumen.get('en_curso') or 0) + (resumen.get('no_iniciados') or 0),
        'inscritos_pct': 100 if resumen.get('total_inscritos') else 0,
        'iniciados_pct': porcentajes.get('inicio', 0),
        'en_curso_pct': porcentajes.get('en_curso', 0),
        'finalizados_pct': porcentajes.get('finalizacion', 0),
    }
    meta_config, _created = MetaMetricaEmpresa.objects.get_or_create(
        cliente=org,
        curso=None,
    )

    ejecutivo = resumen_ejecutivo_portal(
        org,
        curso_id=curso_id_int,
        grupo_id=grupo_id_int,
        desde=desde,
        hasta=hasta,
    )
    estudiantes_detalle = detalle_estudiantes_learning(
        org,
        curso_id=curso_id_int,
        grupo_id=grupo_id_int,
        desde=desde,
        hasta=hasta,
    )
    ejecutivo_chart_json = {
        'mensajes_labels': json.dumps(ejecutivo['chart_mensajes_labels'], ensure_ascii=False),
        'mensajes_values': json.dumps(ejecutivo['chart_mensajes_values']),
    }

    return render(request, 'portal/metricas_empresa.html', {
        'org': org,
        'metricas': metricas,
        'resumen': resumen,
        'resumen_visual': resumen_visual,
        'semaforos': metricas.get('semaforos', {}),
        'progreso_estudiantes': metricas.get('progreso_estudiantes', [])[:100],
        'estudiantes_detalle': estudiantes_detalle,
        'ejecutivo': ejecutivo,
        'ejecutivo_chart_json': ejecutivo_chart_json,
        'grupo_seleccionado': grupos.filter(pk=grupo_id_int).first() if grupo_id_int else None,
        'curso_seleccionado': cursos.filter(pk=curso_id_int).first() if curso_id_int else None,
        'distribucion_modulos': metricas.get('distribucion_modulos', []),
        'cursos': cursos,
        'grupos': grupos,
        'metas': metricas.get('metas', {}),
        'meta_config': meta_config,
        'metas_guardadas': metas_guardadas,
        'metas_error_lectura': metas_error_lectura,
        'puede_configurar': puede_configurar,
        'filtros': {
            'curso': curso_id_int,
            'grupo': grupo_id_int,
            'desde': desde or '',
            'hasta': hasta or '',
            'modulo_hasta': modulo_hasta or '',
        },
    })


def _curso_filtro_portal(request, org, cursos):
    curso_id = request.GET.get('curso') or None
    curso_id_int = int(curso_id) if curso_id and str(curso_id).isdigit() else None
    if curso_id_int and not cursos.filter(pk=curso_id_int).exists():
        curso_id_int = None
    return curso_id_int


@portal_login_required
@requiere_modulo('cursos')
def portal_gamificacion(request):
    """Redirige al dashboard (ranking integrado allí)."""
    return redirect('/portal/dashboard/#ranking')


@portal_login_required
@requiere_modulo('cursos')
def portal_cobertura(request):
    """Diversidad territorial: departamentos y municipios del curso."""
    from .cobertura_geo import resumen_cobertura_geografica

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    resumen = resumen_cobertura_geografica(org, None)
    chart_labels = json.dumps(
        [d['departamento'] for d in resumen['por_departamento'][:12]],
        ensure_ascii=False,
    )
    chart_values = json.dumps([d['cantidad'] for d in resumen['por_departamento'][:12]])

    return render(request, 'portal/cobertura.html', {
        'org': org,
        'resumen': resumen,
        'cursos': cursos,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
    })


@portal_login_required
@requiere_modulo('cursos')
def portal_cobertura_api(request):
    """JSON para mapa Leaflet (fase 2: lat/lng por catálogo municipios)."""
    from .cobertura_geo import resumen_cobertura_geografica

    org = _portal_org(request)
    if not org:
        return JsonResponse({'error': 'no auth'}, status=401)

    data = resumen_cobertura_geografica(org, None)
    return JsonResponse(data)


@portal_login_required
@requiere_modulo('cursos')
def portal_cobertura_geojson(request):
    """GeoJSON departamentos Colombia (DANE, estático en el repo)."""
    from .geo_catalogo import ruta_geojson_departamentos

    path = ruta_geojson_departamentos()
    if not path.is_file():
        return JsonResponse({'error': 'geojson no disponible'}, status=404)
    return FileResponse(path.open('rb'), content_type='application/geo+json')


@portal_login_required
@requiere_modulo('cursos')
def portal_cobertura_municipios_geojson(request):
    """GeoJSON municipios simplificado (coroplético portal)."""
    from .geo_catalogo import ruta_geojson_municipios

    path = ruta_geojson_municipios()
    if not path.is_file():
        return JsonResponse({'error': 'geojson municipios no disponible'}, status=404)
    return FileResponse(path.open('rb'), content_type='application/geo+json')


def suscripcion_vencida(request):
    whatsapp_soporte = limpiar_numero_whatsapp(
        getattr(settings, 'TWILIO_WHATSAPP_NUMBER', '')
        or getattr(settings, 'TWILIO_PHONE_NUMBER', '')
    )
    return render(request, 'portal/suscripcion_vencida.html', {
        'whatsapp_soporte': whatsapp_soporte,
    })


@portal_login_required
def pqrs_lista(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    pqrs = SolicitudSoporte.objects.filter(
        estudiante__cliente=org,
    ).select_related('estudiante')
    pqrs = _filtrar_pqrs_por_tipo_proyecto(pqrs, org).order_by('-fecha_solicitud')

    estado = request.GET.get('estado', '')
    if estado:
        pqrs = pqrs.filter(estado=estado)

    total_pendientes = _filtrar_pqrs_por_tipo_proyecto(
        SolicitudSoporte.objects.filter(estudiante__cliente=org, estado='pendiente'),
        org,
    ).count()

    return render(request, 'portal/pqrs_lista.html', {
        'org': org,
        'pqrs': pqrs,
        'estado_filtro': estado,
        'total_pendientes': total_pendientes,
    })


@portal_login_required
def pqrs_detalle(request, pqrs_id):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    base_queryset = _filtrar_pqrs_por_tipo_proyecto(
        SolicitudSoporte.objects.filter(estudiante__cliente=org),
        org,
    )
    pqrs = get_object_or_404(
        base_queryset.select_related('estudiante', 'respondido_por'),
        id=pqrs_id,
    )
    puede_responder = request.portal_usuario.rol == 'admin'
    error_envio = None

    if request.method == 'POST' and puede_responder and pqrs.estado not in ('resuelta', 'cerrada'):
        respuesta = request.POST.get('respuesta', '').strip()
        if respuesta:
            from core.pqrs_respuesta import aplicar_respuesta_pqrs

            ok, error_envio = aplicar_respuesta_pqrs(
                pqrs,
                respuesta,
                request.portal_usuario.user,
            )
            if ok:
                return redirect('/portal/pqrs/')
            if not error_envio:
                error_envio = 'No pudimos enviar la respuesta por WhatsApp. Intenta nuevamente.'

    return render(request, 'portal/pqrs_detalle.html', {
        'org': org,
        'pqrs': pqrs,
        'puede_responder': puede_responder,
        'error_envio': error_envio,
    })


@portal_login_required
def perfil_organizacion(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    puede_editar = request.portal_usuario.rol == 'admin'
    mensaje_ok = None
    mensaje_error = None

    if request.method == 'POST' and puede_editar:
        from .utils import guardar_logo_organizacion

        org.portal_subtitulo = (request.POST.get('portal_subtitulo') or '').strip()[:200]
        logo_url_manual = (request.POST.get('logo_url') or '').strip()
        archivo = request.FILES.get('logo_archivo')

        try:
            if archivo:
                org.logo_url = guardar_logo_organizacion(archivo, org.pk)
            elif logo_url_manual:
                org.logo_url = logo_url_manual
            org.save(update_fields=['logo_url', 'portal_subtitulo'])
            mensaje_ok = 'Perfil de la organización actualizado.'
        except ValueError as exc:
            mensaje_error = str(exc)
        except Exception:
            mensaje_error = 'No se pudo guardar el logo. Intente de nuevo o use una URL.'

    elif request.method == 'POST' and not puede_editar:
        mensaje_error = 'Solo los administradores del portal pueden editar el perfil.'

    return render(request, 'portal/perfil.html', {
        'org': org,
        'puede_editar': puede_editar,
        'mensaje_ok': mensaje_ok,
        'mensaje_error': mensaje_error,
    })
