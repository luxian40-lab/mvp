import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from calculadora_margen.analytics import (
    EVENTO_APERTURA,
    EVENTO_CALCULO_OK,
    EVENTO_RECOMENDACIONES_OK,
    SESSION_COOKIE,
    atribucion_desde_request,
    registrar_evento,
    session_key,
)
from calculadora_margen.rate_limit import rate_limit_recomendaciones
from calculadora_margen.services.calculo import calcular_margen, margen_para_precio
from calculadora_margen.services.recomendaciones import generar_recomendaciones_ia

logger = logging.getLogger(__name__)


def _parse_json_body(request) -> dict:
    try:
        if request.content_type and 'application/json' in request.content_type:
            return json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return request.POST.dict()


def _set_session_cookie(response, request):
    if SESSION_COOKIE not in request.COOKIES:
        response.set_cookie(SESSION_COOKIE, session_key(request), max_age=60 * 60 * 24 * 30, samesite='Lax')
    return response


@require_GET
def landing(request):
    cliente_id, curso_id = atribucion_desde_request(request)
    ctx = {'curso_id': curso_id}
    response = render(request, 'calculadora_margen/index.html', ctx)
    response = _set_session_cookie(response, request)
    registrar_evento(request, EVENTO_APERTURA)
    return response


@csrf_protect
@require_POST
def api_evento(request):
    """Telemetría desde el front (wizard, simulador, etc.)."""
    data = _parse_json_body(request)
    evento = str(data.get('evento', '')).strip()
    margen_rango = str(data.get('margen_rango', '')).strip()
    meta = data.get('meta') if isinstance(data.get('meta'), dict) else {}
    ok = registrar_evento(request, evento, margen_rango=margen_rango, meta=meta)
    response = JsonResponse({'success': ok})
    return _set_session_cookie(response, request)


@csrf_protect
@require_POST
def api_calcular(request):
    data = _parse_json_body(request)
    try:
        resultado = calcular_margen(
            producto=data.get('producto', ''),
            cantidad_producida=data.get('cantidad_producida'),
            unidad=data.get('unidad', 'unidades'),
            materias_primas=data.get('materias_primas', 0),
            mano_obra=data.get('mano_obra', 0),
            transporte=data.get('transporte', 0),
            empaque=data.get('empaque', 0),
            otros_costos=data.get('otros_costos', 0),
            costos_fijos=data.get('costos_fijos', 0),
            precio_actual=data.get('precio_actual', 0),
        )
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    resultado['success'] = True
    registrar_evento(
        request,
        EVENTO_CALCULO_OK,
        margen_rango=str(resultado.get('nivel_alerta', '')),
    )
    response = JsonResponse(resultado)
    return _set_session_cookie(response, request)


@csrf_protect
@require_POST
def api_recomendaciones(request):
    limited = rate_limit_recomendaciones(request)
    if limited is not None:
        return limited

    data = _parse_json_body(request)
    payload = data.get('datos') or data

    if not payload.get('producto'):
        return JsonResponse({'success': False, 'error': 'Datos insuficientes.'}, status=400)

    try:
        ia = generar_recomendaciones_ia(payload)
    except RuntimeError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    registrar_evento(request, EVENTO_RECOMENDACIONES_OK)
    response = JsonResponse({'success': True, **ia})
    return _set_session_cookie(response, request)


@csrf_protect
@require_POST
def api_simular_precio(request):
    """Recalcula margen para otro precio — sin IA."""
    data = _parse_json_body(request)
    try:
        costo = float(data.get('costo_unitario', 0))
        precio = float(data.get('precio', 0))
        margen = margen_para_precio(costo, precio)
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Datos inválidos.'}, status=400)

    from calculadora_margen.analytics import EVENTO_SIMULO_PRECIO

    registrar_evento(request, EVENTO_SIMULO_PRECIO)
    response = JsonResponse({'success': True, 'margen': margen, 'precio': precio})
    return _set_session_cookie(response, request)
