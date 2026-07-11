"""Admin: retención vive en Dashboard Eki (?tab=retencion)."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect


@staff_member_required
def retencion_admin_view(request):
    """Compat: /admin/retencion/ → Dashboard Eki pestaña Retención."""
    params = request.GET.copy()
    params['tab'] = 'retencion'
    qs = params.urlencode()
    return redirect(f'/admin/dashboard/?{qs}' if qs else '/admin/dashboard/?tab=retencion')
