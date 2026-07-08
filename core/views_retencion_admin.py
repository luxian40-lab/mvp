"""Admin: panel de retención y embudo (Fase 1 anti-deserción)."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.models import Cliente, Curso
from core.models_extras import GrupoEstudiantes
from portal.retencion_service import analitica_retencion_portal


def _cliente_desde_request(request) -> Cliente | None:
    raw = request.GET.get('cliente') or request.POST.get('cliente')
    if not raw:
        return None
    try:
        return Cliente.objects.get(pk=int(raw), activo=True)
    except (ValueError, Cliente.DoesNotExist):
        return None


def _int_param(request, name: str) -> int | None:
    raw = request.GET.get(name) or request.POST.get(name) or ''
    return int(raw) if str(raw).isdigit() else None


@staff_member_required
def retencion_admin_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    org = _cliente_desde_request(request)
    curso_id_int = _int_param(request, 'curso')
    grupo_id_int = _int_param(request, 'grupo')
    desde = (request.GET.get('desde') or '').strip()
    hasta = (request.GET.get('hasta') or '').strip()

    cursos = Curso.objects.none()
    grupos = GrupoEstudiantes.objects.none()
    data = None

    if org:
        cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
        grupos = GrupoEstudiantes.objects.filter(cliente=org, activo=True).order_by('nombre')
        if curso_id_int and not cursos.filter(pk=curso_id_int).exists():
            curso_id_int = None
        if grupo_id_int and not grupos.filter(pk=grupo_id_int).exists():
            grupo_id_int = None
        data = analitica_retencion_portal(
            org,
            curso_id=curso_id_int,
            grupo_id=grupo_id_int,
            desde=desde or None,
            hasta=hasta or None,
        )

    return render(request, 'admin/retencion.html', {
        'titulo': 'Retención y embudo',
        'clientes': clientes,
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
