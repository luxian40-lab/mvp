"""Legacy URL: redirige a envío certificados unificado."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect


@staff_member_required
def certificados_presenciales_view(request):
    q = request.GET.copy()
    if request.method == 'POST':
        q = request.POST.copy()
    base = '/admin/envio-certificados/'
    return redirect(base + (f'?{q.urlencode()}' if q else ''))
