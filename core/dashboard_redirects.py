"""Redirecciones de dashboards legacy al shell unificado (Parte 1)."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from django.urls import reverse

from core.domains.dashboard import LEGACY_DASHBOARD_REDIRECTS


def _build_unified_dashboard_url(request, tab: str, section: str = '') -> str:
    params = request.GET.copy()
    params['tab'] = tab
    if section:
        params['section'] = section
    else:
        params.pop('section', None)
    base = reverse('dashboard_unificado')
    query = params.urlencode()
    return f'{base}?{query}' if query else base


@staff_member_required
def redirect_legacy_dashboard(request, route_key: str):
    """Redirige rutas antiguas a ``/admin/dashboard/`` con tab/section canónicos."""
    mapping = LEGACY_DASHBOARD_REDIRECTS.get(route_key, {'tab': 'executive'})
    tab = mapping.get('tab', 'executive')
    section = mapping.get('section', '')
    return redirect(_build_unified_dashboard_url(request, tab, section))


@staff_member_required
def redirect_dashboard_antiguo(request):
    return redirect_legacy_dashboard(request, 'dashboard_antiguo')


@staff_member_required
def redirect_dashboard_gerencial(request):
    return redirect_legacy_dashboard(request, 'dashboard_gerencial')


@staff_member_required
def redirect_dashboard_metrics(request):
    return redirect_legacy_dashboard(request, 'dashboard_metrics')


@staff_member_required
def redirect_dashboard_analytics(request):
    return redirect_legacy_dashboard(request, 'dashboard_analytics')


@staff_member_required
def redirect_dashboard_reportes(request):
    return redirect_legacy_dashboard(request, 'dashboard_reportes_avanzados')
