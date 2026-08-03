"""Mapa de cobertura territorial en admin (misma lógica que portal)."""

from __future__ import annotations

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from core.models import Cliente, Curso

from portal.cobertura_geo import resumen_cobertura_geografica
from portal.geo_catalogo import ruta_geojson_municipios

COBERTURA_GLOBAL_CACHE_KEY = 'eki_cobertura_global_v2'
COBERTURA_GLOBAL_CACHE_SECONDS = 45


def get_cobertura_global(*, force: bool = False) -> dict:
    """Resumen territorial de todos los estudiantes activos (cache corto)."""
    from django.core.cache import cache
    from django.utils import timezone

    if not force:
        try:
            cached = cache.get(COBERTURA_GLOBAL_CACHE_KEY)
            if cached:
                return cached
        except Exception:
            pass

    data = resumen_cobertura_geografica(
        None, None, include_por_curso=False, include_puntos=False
    )
    data['generated_at'] = timezone.now().isoformat()
    try:
        cache.set(COBERTURA_GLOBAL_CACHE_KEY, data, COBERTURA_GLOBAL_CACHE_SECONDS)
    except Exception:
        pass
    return data


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
    # Sin cliente → cobertura global (todos los estudiantes activos)
    resumen = resumen_cobertura_geografica(
        org, None, include_por_curso=bool(org), include_puntos=False
    )
    chart_labels = '[]'
    chart_values = '[]'
    if resumen and resumen.get('por_departamento'):
        chart_labels = json.dumps(
            [d['departamento'] for d in resumen['por_departamento'][:12]],
            ensure_ascii=False,
        )
        chart_values = json.dumps([d['cantidad'] for d in resumen['por_departamento'][:12]])

    return render(request, 'admin/cobertura_mapa.html', {
        'titulo': 'Cobertura territorial' + ('' if org else ' (global)'),
        'clientes': clientes,
        'org': org,
        'cursos': cursos,
        'resumen': resumen,
        'es_global': org is None,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
    })


@staff_member_required
def cobertura_admin_api(request):
    """JSON de cobertura. Sin cliente (o ?global=1) → todos los estudiantes activos."""
    org = _cliente_desde_request(request)
    global_flag = (request.GET.get('global') or '').strip() in ('1', 'true', 'yes')
    force = (request.GET.get('force') or '').strip() in ('1', 'true', 'yes')
    if org is None or global_flag:
        return JsonResponse(get_cobertura_global(force=force))
    return JsonResponse(
        resumen_cobertura_geografica(org, None, include_puntos=False)
    )


@staff_member_required
def cobertura_admin_municipios_geojson(request):
    path = ruta_geojson_municipios()
    if not path.is_file():
        raise Http404('GeoJSON no disponible')
    return FileResponse(path.open('rb'), content_type='application/geo+json')
