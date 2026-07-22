"""Vistas HTML del hub semi-admin eki (/portal/ops/)."""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from portal.authz import requiere_eki_ops
from portal.views import portal_login_required


@portal_login_required
@requiere_eki_ops
def portal_eki_ops(request):
    """Home ops = métricas multi-org."""
    return portal_eki_ops_metricas(request)


@portal_login_required
@requiere_eki_ops
@require_GET
def portal_eki_ops_metricas(request):
    from .eki_ops_service import listar_orgs_activas, metricas_por_organizacion, totales_globales

    org_raw = (request.GET.get('org') or '').strip()
    org_id = int(org_raw) if org_raw.isdigit() else None
    filas = metricas_por_organizacion(org_id=org_id)
    return render(request, 'portal/eki_ops_metricas.html', {
        'filas': filas,
        'totales': totales_globales(filas),
        'orgs': listar_orgs_activas(),
        'filtro_org': org_id,
    })


@portal_login_required
@requiere_eki_ops
@require_GET
def portal_eki_ops_metricas_export(request):
    from .eki_ops_service import metricas_por_organizacion, exportar_metricas_excel

    org_raw = (request.GET.get('org') or '').strip()
    org_id = int(org_raw) if org_raw.isdigit() else None
    filas = metricas_por_organizacion(org_id=org_id)
    buf = exportar_metricas_excel(filas)
    stamp = timezone.now().strftime('%Y%m%d')
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="eki_ops_metricas_{stamp}.xlsx"'
    return resp


@portal_login_required
@requiere_eki_ops
def portal_eki_ops_cursos(request):
    """Shell del editor JS de cursos / contenido / microcontenidos."""
    return render(request, 'portal/curso_editor.html')


def _org_filtro(request):
    from .eki_ops_service import listar_orgs_activas

    org_raw = (request.GET.get('org') or request.POST.get('org') or '').strip()
    org_id = int(org_raw) if org_raw.isdigit() else None
    return org_id, listar_orgs_activas()


@portal_login_required
@requiere_eki_ops
@require_GET
def portal_eki_ops_estudiantes(request):
    from core.models import Curso, Estudiante
    from core.models_extras import GrupoEstudiantes

    org_id, orgs = _org_filtro(request)
    qs = Estudiante.objects.select_related('cliente').annotate(
        cursos_count=Count('progresos__curso', distinct=True),
    )
    if org_id:
        qs = qs.filter(cliente_id=org_id)
    qs = qs.order_by('cliente__nombre', 'nombre')[:500]

    grupos = GrupoEstudiantes.objects.filter(activo=True).select_related('cliente')
    cursos = Curso.objects.filter(activo=True).select_related('cliente')
    if org_id:
        grupos = grupos.filter(cliente_id=org_id)
        cursos = cursos.filter(cliente_id=org_id)

    return render(request, 'portal/eki_ops_estudiantes.html', {
        'estudiantes': qs,
        'orgs': orgs,
        'filtro_org': org_id,
        'grupos': grupos.order_by('cliente__nombre', 'nombre')[:200],
        'cursos': cursos.order_by('cliente__nombre', 'nombre')[:200],
    })


@portal_login_required
@requiere_eki_ops
@require_GET
def portal_eki_ops_grupos(request):
    from core.models_extras import GrupoEstudiantes

    org_id, orgs = _org_filtro(request)
    qs = (
        GrupoEstudiantes.objects.filter(activo=True)
        .select_related('cliente')
        .annotate(n_est=Count('estudiantes'))
        .order_by('cliente__nombre', 'nombre')
    )
    if org_id:
        qs = qs.filter(cliente_id=org_id)
    return render(request, 'portal/eki_ops_grupos.html', {
        'grupos': qs[:300],
        'orgs': orgs,
        'filtro_org': org_id,
    })


@portal_login_required
@requiere_eki_ops
@require_http_methods(['GET', 'POST'])
def portal_eki_ops_campanas(request):
    """Listar / crear / lanzar campañas WhatsApp (curso) multi-org."""
    from core.models import Campana, Curso, Plantilla
    from core.models_extras import GrupoEstudiantes
    from core.services import encolar_ejecutar_campana

    org_id, orgs = _org_filtro(request)

    if request.method == 'POST':
        accion = (request.POST.get('accion') or '').strip()
        if accion == 'lanzar':
            campana_id = request.POST.get('campana_id')
            campana = get_object_or_404(Campana, pk=campana_id)
            ok, msg = _validar_y_lanzar_campana(campana, encolar_ejecutar_campana)
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect(
                f'/portal/ops/campanas/?org={org_id}' if org_id else '/portal/ops/campanas/'
            )

        if accion == 'crear':
            ok, msg = _crear_campana_ops(request.POST)
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            org_post = (request.POST.get('cliente_id') or '').strip()
            return redirect(
                f'/portal/ops/campanas/?org={org_post}' if org_post.isdigit() else '/portal/ops/campanas/'
            )

    campanas = Campana.objects.select_related('cliente', 'curso_destino', 'grupo', 'plantilla').order_by('-fecha_creacion')
    if org_id:
        campanas = campanas.filter(cliente_id=org_id)

    filas = []
    for c in campanas[:200]:
        if c.tipo_audiencia == 'grupo' and c.grupo_id:
            dest = c.grupo.estudiantes.filter(activo=True).count()
        else:
            dest = c.destinatarios.filter(activo=True).count()
        filas.append({'obj': c, 'dest_count': dest})

    grupos = GrupoEstudiantes.objects.filter(activo=True).select_related('cliente').order_by('cliente__nombre', 'nombre')
    cursos = Curso.objects.filter(activo=True).select_related('cliente').order_by('cliente__nombre', 'nombre')
    plantillas = Plantilla.objects.filter(activa=True, aprobada_twilio=True).order_by('nombre_interno')[:100]
    if org_id:
        grupos = grupos.filter(cliente_id=org_id)
        cursos = cursos.filter(cliente_id=org_id)

    return render(request, 'portal/eki_ops_campanas.html', {
        'campanas': filas,
        'orgs': orgs,
        'filtro_org': org_id,
        'grupos': grupos[:200],
        'cursos': cursos[:200],
        'plantillas': plantillas,
    })


