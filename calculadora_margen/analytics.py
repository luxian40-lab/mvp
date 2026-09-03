"""Telemetría agregada de la calculadora margen (sin PII ni montos)."""
from __future__ import annotations

import hashlib
import math
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
    inicios = por_evento.get(EVENTO_INICIO_WIZARD, 0)
    resultados = por_evento.get(EVENTO_RESULTADO_VISTO, 0)

    def _pct(num: int, den: int) -> Optional[float]:
        return round(100.0 * num / den, 1) if den else None

    base_embudo = aperturas or sesiones or 1
    embudo = [
        {
            'etapa': 'Abrieron enlace',
            'n': aperturas,
            'pct': 100.0 if aperturas else None,
            'pct_base': 100.0 if aperturas else None,
        },
        {
            'etapa': 'Iniciaron cálculo',
            'n': inicios,
            'pct': _pct(inicios, base_embudo),
            'pct_base': _pct(inicios, aperturas) if aperturas else None,
        },
        {
            'etapa': 'Completaron margen',
            'n': calculos,
            'pct': _pct(calculos, base_embudo),
            'pct_base': _pct(calculos, aperturas) if aperturas else None,
        },
        {
            'etapa': 'Vieron resultado',
            'n': resultados,
            'pct': _pct(resultados, base_embudo),
            'pct_base': _pct(resultados, calculos) if calculos else None,
        },
    ]

    habilidades = [
        {
            'nombre': 'Calcular margen',
            'descripcion': 'Completan el wizard de costos',
            'pct': _pct(calculos, aperturas) if aperturas else None,
            'n': calculos,
            'nivel': 'fortaleza' if (calculos and aperturas and calculos / aperturas >= 0.5) else 'desarrollo',
        },
        {
            'nombre': 'Tips con IA',
            'descripcion': 'Piden recomendaciones tras calcular',
            'pct': tasa_ia,
            'n': recomendaciones,
            'nivel': 'fortaleza' if tasa_ia and tasa_ia >= 40 else 'desarrollo',
        },
        {
            'nombre': 'Simular precio',
            'descripcion': 'Prueban escenarios de precio',
            'pct': _pct(simulaciones, calculos) if calculos else None,
            'n': simulaciones,
            'nivel': 'fortaleza' if simulaciones and calculos and simulaciones / calculos >= 0.3 else 'brecha',
        },
    ]

    max_rango = max(rangos.values()) if rangos else 0
    margen_barras = [
        {
            'rango': rango,
            'n': n,
            'pct_ancho': round(100.0 * n / max_rango, 1) if max_rango else 0,
        }
        for rango, n in sorted(rangos.items(), key=lambda x: (-x[1], x[0]))
    ]

    radar_labels: list[str] = []
    radar_polygon = ''
    if len(habilidades) >= 3:
        cx, cy, radius = 100.0, 100.0, 72.0
        angles = (-90, 30, 150)
        pts: list[tuple[float, float]] = []
        for i, h in enumerate(habilidades[:3]):
            pct = float(h.get('pct') or 0)
            r = radius * max(0.0, min(100.0, pct)) / 100.0
            ang = math.radians(angles[i])
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
            radar_labels.append(str(h.get('nombre') or '')[:18])
        radar_polygon = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)

    links = {}
    cliente = Cliente.objects.filter(pk=cliente_id).first()
    if cliente:
        links = urls_margen_cliente(cliente)

    return {
        'dias': dias,
        'sesiones': sesiones,
        'aperturas': aperturas,
        'inicios_wizard': inicios,
        'calculos': calculos,
        'resultados_vistos': resultados,
        'simulaciones': simulaciones,
        'recomendaciones': recomendaciones,
        'tasa_completa_pct': tasa_completa,
        'tasa_ia_pct': tasa_ia,
        'margen_rangos': rangos,
        'margen_barras': margen_barras,
        'embudo': embudo,
        'habilidades': habilidades,
        'radar_polygon': radar_polygon,
        'radar_labels': radar_labels,
        'links': links,
        'link_compartir': links.get('url_org', ''),
        'link_token': links.get('url_token', ''),
    }
