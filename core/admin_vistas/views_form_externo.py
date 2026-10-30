"""Webhook: formulario externo (Google Form) → habilitar módulo."""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.form_externo_service import procesar_respuesta_formulario_externo
from core.models_extras import EnlaceFormularioExterno

logger = logging.getLogger(__name__)


def _payload_desde_request(request) -> dict:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return {}
    if request.POST:
        return request.POST.dict()
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


@csrf_exempt
@require_http_methods(['POST'])
def webhook_formulario_externo(request, token: str):
    """
    POST /api/integracion/form-externo/<token>/
    Body JSON: {"cedula": "123"} o {"telefono": "573..."}
    """
    enlace = EnlaceFormularioExterno.objects.filter(token=token, activo=True).select_related(
        'cliente', 'curso', 'modulo',
    ).first()
    if not enlace:
        return JsonResponse({'ok': False, 'mensaje': 'Enlace no válido.'}, status=404)

    secreto = getattr(settings, 'FORM_EXTERNO_WEBHOOK_SECRET', '') or ''
    if secreto:
        header = request.headers.get('X-Eki-Form-Secret', '')
        if header != secreto:
            return JsonResponse({'ok': False, 'mensaje': 'No autorizado.'}, status=403)

    payload = _payload_desde_request(request)
    resultado = procesar_respuesta_formulario_externo(enlace, payload)
    status = 200 if resultado['ok'] else 400
    logger.info('[FormExterno] %s → %s', enlace.nombre, resultado['mensaje'])
    return JsonResponse(resultado, status=status)
