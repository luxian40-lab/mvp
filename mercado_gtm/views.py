import json
import logging
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from mercado_gtm.models import EscenarioMercado
from mercado_gtm.rate_limit import rate_limit_ia
from mercado_gtm.services.calculos import calcular_escenario_completo, simular
from mercado_gtm.services import ia as ia_svc

logger = logging.getLogger(__name__)

SESSION_COOKIE = 'eki_mercado_sid'


def _parse_json_body(request) -> dict:
    try:
        if request.content_type and 'application/json' in request.content_type:
            return json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return request.POST.dict()


def _sid(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ''


def _set_session_cookie(response, request):
    if SESSION_COOKIE not in request.COOKIES:
        response.set_cookie(
            SESSION_COOKIE, _sid(request), max_age=60 * 60 * 24 * 30, samesite='Lax',
        )
    return response


def _escenario_a_dict(obj: EscenarioMercado) -> dict:
    return {
        'id': obj.pk,
        'nombre_escenario': obj.nombre_escenario,
        'producto': obj.producto,
        'categoria': obj.categoria,
        'presentacion': obj.presentacion,
        'precio': float(obj.precio or 0),
        'unidad_venta': obj.unidad_venta,
        'ubicacion_actual': obj.ubicacion_actual,
        'mercado_objetivo': obj.mercado_objetivo,
        'alcance': obj.alcance,
        'segmentos_cliente': obj.segmentos_cliente or [],
        'ticket_mensual_estimado': float(obj.ticket_mensual_estimado or 0),
        'capacidad_mensual_maxima': (
            float(obj.capacidad_mensual_maxima)
            if obj.capacidad_mensual_maxima is not None else None
        ),
        'tam': float(obj.tam or 0),
        'sam': float(obj.sam or 0),
        'som_conservador': float(obj.som_conservador or 0),
        'som_base': float(obj.som_base or 0),
        'som_ambicioso': float(obj.som_ambicioso or 0),
        'confianza_estimacion': obj.confianza_estimacion,
        'nota_confianza': obj.nota_confianza,
        'trazabilidad': obj.trazabilidad or {},
        'gtm': obj.gtm or {},
        'extraccion': obj.extraccion or {},
    }


def _aplicar_resultado(obj: EscenarioMercado, resultado: dict) -> None:
    for field in (
        'nombre_escenario', 'producto', 'categoria', 'presentacion', 'unidad_venta',
        'ubicacion_actual', 'mercado_objetivo', 'alcance', 'confianza_estimacion',
        'nota_confianza',
    ):
        if field in resultado:
            setattr(obj, field, resultado[field] or getattr(obj, field))

    obj.segmentos_cliente = resultado.get('segmentos_cliente') or []
    obj.precio = Decimal(str(resultado.get('precio') or 0))
    obj.ticket_mensual_estimado = Decimal(str(resultado.get('ticket_mensual_estimado') or 0))
    cap = resultado.get('capacidad_mensual_maxima')
    obj.capacidad_mensual_maxima = Decimal(str(cap)) if cap is not None else None
    for f in ('tam', 'sam', 'som_conservador', 'som_base', 'som_ambicioso'):
        setattr(obj, f, Decimal(str(resultado.get(f) or 0)))
    obj.trazabilidad = resultado.get('trazabilidad') or {}


@require_GET
def landing(request):
    response = render(request, 'mercado_gtm/index.html', {})
    return _set_session_cookie(response, request)


@csrf_protect
@require_POST
def api_extraer(request):
    limited = rate_limit_ia(request)
    if limited is not None:
        return limited

    data = _parse_json_body(request)
    texto = data.get('texto') or data.get('texto_libre') or ''
    try:
        extraccion = ia_svc.extraer_contexto(texto)
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    response = JsonResponse({'success': True, 'extraccion': extraccion})
    return _set_session_cookie(response, request)


@csrf_protect
@require_POST
def api_calcular(request):
    """Motor determinístico — sin IA."""
    data = _parse_json_body(request)
    try:
        segmentos = data.get('segmentos_cliente') or data.get('segmentos') or []
        if isinstance(segmentos, str):
            segmentos = [s.strip() for s in segmentos.split(',') if s.strip()]

        resultado = calcular_escenario_completo(
            producto=data.get('producto', ''),
            precio=data.get('precio', 0),
            ticket_mensual=data.get('ticket_mensual_estimado') or data.get('ticket_mensual'),
            alcance=data.get('alcance', 'local'),
            segmentos=segmentos,
            capacidad_unidades=data.get('capacidad_mensual_maxima') or data.get('capacidad'),
            clientes_estimados=data.get('clientes_estimados'),
            ticket_no_se=bool(data.get('ticket_no_se')),
            ubicacion_actual=data.get('ubicacion_actual', ''),
            mercado_objetivo=data.get('mercado_objetivo', ''),
            categoria=data.get('categoria', ''),
            presentacion=data.get('presentacion', ''),
            unidad_venta=data.get('unidad_venta', 'unidad'),
        )
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    guardar = bool(data.get('guardar', True))
    escenario_id = None
    if guardar:
        obj = EscenarioMercado(session_key=_sid(request))
        if request.user.is_authenticated:
            obj.usuario = request.user
        _aplicar_resultado(obj, resultado)
        if data.get('extraccion') and isinstance(data['extraccion'], dict):
            obj.extraccion = data['extraccion']
        obj.save()
        escenario_id = obj.pk
        resultado['id'] = escenario_id

    resultado['success'] = True
    response = JsonResponse(resultado)
    return _set_session_cookie(response, request)


@csrf_protect
@require_POST
def api_simular(request):
    data = _parse_json_body(request)
    try:
        out = simular(
            sam=data.get('sam'),
            clientes=data.get('clientes'),
            ticket=data.get('ticket'),
            precio=data.get('precio'),
            participacion_pct=data.get('participacion_pct') or data.get('participacion'),
            capacidad_unidades=data.get('capacidad_unidades') or data.get('capacidad'),
        )
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
    out['success'] = True
    return JsonResponse(out)


@csrf_protect
@require_POST
def api_gtm(request):
    limited = rate_limit_ia(request)
    if limited is not None:
        return limited

    data = _parse_json_body(request)
    escenario = data.get('escenario') or data
    if not escenario.get('tam') and data.get('id'):
        obj = get_object_or_404(EscenarioMercado, pk=data['id'])
        escenario = _escenario_a_dict(obj)

    if not escenario.get('tam'):
        return JsonResponse(
            {'success': False, 'error': 'Necesitas un escenario calculado primero.'},
            status=400,
        )

    escenario['recomendar_margen'] = bool(data.get('recomendar_margen'))
    try:
        ia_out = ia_svc.generar_gtm(escenario)
    except RuntimeError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    esc_id = data.get('id') or escenario.get('id')
    if esc_id:
        try:
            obj = EscenarioMercado.objects.get(pk=esc_id)
            obj.gtm = {
                **ia_out.get('gtm', {}),
                'explicacion_embudo': ia_out.get('explicacion_embudo'),
                'segmento_recomendado': ia_out.get('segmento_recomendado'),
                'recomienda_calculadora_margen': ia_out.get('recomienda_calculadora_margen'),
                'nota_margen': ia_out.get('nota_margen'),
            }
            obj.save(update_fields=['gtm', 'actualizado_en'])
        except EscenarioMercado.DoesNotExist:
            pass

    response = JsonResponse({'success': True, **ia_out})
    return _set_session_cookie(response, request)


@csrf_protect
@require_POST
def api_preguntar(request):
    limited = rate_limit_ia(request)
    if limited is not None:
        return limited

    data = _parse_json_body(request)
    pregunta = data.get('pregunta') or data.get('mensaje') or ''
    escenario = data.get('escenario') or {}
    if data.get('id') and not escenario.get('tam'):
        obj = get_object_or_404(EscenarioMercado, pk=data['id'])
        escenario = _escenario_a_dict(obj)

    try:
        out = ia_svc.responder_pregunta(pregunta, escenario)
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    response = JsonResponse({'success': True, **out})
    return _set_session_cookie(response, request)


@require_GET
def api_listar(request):
    """Lista escenarios de la sesión (comparar §22)."""
    from django.db.models import Q

    q = Q(session_key=_sid(request))
    if request.user.is_authenticated:
        q = q | Q(usuario=request.user)
    qs = EscenarioMercado.objects.filter(q).order_by('-actualizado_en')[:20]
    items = [_escenario_a_dict(o) for o in qs]
    return JsonResponse({'success': True, 'escenarios': items})
