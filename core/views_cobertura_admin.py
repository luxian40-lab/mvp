"""Mapa de cobertura territorial en admin (misma lógica que portal)."""

from __future__ import annotations

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from core.models import Cliente, Curso

from portal.cobertura_geo import resumen_cobertura_geografica
from portal.geo_catalogo import ruta_geojson_municipios


def _cliente_desde_request(request) -> Cliente | None:
    raw = request.GET.get('cliente') or request.GET.get('cliente_id')
    if not raw:
        return None
    try:
        return Cliente.objects.get(pk=int(raw))
    except (ValueError, Cliente.DoesNotExist):
        return None


def _curso_id_desde_request(request, org: Cliente | None) -> int | None:
    raw = request.GET.get('curso')
    if not raw or not org:
        return None
    try:
        cid = int(raw)
    except ValueError:
        return None
    if Curso.objects.filter(pk=cid, cliente=org).exists():
        return cid
    return None


@staff_member_required
def cobertura_admin_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    org = _cliente_desde_request(request)
    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre') if org else Curso.objects.none()
    resumen = resumen_cobertura_geografica(org, None) if org else None
    chart_labels = '[]'
    chart_values = '[]'
    if resumen and resumen.get('por_departamento'):
        chart_labels = json.dumps(
            [d['departamento'] for d in resumen['por_departamento'][:12]],
            ensure_ascii=False,
        )
        chart_values = json.dumps([d['cantidad'] for d in resumen['por_departamento'][:12]])

    return render(request, 'admin/cobertura_mapa.html', {
        'titulo': 'Cobertura territorial',
        'clientes': clientes,
        'org': org,
        'cursos': cursos,
        'resumen': resumen,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
    })


@staff_member_required
def cobertura_admin_api(request):
    org = _cliente_desde_request(request)
    if not org:
        return JsonResponse({'error': 'cliente requerido'}, status=400)
    return JsonResponse(resumen_cobertura_geografica(org, None))


@staff_member_required
def cobertura_admin_municipios_geojson(request):
    path = ruta_geojson_municipios()
    if not path.is_file():
        raise Http404('GeoJSON no disponible')
    return FileResponse(path.open('rb'), content_type='application/geo+json')
