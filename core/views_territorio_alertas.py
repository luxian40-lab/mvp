"""Panel ops: alertas territoriales (Fase C — solo staff eki)."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.alerta_territorial_ops import (
    build_territorio_alertas_snapshot,
    min_k_default,
    transicionar_alerta,
    ventana_horas_default,
)
from core.models import AlertaTerritorial

logger = logging.getLogger(__name__)

_ACCIONES = {
    'validar': AlertaTerritorial.ESTADO_VALIDADA,
    'comunicar': AlertaTerritorial.ESTADO_COMUNICADA,
    'accionar': AlertaTerritorial.ESTADO_ACCIONADA,
    'cerrar': AlertaTerritorial.ESTADO_CERRADA,
}


@staff_member_required
@require_http_methods(['GET', 'POST'])
def territorio_alertas_view(request):
    if request.method == 'POST':
        accion = (request.POST.get('accion') or '').strip().lower()
        alerta_id = request.POST.get('alerta_id')
        nota = (request.POST.get('nota') or '').strip()
        destino = _ACCIONES.get(accion)
        if not destino or not alerta_id:
            messages.error(request, 'Acción o alerta inválida.')
        else:
            alerta = get_object_or_404(AlertaTerritorial, pk=alerta_id)
            try:
                transicionar_alerta(
                    alerta,
                    nuevo_estado=destino,
                    usuario=request.user,
                    nota=nota,
                )
                messages.success(
                    request,
                    f'Alerta #{alerta.pk} → {destino} ({alerta.familia} @ {alerta.territory_id}).',
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            except Exception:
                logger.exception('territorio_alertas_transicion')
                messages.error(request, 'No se pudo actualizar la alerta.')
        qs = request.GET.urlencode()
        return redirect(request.path + (f'?{qs}' if qs else ''))

    try:
        ventana = int(request.GET.get('ventana') or ventana_horas_default())
    except (TypeError, ValueError):
        ventana = ventana_horas_default()
    ventana = max(1, min(ventana, 24 * 30))
    prefijo = (request.GET.get('familia') or '').strip()

    data = build_territorio_alertas_snapshot(
        ventana_horas=ventana,
        tipo_prefijo=prefijo,
    )
    return render(
        request,
        'admin/territorio_alertas.html',
        {
            'data': data,
            'ventana': ventana,
            'familia': prefijo,
            'min_k': min_k_default(),
            'title': 'Alertas territoriales',
        },
    )
