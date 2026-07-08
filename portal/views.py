import json

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Count
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (
    CampanaUnica,
    Curso,
    Estudiante,
    MetaMetricaEmpresa,
    ProgresoEstudiante,
    RespuestaCampanaUnica,
    SolicitudSoporte,
)
from core.models_certificados import Certificado
from core.campana_respuestas import destinatarios_efectivos_qs
from core.models_extras import GrupoEstudiantes
from core.drip_schedule import max_modulo_alcanzado
from core.metricas_empresa import calcular_metricas_empresa
from .authz import requiere_portal_admin
from .curso_flujo_service import embudo_curso_portal
from .capabilities import (
    categorias_pqrs_portal,
    modulos_portal,
    portal_home_url,
    portal_solo_nat,
    puede_editar_config_gei_portal,
    requiere_modulo,
)
from .gei_config import (
    formulario_editable_por_org,
    obtener_formulario_org,
    queryset_formularios_org,
)
from .nat_documentos import crear_documento_nat, listar_documentos_nat
from .metricas_ejecutivas import detalle_estudiantes_learning, resumen_ejecutivo_portal
from .retencion_service import analitica_retencion_portal
from .ranking_portal import ranking_portal
from .exports import (
    filas_reenganche_sin_modulo,
    respuesta_excel_avance_estudiantes,
    respuesta_excel_plantilla,
    validar_filtros_export,
)
from .gei_exports import respuesta_excel_fichas_gei
from .gei_service import analitica_gei, parse_filtros_gei
from .nat_service import analitica_nat
from .middleware import PORTAL_SESSION_KEY
from .utils import limpiar_numero_whatsapp, enviar_whatsapp_respuesta
from .dashboard_ops import comparativa_periodos, operacion_del_dia
from .timeline_service import timeline_organizacion
from .forms_usuarios import CrearUsuarioPortalForm
from .models import PortalFeedback, PortalUsuario
from .rag_curso_service import crear_documento_curso, listar_documentos_curso_org
from .gei_factores import filas_factores_portal


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
        org = request.portal_usuario.organizacion
        return redirect(portal_home_url(org))

    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        from portal.portal_auth import iniciar_sesion_portal, portal_usuario_de_user, puede_acceder_portal

        pu = portal_usuario_de_user(user) if user else None
        if puede_acceder_portal(pu):
            iniciar_sesion_portal(request, pu)
            return redirect(portal_home_url(pu.organizacion))
        error = 'Credenciales incorrectas o usuario sin acceso al portal.'
    return render(request, 'portal/login.html', {'error': error})


def portal_logout(request):
    request.session.pop(PORTAL_SESSION_KEY, None)
    return redirect('/portal/login/')


