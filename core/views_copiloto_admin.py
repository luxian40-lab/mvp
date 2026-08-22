"""Copiloto ops en admin Unfold."""
from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.copiloto_ops import responder_copiloto, snapshot_ops

SUGERIDAS = (
    '¿Qué falló en WhatsApp hoy?',
    '¿Hay campañas sin enviar?',
    '¿Cómo va el saldo Twilio?',
    '¿La demo Riendas está cableada?',
)


@staff_member_required
@require_http_methods(['GET', 'POST'])
def copiloto_ops_view(request):
    pregunta = ''
    resultado = None
    if request.method == 'POST':
        pregunta = (request.POST.get('pregunta') or '').strip()
        resultado = responder_copiloto(pregunta)
    else:
        pregunta = (request.GET.get('q') or '').strip()
        if pregunta:
            resultado = responder_copiloto(pregunta)

    snap = (resultado or {}).get('snapshot') or snapshot_ops()
    return render(
        request,
        'admin/copiloto_ops.html',
        {
            'title': 'Copiloto ops',
            'pregunta': pregunta,
            'resultado': resultado,
            'sugeridas': SUGERIDAS,
            'snap': snap,
        },
    )
