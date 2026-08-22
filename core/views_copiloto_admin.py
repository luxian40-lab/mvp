"""Copiloto ops: chat en el admin (JSON) + redirect de la página vieja."""
from __future__ import annotations

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from core.copiloto_ops import responder_copiloto

SESSION_KEY = 'eki_copiloto_chat'
MAX_TURNS = 24

SUGERIDAS = (
    '¿Qué falló en WhatsApp hoy?',
    '¿Hay campañas sin enviar?',
    '¿Cómo va el saldo Twilio?',
    '¿La demo Riendas está cableada?',
)


def _historial(request) -> list:
    raw = request.session.get(SESSION_KEY) or []
    if not isinstance(raw, list):
        return []
    return raw[-MAX_TURNS:]


@staff_member_required
def copiloto_ops_view(request):
    """Ya no es una pestaña: abre el chat del header en Inicio."""
    return redirect('/admin/?copiloto=1')


@staff_member_required
@require_http_methods(['POST'])
def copiloto_ask_view(request):
    pregunta = ''
    if request.content_type and 'application/json' in request.content_type:
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            body = {}
        pregunta = (body.get('pregunta') or '').strip()
    else:
        pregunta = (request.POST.get('pregunta') or '').strip()
    if not pregunta:
        return JsonResponse({'ok': False, 'error': 'Escriba una pregunta.'}, status=400)

    hist = _historial(request)
    out = responder_copiloto(pregunta, historial=hist)
    hist.append({'role': 'user', 'text': pregunta})
    hist.append(
        {
            'role': 'assistant',
            'text': out.get('respuesta') or '',
            'fuente': out.get('fuente') or 'reglas',
        }
    )
    request.session[SESSION_KEY] = hist[-MAX_TURNS:]
    request.session.modified = True
    return JsonResponse(
        {
            'ok': True,
            'respuesta': out.get('respuesta') or '',
            'fuente': out.get('fuente') or 'reglas',
            'historial': request.session[SESSION_KEY],
        }
    )
