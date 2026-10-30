"""Apertura pública /v/<token> y hitos del reproductor propio."""
from __future__ import annotations

import json
import logging

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from core.models_video import VideoEnlace
from core.video_links import (
    HITOS,
    es_prefetch,
    redirect_externo_seguro,
    registrar_apertura,
    registrar_progreso,
    token_valido,
    url_de_reproduccion,
)

logger = logging.getLogger(__name__)


def _buscar_enlace(token: str) -> VideoEnlace | None:
    if not token_valido(token):
        return None
    return VideoEnlace.objects.filter(token=token).first()


@require_GET
def abrir_video(request, token: str):
    """Registra la apertura y luego redirige o muestra el reproductor."""
    enlace = _buscar_enlace(token)
    if enlace is None:
        return HttpResponse('Enlace no encontrado.', status=404, content_type='text/plain; charset=utf-8')

    ua = request.META.get('HTTP_USER_AGENT', '') or ''
    try:
        destino = url_de_reproduccion(enlace)
    except Exception:
        logger.exception('video sin destino reproducible enlace_id=%s', enlace.pk)
        return HttpResponse(
            'No se pudo abrir el video.',
            status=502,
            content_type='text/plain; charset=utf-8',
        )

    if not es_prefetch(ua):
        registrar_apertura(enlace, ua)
        logger.info(
            'video_apertura video_id=%s estudiante_id=%s curso_id=%s',
            enlace.video_id,
            enlace.estudiante_id,
            enlace.curso_id,
        )

    if enlace.destino_tipo == VideoEnlace.DESTINO_EXTERNO:
        if not redirect_externo_seguro(destino):
            return HttpResponse(
                'Destino no permitido.',
                status=400,
                content_type='text/plain; charset=utf-8',
            )
        return HttpResponseRedirect(destino)

    return render(
        request,
        'video/reproductor.html',
        {
            'src': destino,
            'etiqueta': enlace.etiqueta or 'Video',
            'token': enlace.token,
        },
    )


@require_POST
def progreso_video(request, token: str):
    enlace = _buscar_enlace(token)
    if enlace is None:
        return JsonResponse({'ok': False, 'error': 'Enlace no encontrado.'}, status=404)

    if enlace.destino_tipo == VideoEnlace.DESTINO_EXTERNO:
        return JsonResponse(
            {'ok': False, 'error': 'Este video solo registra la apertura del enlace.'},
            status=400,
        )

    hito = _hito_entero(_leer_hito(request))
    if hito not in HITOS:
        return JsonResponse(
            {'ok': False, 'error': 'hito debe ser 25, 50, 75 o 100'},
            status=400,
        )

    _fila, nuevo = registrar_progreso(
        enlace,
        hito,
        request.META.get('HTTP_USER_AGENT', '') or '',
    )
    return JsonResponse({'ok': True, 'evento': HITOS[hito], 'nuevo': nuevo})


def _hito_entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _leer_hito(request):
    ctype = (request.content_type or '').lower()
    if 'json' in ctype:
        try:
            data = json.loads(request.body.decode() or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return data.get('hito')
    return request.POST.get('hito')
