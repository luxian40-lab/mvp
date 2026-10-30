"""JSON de líneas y botón Actualizar del inicio. No calcula el resto de la pantalla."""
from __future__ import annotations

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)


@staff_member_required
@require_GET
def admin_inicio_lineas(request):
    from core.admin.home_data import estado_lineas

    try:
        lineas = estado_lineas()
    except Exception:
        logger.exception('inicio lineas')
        lineas = []
    return JsonResponse({'ok': True, 'lineas': lineas})


@staff_member_required
@require_POST
def admin_inicio_actualizar(request):
    from core.admin.home_data import invalidar_home

    invalidar_home(request.user)
    return redirect('admin:index')
