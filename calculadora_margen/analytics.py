"""Telemetría agregada de la calculadora margen (sin PII ni montos)."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Optional

from django.http import HttpRequest

from calculadora_margen.links import resolver_cliente_id, urls_margen_cliente

EVENTO_APERTURA = 'apertura'
EVENTO_INICIO_WIZARD = 'inicio_wizard'
EVENTO_CALCULO_OK = 'calculo_ok'
EVENTO_RESULTADO_VISTO = 'resultado_visto'
EVENTO_SIMULO_PRECIO = 'simulo_precio'
EVENTO_RECOMENDACIONES_OK = 'recomendaciones_ok'

EVENTOS_VALIDOS = frozenset({
    EVENTO_APERTURA,
    EVENTO_INICIO_WIZARD,
    EVENTO_CALCULO_OK,
    EVENTO_RESULTADO_VISTO,
    EVENTO_SIMULO_PRECIO,
    EVENTO_RECOMENDACIONES_OK,
})

SESSION_COOKIE = 'cm_sid'


def _parse_int(val) -> Optional[int]:
    try:
        n = int(val)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def atribucion_desde_request(request: HttpRequest) -> tuple[Optional[int], Optional[int]]:
    """
    Resuelve cliente y curso desde URL o sesión.

    Query soportada:
    - ?org=cooperativa-valle  (slug legible)
    - ?t=abc123token          (opaco)
    - ?cliente=21             (legacy numérico)
    - ?curso=22               (opcional, atribución al módulo/curso WA)
    """
    org = request.GET.get('org', '')
    token = request.GET.get('t', '') or request.GET.get('token', '')
    cliente_raw = request.GET.get('cliente', '')

    cliente = resolver_cliente_id(org=org, token=token, cliente_id=cliente_raw)
    curso = _parse_int(request.GET.get('curso'))

    if cliente is None:
        cliente = _parse_int(request.session.get('cm_cliente_id'))
    if curso is None:
        curso = _parse_int(request.session.get('cm_curso_id'))

    if cliente:
        request.session['cm_cliente_id'] = cliente
    if curso:
        request.session['cm_curso_id'] = curso
    return cliente, curso


def session_key(request: HttpRequest) -> str:
    sid = request.COOKIES.get(SESSION_COOKIE)
    if sid and len(sid) >= 16:
        return sid[:64]
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:32]


def registrar_evento(
    request: HttpRequest,
    evento: str,
    *,
    margen_rango: str = '',
    meta: Optional[dict] = None,
) -> bool:
    if evento not in EVENTOS_VALIDOS:
        return False
    cliente_id, curso_id = atribucion_desde_request(request)
    if not cliente_id:
        return False
    try:
        from core.models import Cliente
        from calculadora_margen.models import MargenUsoEvento

        if not Cliente.objects.filter(pk=cliente_id).exists():
            return False

        MargenUsoEvento.objects.create(
            cliente_id=cliente_id,
            curso_id=curso_id,
            session_key=session_key(request),
            evento=evento,
            margen_rango=(margen_rango or '')[:20],
            meta=meta or {},
        )
        return True
    except Exception:
        return False


def resumen_uso_cliente(cliente_id: int, *, dias: int = 30) -> dict[str, Any]:
    from datetime import timedelta

    from django.db.models import Count
    from django.utils import timezone

    from calculadora_margen.models import MargenUsoEvento
    from core.models import Cliente

    desde = timezone.now() - timedelta(days=max(1, dias))
    qs = MargenUsoEvento.objects.filter(cliente_id=cliente_id, creado_en__gte=desde)

    por_evento = dict(
        qs.values('evento').annotate(n=Count('id')).values_list('evento', 'n')
    )
    sesiones = qs.values('session_key').distinct().count()
    aperturas = por_evento.get(EVENTO_APERTURA, 0)
    calculos = por_evento.get(EVENTO_CALCULO_OK, 0)
    recomendaciones = por_evento.get(EVENTO_RECOMENDACIONES_OK, 0)
    simulaciones = por_evento.get(EVENTO_SIMULO_PRECIO, 0)

    rangos = dict(
        qs.filter(evento=EVENTO_CALCULO_OK, margen_rango__gt='')
        .values('margen_rango')
        .annotate(n=Count('id'))
        .values_list('margen_rango', 'n')
    )

    tasa_completa = round(100.0 * calculos / aperturas, 1) if aperturas else None
    tasa_ia = round(100.0 * recomendaciones / calculos, 1) if calculos else None

    links = {}
    cliente = Cliente.objects.filter(pk=cliente_id).first()
    if cliente:
        links = urls_margen_cliente(cliente)

    return {
        'dias': dias,
        'sesiones': sesiones,
        'aperturas': aperturas,
        'inicios_wizard': por_evento.get(EVENTO_INICIO_WIZARD, 0),
        'calculos': calculos,
        'resultados_vistos': por_evento.get(EVENTO_RESULTADO_VISTO, 0),
        'simulaciones': simulaciones,
        'recomendaciones': recomendaciones,
        'tasa_completa_pct': tasa_completa,
        'tasa_ia_pct': tasa_ia,
        'margen_rangos': rangos,
        'links': links,
        'link_compartir': links.get('url_org', ''),
        'link_token': links.get('url_token', ''),
    }