def _validar_y_lanzar_campana(campana, encolar_fn) -> tuple[bool, str]:
    sid_plantilla = ''
    if campana.plantilla_id:
        p = campana.plantilla
        sid_plantilla = (
            getattr(p, 'twilio_template_sid', None)
            or getattr(p, 'content_sid', None)
            or ''
        )
    if campana.template_twilio_id:
        pass
    elif sid_plantilla and campana.plantilla.aprobada_twilio:
        pass
    else:
        return False, (
            f'«{campana.nombre}»: necesita Content SID de Twilio o plantilla aprobada.'
        )

    if campana.tipo_audiencia == 'grupo':
        if not campana.grupo_id:
            return False, f'«{campana.nombre}»: sin grupo seleccionado.'
        n = campana.grupo.estudiantes.filter(activo=True).count()
    else:
        n = campana.destinatarios.filter(activo=True).count()
    if n == 0:
        return False, f'«{campana.nombre}»: sin destinatarios activos.'

    try:
        modo = encolar_fn(campana.id)
        detalle = 'Celery' if modo == 'celery' else 'background'
        return True, (
            f'Campaña «{campana.nombre}» encolada ({detalle}) → {n} destinatarios.'
        )
    except Exception as exc:
        return False, f'Error al encolar: {exc}'


def _crear_campana_ops(data) -> tuple[bool, str]:
    from core.models import Campana, Cliente, Curso, Estudiante, Plantilla
    from core.models_extras import GrupoEstudiantes

    nombre = (data.get('nombre') or '').strip()
    cliente_id = data.get('cliente_id')
    if not nombre:
        return False, 'Nombre obligatorio.'
    if not cliente_id:
        return False, 'Organización obligatoria.'
    org = Cliente.objects.filter(pk=cliente_id, activo=True).first()
    if not org:
        return False, 'Organización no encontrada.'

    twilio = (data.get('template_twilio_id') or '').strip()
    plantilla_id = data.get('plantilla_id')
    plantilla = None
    if plantilla_id:
        plantilla = Plantilla.objects.filter(pk=plantilla_id, activa=True).first()
    if not twilio and not (
        plantilla
        and plantilla.aprobada_twilio
        and (plantilla.twilio_template_sid or getattr(plantilla, 'content_sid', None))
    ):
        return False, 'Indique Content SID de Twilio o una plantilla aprobada.'

    tipo = (data.get('tipo_audiencia') or 'grupo').strip()
    grupo = None
    if tipo == 'grupo':
        gid = data.get('grupo_id')
        grupo = GrupoEstudiantes.objects.filter(pk=gid, cliente=org, activo=True).first()
        if not grupo:
            return False, 'Seleccione un grupo válido de esa organización.'

    curso = None
    es_curso = bool(data.get('es_campana_curso'))
    if es_curso:
        cid = data.get('curso_id')
        curso = Curso.objects.filter(pk=cid, cliente=org).first()
        if not curso:
            return False, 'Curso destino obligatorio para campaña de inicio de curso.'

    campana = Campana.objects.create(
        nombre=nombre[:100],
        cliente=org,
        template_twilio_id=twilio or None,
        plantilla=plantilla,
        tipo_audiencia='grupo' if tipo == 'grupo' else 'individual',
        grupo=grupo,
        es_campana_curso=es_curso,
        curso_destino=curso,
        canal_envio='whatsapp',
    )
    if tipo != 'grupo':
        ids = list(
            Estudiante.objects.filter(cliente=org, activo=True).values_list('pk', flat=True)[:5000]
        )
        if ids:
            campana.destinatarios.set(ids)
        else:
            campana.delete()
            return False, 'La organización no tiene estudiantes activos.'

    return True, f'Campaña «{campana.nombre}» creada (id={campana.pk}). Puede lanzarla desde la tabla.'