@portal_login_required
def dashboard(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')
    if portal_solo_nat(org):
        return redirect('/portal/biblioteca/')

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

    ops = None
    comparativa = None
    timeline_preview = []
    if mods['cursos']:
        ops = operacion_del_dia(org, categorias_pqrs=categorias_pqrs_portal(org))
        comparativa = comparativa_periodos(org)
        timeline_preview = timeline_organizacion(org, limite=8)

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
        'ops': ops,
        'comparativa': comparativa,
        'timeline_preview': timeline_preview,
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


def _modulo_facilitador_ia(org):
    mods = modulos_portal(org)
    return mods.get('cursos') or mods.get('gei')


@portal_login_required
@requiere_modulo('gei')
def portal_gei_formularios(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    formularios = []
    for f in queryset_formularios_org(org):
        formularios.append({
            'obj': f,
            'editable': formulario_editable_por_org(f, org, portal_usuario=request.portal_usuario),
            'pasos': f.flujo_pasos.count(),
        })

    return render(request, 'portal/gei_formularios.html', {
        'org': org,
        'formularios': formularios,
        'puede_editar': puede_editar_config_gei_portal(request.portal_usuario),
    })


@portal_login_required
@requiere_modulo('gei')
def portal_gei_formulario_editar(request, formulario_id):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    formulario = obtener_formulario_org(formulario_id, org)
    if not formulario:
        return redirect('/portal/gei/formularios/')

    editable = formulario_editable_por_org(formulario, org, portal_usuario=request.portal_usuario)
    puede_editar = puede_editar_config_gei_portal(request.portal_usuario)
    error = None
    ok = False

    if request.method == 'POST' and editable and puede_editar:
        from formulario.models import FlujoPregunta

        pasos = list(formulario.flujo_pasos.order_by('orden'))
        for paso in pasos:
            prefix = f'paso_{paso.pk}_'
            texto = (request.POST.get(prefix + 'pregunta_texto') or '').strip()
            if texto:
                paso.pregunta_texto = texto
            paso.texto_reintento = (request.POST.get(prefix + 'texto_reintento') or '').strip()
            paso.es_opcional = prefix + 'es_opcional' in request.POST
            paso.save(update_fields=['pregunta_texto', 'texto_reintento', 'es_opcional'])
        ok = True
    elif request.method == 'POST' and not editable:
        error = 'No tiene permiso para editar este formulario.'
    elif request.method == 'POST' and not puede_editar:
        error = 'Solo administrador o profesor del portal pueden guardar cambios.'

    pasos = list(formulario.flujo_pasos.order_by('orden'))
    return render(request, 'portal/gei_formulario_editar.html', {
        'org': org,
        'formulario': formulario,
        'pasos': pasos,
        'editable': editable,
        'puede_editar': puede_editar,
        'error': error,
        'ok': ok,
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
@requiere_modulo('nat')
@requiere_portal_admin
def portal_nat_documentos(request):
    return redirect('/portal/biblioteca/')


@portal_login_required
@requiere_modulo('cursos')
def campanas_lista(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    campanas = []
    for c in CampanaUnica.objects.filter(cliente=org).order_by('-fecha_creacion'):
        campanas.append({
            'obj': c,
            'dest_count': destinatarios_efectivos_qs(c).count(),
        })

    return render(request, 'portal/campanas.html', {
        'org': org,
        'campanas': campanas,
        'portal_es_admin': getattr(request, 'portal_es_admin', False),
    })


@portal_login_required
@requiere_modulo('cursos')
def campana_detalle(request, campana_id):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    campana = get_object_or_404(CampanaUnica, pk=campana_id, cliente=org)
    respuestas = (
        RespuestaCampanaUnica.objects.filter(campana=campana)
        .select_related('estudiante')
        .order_by('-fecha_respuesta')
    )
    resp_si = [r for r in respuestas if r.respuesta == 'si']
    resp_no = [r for r in respuestas if r.respuesta == 'no']
    dest_count = destinatarios_efectivos_qs(campana).count()
    pct_si = round(100 * len(resp_si) / dest_count, 1) if dest_count else 0

    return render(request, 'portal/campana_detalle.html', {
        'org': org,
        'campana': campana,
        'dest_count': dest_count,
        'resp_si': resp_si,
        'resp_no': resp_no,
        'pct_si': pct_si,
        'puede_gestionar': getattr(request, 'portal_es_admin', False),
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

    certificados = Certificado.objects.filter(
        estudiante=estudiante,
    ).select_related('curso').order_by('-fecha_emision')[:20]

    gamificacion = None
    try:
        from core.gamificacion_modo import gamificacion_activa
        if gamificacion_activa(org):
            from core.gamificacion_actions import obtener_estadisticas_estudiante
            gamificacion = obtener_estadisticas_estudiante(estudiante)
    except Exception:
        pass

    mensajes_recientes = []
    try:
        from core.models import WhatsappLog
        if estudiante.telefono:
            mensajes_recientes = list(
                WhatsappLog.objects.filter(telefono=estudiante.telefono)
                .order_by('-fecha')[:6]
            )
    except Exception:
        pass

    return render(request, 'portal/estudiante_detalle.html', {
        'org': org,
        'estudiante': estudiante,
        'progreso_filas': progreso_filas,
        'pqrs': pqrs,
        'grupos': grupos,
        'certificados': certificados,
        'gamificacion': gamificacion,
        'mensajes_recientes': mensajes_recientes,
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
def exportar_avance_excel(request):
    """Excel con avance detallado de estudiantes (mismos filtros que métricas)."""
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    curso_id_int, grupo_id_int = validar_filtros_export(
        org,
        request.GET.get('curso'),
        request.GET.get('grupo'),
    )
    desde = request.GET.get('desde') or None
    hasta = request.GET.get('hasta') or None
    filas = detalle_estudiantes_learning(
        org,
        curso_id=curso_id_int,
        grupo_id=grupo_id_int,
        desde=desde,
        hasta=hasta,
        limite=10000,
    )
    slug = (org.nombre or 'org')[:30].replace(' ', '_')
    return respuesta_excel_avance_estudiantes(
        filas,
        nombre_archivo=f'avance_estudiantes_{slug}.xlsx',
    )


@portal_login_required
def portal_reportes(request):
    """Centro de descargas Excel para la organización."""
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    mods = modulos_portal(org)
    cursos, grupos = _filtros_portal_cursos_grupos(org) if mods.get('cursos') else ([], [])
    gei_filtros = parse_filtros_gei(request, org) if mods.get('gei') else {}

    return render(request, 'portal/reportes.html', {
        'org': org,
        'mods': mods,
        'cursos': cursos,
        'grupos': grupos,
        'gei_filtros': gei_filtros,
        'filtros': {
            'curso': request.GET.get('curso', ''),
            'grupo': request.GET.get('grupo', ''),
            'desde': request.GET.get('desde', ''),
            'hasta': request.GET.get('hasta', ''),
        },
    })


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
def portal_curso_flujo(request, curso_id: int):
    """Embudo de avance por módulo (solo lectura)."""
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    datos = embudo_curso_portal(org, curso_id)
    if datos is None:
        return redirect('/portal/cursos/')

    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    return render(request, 'portal/curso_flujo.html', {
        'org': org,
        'cursos': cursos,
        'datos': datos,
        'curso': datos['curso'],
    })


@portal_login_required
@requiere_modulo('cursos')
def portal_certificados(request):
    """Listado de certificados emitidos por la organización (solo lectura)."""
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    curso_id_raw = request.GET.get('curso') or ''
    curso_id = int(curso_id_raw) if str(curso_id_raw).isdigit() else None
    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    if curso_id and not cursos.filter(pk=curso_id).exists():
        curso_id = None

    qs = (
        Certificado.objects.filter(estudiante__cliente=org)
        .select_related('estudiante', 'curso')
        .order_by('-fecha_emision', '-id')
    )
    if curso_id:
        qs = qs.filter(curso_id=curso_id)

    total_emitidos = qs.filter(emitido=True).count()
    return render(request, 'portal/certificados.html', {
        'org': org,
        'cursos': cursos,
        'certificados': qs[:500],
        'total_emitidos': total_emitidos,
        'filtro_curso': curso_id,
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


@portal_login_required
@requiere_modulo('cursos')
def portal_retencion(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    cursos, grupos = _filtros_portal_cursos_grupos(org)
    curso_id_int = _curso_filtro_portal(request, org, cursos)
    grupo_id = request.GET.get('grupo') or None
    grupo_id_int = int(grupo_id) if grupo_id and str(grupo_id).isdigit() else None
    if grupo_id_int and not grupos.filter(pk=grupo_id_int).exists():
        grupo_id_int = None

    desde = request.GET.get('desde') or ''
    hasta = request.GET.get('hasta') or ''

    data = analitica_retencion_portal(
        org,
        curso_id=curso_id_int,
        grupo_id=grupo_id_int,
        desde=desde or None,
        hasta=hasta or None,
    )

    return render(request, 'portal/retencion.html', {
        'org': org,
        'data': data,
        'cursos': cursos,
        'grupos': grupos,
        'filtros': {
            'curso_id': curso_id_int,
            'grupo_id': grupo_id_int,
            'desde': desde,
            'hasta': hasta,
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
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    from core.gamificacion import Badge, BadgeEstudiante
    from core.gamificacion_modo import gamificacion_activa, get_modo_gamificacion, modo_usa_calificacion

    curso_id = request.GET.get('curso')
    curso_id_int = int(curso_id) if curso_id and str(curso_id).isdigit() else None
    curso_sel = None
    if curso_id_int:
        curso_sel = Curso.objects.filter(pk=curso_id_int, cliente=org).first()

    ranking_data = ranking_portal(org, curso_id=curso_id_int, limite=30)
    modo = get_modo_gamificacion(org)

    medallas_catalogo = []
    if gamificacion_activa(org):
        badges = list(Badge.objects.filter(activo=True).order_by('nombre')[:24])
        counts = {
            row['badge_id']: row['c']
            for row in BadgeEstudiante.objects.filter(
                estudiante__cliente=org,
                badge_id__in=[b.id for b in badges],
            ).values('badge_id').annotate(c=Count('id'))
        }
        for b in badges:
            medallas_catalogo.append({
                'badge': b,
                'otorgadas': counts.get(b.id, 0),
            })

    return render(request, 'portal/gamificacion.html', {
        'org': org,
        'gamificacion_activa': gamificacion_activa(org),
        'modo_label': ranking_data.get('modo_label', ''),
        'es_calificacion': modo_usa_calificacion(org),
        'ranking': ranking_data.get('ranking', []),
        'columna_valor': ranking_data.get('columna_valor', ''),
        'cursos': Curso.objects.filter(cliente=org, activo=True).order_by('nombre'),
        'filtro_curso': curso_id_int,
        'curso_seleccionado': curso_sel,
        'medallas_catalogo': medallas_catalogo,
        'modo': modo,
    })


@portal_login_required
@requiere_modulo('cursos')
def portal_conversaciones(request):
    """Historial WhatsApp de los participantes de la organización."""
    from core.conversaciones_service import construir_contexto_inbox
    from django.contrib import messages

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    puede_responder = request.portal_usuario.rol == 'admin'

    if request.method == 'POST' and puede_responder:
        estudiante_raw = request.POST.get('estudiante_id', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        texto = request.POST.get('mensaje', '').strip()
        est = None
        if estudiante_raw.isdigit():
            est = Estudiante.objects.filter(pk=int(estudiante_raw), cliente=org, activo=True).first()
        if est:
            telefono = est.telefono
        if texto and telefono:
            if enviar_whatsapp_respuesta(telefono, texto):
                messages.success(request, 'Mensaje enviado por WhatsApp.')
            else:
                messages.error(request, 'No se pudo enviar el mensaje. Verifique ventana 24 h o plantilla.')
        redirect_url = '/portal/conversaciones/'
        if est:
            redirect_url += f'?estudiante={est.pk}'
        elif telefono:
            redirect_url += f'?telefono={limpiar_numero_whatsapp(telefono)}'
        return redirect(redirect_url)

    estudiante_raw = (request.GET.get('estudiante') or '').strip()
    estudiante_id = int(estudiante_raw) if estudiante_raw.isdigit() else None
    page_raw = (request.GET.get('page') or '1').strip()
    page = int(page_raw) if page_raw.isdigit() else 1

    context = construir_contexto_inbox(
        estudiante_id=estudiante_id,
        telefono=(request.GET.get('telefono') or '').strip() or None,
        page=page,
        org_fijo=org,
    )
    context.update({
        'org': org,
        'inbox_base_url': '/portal/conversaciones/',
        'inbox_volver_url': '/portal/dashboard/',
        'inbox_volver_label': 'Dashboard',
        'inbox_modo': 'portal',
        'inbox_allow_reply': puede_responder,
    })
    return render(request, 'portal/conversaciones.html', context)


@portal_login_required
@requiere_modulo('cursos')
def portal_timeline(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')
    return render(request, 'portal/timeline.html', {
        'org': org,
        'eventos': timeline_organizacion(org, limite=50),
    })


@portal_login_required
@requiere_portal_admin
def portal_usuarios(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    form = None
    ok_msg = None
    if request.method == 'POST':
        form = CrearUsuarioPortalForm(request.POST)
        if form.is_valid():
            form.save(org)
            return redirect('/portal/usuarios/?creado=1')
    else:
        form = CrearUsuarioPortalForm()

    usuarios = PortalUsuario.objects.filter(organizacion=org).select_related('user').order_by('user__username')
    if request.GET.get('creado'):
        ok_msg = 'Usuario creado correctamente.'

    return render(request, 'portal/usuarios.html', {
        'org': org,
        'form': form,
        'usuarios': usuarios,
        'ok_msg': ok_msg,
    })


@portal_login_required
@requiere_modulo('empleabilidad')
def portal_empleabilidad(request):
    """KPIs de exploración territorial: retención, misiones y oportunidades georef."""
    from .empleabilidad_metricas import resumen_empleabilidad_portal

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    resumen = resumen_empleabilidad_portal(org)
    return render(request, 'portal/empleabilidad.html', {
        'org': org,
        'resumen': resumen,
    })


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

    from .branding import branding_portal_completo, pasos_branding

    return render(request, 'portal/perfil.html', {
        'org': org,
        'puede_editar': puede_editar,
        'mensaje_ok': mensaje_ok,
        'mensaje_error': mensaje_error,
        'branding_completo': branding_portal_completo(org),
        'branding_pasos': pasos_branding(org),
    })


@portal_login_required
def portal_feedback(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    ok = False
    if request.method == 'POST':
        mensaje = (request.POST.get('mensaje') or '').strip()
        categoria = request.POST.get('categoria') or 'mejora'
        if mensaje:
            PortalFeedback.objects.create(
                organizacion=org,
                usuario=request.portal_usuario.user,
                categoria=categoria,
                mensaje=mensaje,
            )
            return redirect('/portal/feedback/?enviado=1')
    if request.GET.get('enviado'):
        ok = True

    return render(request, 'portal/feedback.html', {
        'org': org,
        'ok': ok,
        'categorias': PortalFeedback.CATEGORIA_CHOICES,
    })


@portal_login_required
def portal_conocimiento(request):
    """RAG y preguntas ejemplo IA del curso (facilitadora — no Nat)."""
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')
    if not _modulo_facilitador_ia(org):
        return redirect('/portal/dashboard/')

    mods = modulos_portal(org)
    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('nombre')
    es_admin = request.portal_usuario.rol == 'admin'
    error = None
    ok = False

    curso_sel = None
    curso_raw = request.POST.get('curso_preguntas') or request.GET.get('curso') or ''
    if str(curso_raw).isdigit():
        curso_sel = cursos.filter(pk=int(curso_raw)).first()
    if not curso_sel and cursos.exists():
        curso_sel = cursos.first()

    if request.method == 'POST':
        accion = request.POST.get('accion') or ''
        if accion == 'rag' and mods['cursos']:
            curso_id = request.POST.get('curso') or ''
            curso = None
            if str(curso_id).isdigit():
                curso = cursos.filter(pk=int(curso_id)).first()
            nombre = (request.POST.get('nombre') or '').strip()
            archivo = request.FILES.get('archivo')
            if curso and nombre and archivo:
                try:
                    crear_documento_curso(
                        curso,
                        nombre=nombre,
                        tipo=request.POST.get('tipo') or 'contenido',
                        archivo=archivo,
                        descripcion=(request.POST.get('descripcion') or '').strip(),
                        subido_por=request.portal_usuario.user,
                    )
                    ok = True
                except ValueError as exc:
                    error = str(exc)
            else:
                error = 'Seleccione curso, nombre y archivo.'
        elif accion == 'preguntas_ia' and mods['cursos']:
            if not es_admin:
                error = 'Solo administradores del portal pueden editar las preguntas ejemplo.'
            else:
                curso_id = request.POST.get('curso_preguntas') or ''
                curso = None
                if str(curso_id).isdigit():
                    curso = cursos.filter(pk=int(curso_id)).first()
                if curso:
                    curso.preguntas_ejemplo_ia = (request.POST.get('preguntas_ejemplo_ia') or '').strip()
                    curso.save(update_fields=['preguntas_ejemplo_ia'])
                    curso_sel = curso
                    ok = True
                else:
                    error = 'Seleccione un curso válido.'

    documentos = listar_documentos_curso_org(org) if mods['cursos'] else []

    return render(request, 'portal/conocimiento.html', {
        'org': org,
        'mods': mods,
        'cursos': cursos,
        'curso_sel': curso_sel,
        'es_admin': es_admin,
        'documentos': documentos,
        'tipos_documento': [
            ('contenido', 'Contenido del curso'),
            ('manual', 'Manual'),
            ('faq', 'Preguntas frecuentes'),
            ('guia', 'Guía práctica'),
            ('normativa', 'Normativa'),
        ],
        'error': error,
        'ok': ok,
    })


@portal_login_required
@requiere_modulo('gei')
def portal_gei_parametros(request):
    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    es_admin = puede_editar_config_gei_portal(request.portal_usuario)
    ok = False
    error = None

    if request.method == 'POST' and es_admin:
        from formulario.calculadora import FACTORES

        overrides = dict(org.gei_factores_json or {})
        for key in FACTORES:
            raw = (request.POST.get(f'factor_{key}') or '').strip()
            if raw == '':
                overrides.pop(key, None)
                continue
            try:
                overrides[key] = float(raw.replace(',', '.'))
            except ValueError:
                error = f'Valor inválido para {key}.'
                break
        if not error:
            org.gei_factores_json = overrides
            org.save(update_fields=['gei_factores_json'])
            ok = True

    return render(request, 'portal/gei_parametros.html', {
        'org': org,
        'filas': filas_factores_portal(org),
        'es_admin': es_admin,
        'ok': ok,
        'error': error,
    })


@portal_login_required
@requiere_modulo('nat')
def portal_biblioteca(request):
    from core.biblioteca_nat_service import listar_biblioteca
    from core.models import BibliotecaConocimiento

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    categoria = (request.GET.get('categoria') or '').strip()
    cultivo = (request.GET.get('cultivo') or '').strip()
    q = (request.GET.get('q') or '').strip()
    items = listar_biblioteca(org, categoria=categoria, cultivo=cultivo, q=q)
    bib_flash = request.session.pop('bib_flash', None)

    return render(request, 'portal/biblioteca.html', {
        'org': org,
        'items': items,
        'categorias': BibliotecaConocimiento.CATEGORIA_CHOICES,
        'filtro_categoria': categoria,
        'filtro_cultivo': cultivo,
        'filtro_q': q,
        'total': items.count(),
        'bib_flash': bib_flash,
    })


@portal_login_required
@requiere_modulo('nat')
def portal_biblioteca_crear(request):
    from core.biblioteca_nat_service import crear_desde_formulario
    from core.models import BibliotecaConocimiento

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    error = None
    ok = False
    if request.method == 'POST':
        try:
            crear_desde_formulario(
                org,
                request.POST,
                archivo=request.FILES.get('archivo'),
                user=request.portal_usuario.user,
            )
            ok = True
            return redirect('/portal/biblioteca/')
        except ValueError as exc:
            error = str(exc)

    return render(request, 'portal/biblioteca_form.html', {
        'org': org,
        'item': None,
        'error': error,
        'ok': ok,
        'categorias': BibliotecaConocimiento.CATEGORIA_CHOICES,
        'formatos': BibliotecaConocimiento.FORMATO_CHOICES,
        'niveles': BibliotecaConocimiento.NIVEL_CHOICES,
        'fuentes': BibliotecaConocimiento.FUENTE_CHOICES,
        'estados_pub': BibliotecaConocimiento.ESTADO_PUBLICACION_CHOICES,
    })


@portal_login_required
@requiere_modulo('nat')
def portal_biblioteca_editar(request, item_id: int):
    from core.biblioteca_nat_service import actualizar_item
    from core.models import BibliotecaConocimiento

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    item = get_object_or_404(BibliotecaConocimiento, pk=item_id, cliente=org)
    error = None

    if request.method == 'POST':
        try:
            actualizar_item(item, request.POST, archivo=request.FILES.get('archivo'))
            return redirect('/portal/biblioteca/')
        except ValueError as exc:
            error = str(exc)

    return render(request, 'portal/biblioteca_form.html', {
        'org': org,
        'item': item,
        'error': error,
        'categorias': BibliotecaConocimiento.CATEGORIA_CHOICES,
        'formatos': BibliotecaConocimiento.FORMATO_CHOICES,
        'niveles': BibliotecaConocimiento.NIVEL_CHOICES,
        'fuentes': BibliotecaConocimiento.FUENTE_CHOICES,
        'estados_pub': BibliotecaConocimiento.ESTADO_PUBLICACION_CHOICES,
    })


@portal_login_required
@requiere_modulo('nat')
def portal_biblioteca_reindexar(request, item_id: int):
    from core.biblioteca_nat_service import reindexar_item
    from core.models import BibliotecaConocimiento

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    item = get_object_or_404(BibliotecaConocimiento, pk=item_id, cliente=org)
    if request.method == 'POST':
        n = reindexar_item(item)
        item.refresh_from_db()
        if n > 0:
            request.session['bib_flash'] = f'«{item.titulo}» indexado ({n} fragmentos).'
        else:
            det = item.rag_error_detalle or 'Revise el archivo o agregue un resumen en Artículo.'
            request.session['bib_flash'] = f'No se pudo indexar «{item.titulo}»: {det}'
    return redirect('/portal/biblioteca/')


@portal_login_required
@requiere_modulo('nat')
@requiere_portal_admin
def portal_biblioteca_reindexar_todo(request):
    from core.biblioteca_nat_service import reindexar_publicados

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    if request.method == 'POST':
        ok, err = reindexar_publicados(org)
        request.session['bib_flash'] = f'Reindexación: {ok} correctos, {err} con error.'
    return redirect('/portal/biblioteca/')


@portal_login_required
@requiere_modulo('nat')
def portal_biblioteca_subida_masiva(request):
    from core.biblioteca_nat_service import crear_masivo_desde_archivos
    from core.models import BibliotecaConocimiento

    org = _portal_org(request)
    if not org:
        return redirect('/portal/login/')

    error = None
    if request.method == 'POST':
        archivos = request.FILES.getlist('archivos')
        if not archivos:
            error = 'Seleccione al menos un archivo PDF.'
        elif len(archivos) > 50:
            error = 'Máximo 50 archivos por carga. Divida en tandas.'
        else:
            ok, err = crear_masivo_desde_archivos(
                org,
                archivos,
                user=request.portal_usuario.user,
                categoria=(request.POST.get('categoria') or 'general').strip(),
                cultivo=(request.POST.get('cultivo') or '').strip(),
            )
            request.session['bib_flash'] = (
                f'Subida masiva: {ok} documento(s) en cola de indexación'
                + (f', {err} rechazados.' if err else '. Indexación en segundo plano (1–5 min).')
            )
            return redirect('/portal/biblioteca/')

    return render(request, 'portal/biblioteca_masiva.html', {
        'org': org,
        'error': error,
        'categorias': BibliotecaConocimiento.CATEGORIA_CHOICES,
    })

