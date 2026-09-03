"""
Capa determinística TAM / SAM / SOM — Python puro, sin IA.

Fórmulas MVP (anexo eki | Encuentra tu mercado, secs. 7–10, 17):
  TAM_mensual = clientes_universo × ticket_mensual
  SAM_mensual = TAM × factor_segmento × factor_alcance_ajustado
  capacidad_valor = capacidad_unidades × precio  (si hay capacidad)
  SOM_x = min(capacidad_valor o ∞, SAM × participación_x)
  SOM nunca supera capacidad declarada.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

# Universo de clientes potenciales (supuesto configurable) por alcance geográfico.
CLIENTES_UNIVERSO_POR_ALCANCE = {
    'local': Decimal('800'),
    'departamental': Decimal('6000'),
    'nacional': Decimal('90000'),
    'exportacion': Decimal('180000'),
}

# Participación del SAM capturable en escenarios SOM (conservador / base / ambicioso).
PARTICIPACION_SOM = {
    'conservador': Decimal('0.01'),
    'base': Decimal('0.03'),
    'ambicioso': Decimal('0.08'),
}

# Factor SAM según número de segmentos de cliente seleccionados.
FACTOR_SEGMENTO_BASE = Decimal('0.22')
FACTOR_SEGMENTO_POR_CHIP = Decimal('0.12')
FACTOR_SEGMENTO_MAX = Decimal('0.85')

MONEY_Q = Decimal('0.01')
PCT_Q = Decimal('0.01')


def _d(value: Any, default: str = '0') -> Decimal:
    if value is None or value == '' or value is False:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def _traza(valor: Decimal, tipo: str, fuente: str, formula: str, anio: int | None = None) -> dict:
    return {
        'valor': float(_money(valor)),
        'tipo': tipo,  # dato | estimacion | supuesto
        'fuente': fuente,
        'año': anio,
        'formula': formula,
    }


def factor_segmentos(segmentos: list | None) -> Decimal:
    n = len(segmentos or [])
    if n <= 0:
        return FACTOR_SEGMENTO_BASE
    f = FACTOR_SEGMENTO_BASE + FACTOR_SEGMENTO_POR_CHIP * Decimal(n)
    return min(f, FACTOR_SEGMENTO_MAX)


def clientes_universo(
    alcance: str,
    clientes_estimados: Any = None,
) -> tuple[Decimal, str]:
    """Devuelve (n_clientes, tipo_fuente)."""
    custom = _d(clientes_estimados)
    if custom > 0:
        return custom, 'dato'
    key = (alcance or 'local').strip().lower()
    if key not in CLIENTES_UNIVERSO_POR_ALCANCE:
        key = 'local'
    return CLIENTES_UNIVERSO_POR_ALCANCE[key], 'supuesto'


def calcular_tam(
    *,
    ticket_mensual: Any,
    alcance: str = 'local',
    clientes_estimados: Any = None,
) -> dict[str, Any]:
    ticket = _d(ticket_mensual)
    if ticket <= 0:
        raise ValueError('Indica un ticket mensual estimado (o usa un valor aproximado).')

    n, tipo = clientes_universo(alcance, clientes_estimados)
    tam = _money(n * ticket)
    return {
        'tam': float(tam),
        'clientes_universo': float(n),
        'ticket_mensual': float(_money(ticket)),
        'trazabilidad': _traza(
            tam,
            tipo if tipo == 'dato' else 'supuesto',
            'usuario' if tipo == 'dato' else f'tabla_alcance:{alcance}',
            'TAM = clientes_universo × ticket_mensual',
        ),
    }


def calcular_sam(
    *,
    tam: Any,
    segmentos: list | None = None,
) -> dict[str, Any]:
    tam_d = _d(tam)
    if tam_d <= 0:
        raise ValueError('TAM debe ser mayor que cero.')
    f = factor_segmentos(segmentos)
    sam = _money(tam_d * f)
    return {
        'sam': float(sam),
        'factor_segmentos': float(f),
        'trazabilidad': _traza(
            sam,
            'estimacion',
            'wizard_segmentos',
            f'SAM = TAM × {f} (factor por segmentos seleccionados)',
        ),
    }


def calcular_capacidad_maxima(
    *,
    capacidad_unidades: Any = None,
    precio: Any = 0,
) -> dict[str, Any]:
    """Valor máximo mensual atendible (unidades × precio). None si no declararon capacidad."""
    cap_u = _d(capacidad_unidades)
    precio_d = _d(precio)
    if cap_u <= 0 or precio_d <= 0:
        return {
            'capacidad_valor': None,
            'capacidad_unidades': float(cap_u) if cap_u > 0 else None,
            'trazabilidad': None,
        }
    valor = _money(cap_u * precio_d)
    return {
        'capacidad_valor': float(valor),
        'capacidad_unidades': float(cap_u),
        'trazabilidad': _traza(
            valor,
            'dato',
            'usuario',
            'capacidad_valor = capacidad_mensual × precio',
        ),
    }


def _aplicar_tope_capacidad(valor: Decimal, capacidad_valor: Decimal | None) -> Decimal:
    if capacidad_valor is None:
        return valor
    return min(valor, capacidad_valor)


def calcular_som(
    *,
    sam: Any,
    precio: Any = 0,
    capacidad_unidades: Any = None,
    participacion_custom: Any = None,
) -> dict[str, Any]:
    """
    Tres escenarios + opcional participación custom (simulador).
    SOM ≤ capacidad_valor cuando hay capacidad declarada.
    """
    sam_d = _d(sam)
    if sam_d <= 0:
        raise ValueError('SAM debe ser mayor que cero.')

    cap = calcular_capacidad_maxima(
        capacidad_unidades=capacidad_unidades,
        precio=precio,
    )
    cap_val = _d(cap['capacidad_valor']) if cap['capacidad_valor'] is not None else None

    outs: dict[str, Any] = {
        'capacidad_valor': cap['capacidad_valor'],
        'trazabilidad': {},
    }

    for nombre, part in PARTICIPACION_SOM.items():
        bruto = _money(sam_d * part)
        final = _money(_aplicar_tope_capacidad(bruto, cap_val))
        outs[f'som_{nombre}'] = float(final)
        outs['trazabilidad'][f'som_{nombre}'] = _traza(
            final,
            'estimacion',
            'motor_deterministico',
            (
                f'SOM_{nombre} = min(capacidad, SAM × {part})'
                if cap_val is not None
                else f'SOM_{nombre} = SAM × {part}'
            ),
        )

    if participacion_custom is not None and str(participacion_custom).strip() != '':
        p = _d(participacion_custom)
        if p > 1:
            p = p / Decimal('100')
        bruto = _money(sam_d * p)
        final = _money(_aplicar_tope_capacidad(bruto, cap_val))
        outs['som_simulado'] = float(final)
        outs['participacion_usada'] = float(p)
        outs['trazabilidad']['som_simulado'] = _traza(
            final,
            'estimacion',
            'simulador',
            f'SOM_sim = min(capacidad, SAM × {p})',
        )

    return outs


def asignar_confianza(
    *,
    ticket_mensual: Any,
    precio: Any,
    segmentos: list | None,
    capacidad_unidades: Any = None,
    clientes_estimados: Any = None,
    ticket_no_se: bool = False,
) -> dict[str, str]:
    """Regla simple MVP: datos clave vs supuestos → alta/media/baja."""
    score = 0
    notas: list[str] = []

    if _d(ticket_mensual) > 0 and not ticket_no_se:
        score += 2
    else:
        notas.append('Ticket mensual es supuesto o “no sé”.')

    if _d(precio) > 0:
        score += 1
    else:
        notas.append('Falta precio de venta.')

    if segmentos:
        score += 1
    else:
        notas.append('Sin segmentos de cliente seleccionados.')

    if _d(capacidad_unidades) > 0:
        score += 1
    else:
        notas.append('Sin capacidad máxima: el SOM no está topeado por producción real.')

    if _d(clientes_estimados) > 0:
        score += 1
    else:
        notas.append('Universo de clientes viene de tabla de supuestos por alcance.')

    if score >= 5:
        nivel = 'alta'
        emoji = '🟢'
    elif score >= 3:
        nivel = 'media'
        emoji = '🟡'
    else:
        nivel = 'baja'
        emoji = '🔴'

    nota = ' '.join(notas) if notas else 'Datos suficientes para una estimación razonable.'
    return {
        'confianza_estimacion': nivel,
        'nota_confianza': f'{emoji} Confianza {nivel}: {nota}',
    }


def calcular_escenario_completo(
    *,
    producto: str,
    precio: Any,
    ticket_mensual: Any,
    alcance: str = 'local',
    segmentos: list | None = None,
    capacidad_unidades: Any = None,
    clientes_estimados: Any = None,
    ticket_no_se: bool = False,
    ubicacion_actual: str = '',
    mercado_objetivo: str = '',
    categoria: str = '',
    presentacion: str = '',
    unidad_venta: str = 'unidad',
) -> dict[str, Any]:
    """Orquesta TAM → SAM → SOM + confianza + trazabilidad."""
    if not (producto or '').strip():
        raise ValueError('Indica qué producto vendes.')

    ticket = _d(ticket_mensual)
    if ticket <= 0:
        # “No sé”: supuesto suave = 2 × precio (compra típica pequeña)
        ticket = _money(_d(precio) * Decimal('2'))
        ticket_no_se = True
        if ticket <= 0:
            ticket = Decimal('50000')  # supuesto COP

    tam_r = calcular_tam(
        ticket_mensual=ticket,
        alcance=alcance,
        clientes_estimados=clientes_estimados,
    )
    sam_r = calcular_sam(tam=tam_r['tam'], segmentos=segmentos)
    som_r = calcular_som(
        sam=sam_r['sam'],
        precio=precio,
        capacidad_unidades=capacidad_unidades,
    )
    conf = asignar_confianza(
        ticket_mensual=ticket_mensual if not ticket_no_se else 0,
        precio=precio,
        segmentos=segmentos,
        capacidad_unidades=capacidad_unidades,
        clientes_estimados=clientes_estimados,
        ticket_no_se=ticket_no_se,
    )

    nombre = ' – '.join(
        p for p in [
            (producto or '').strip(),
            (mercado_objetivo or '').strip() or (ubicacion_actual or '').strip(),
            ', '.join(segmentos or [])[:80] if segmentos else '',
        ] if p
    )

    traz = {
        'tam': tam_r['trazabilidad'],
        'sam': sam_r['trazabilidad'],
        **(som_r.get('trazabilidad') or {}),
    }
    if som_r.get('capacidad_valor') is not None:
        cap = calcular_capacidad_maxima(
            capacidad_unidades=capacidad_unidades,
            precio=precio,
        )
        if cap.get('trazabilidad'):
            traz['capacidad'] = cap['trazabilidad']

    return {
        'nombre_escenario': nombre[:255],
        'producto': producto.strip(),
        'categoria': categoria or '',
        'presentacion': presentacion or '',
        'precio': float(_money(_d(precio))),
        'unidad_venta': unidad_venta or 'unidad',
        'ubicacion_actual': ubicacion_actual or '',
        'mercado_objetivo': mercado_objetivo or '',
        'alcance': alcance or 'local',
        'segmentos_cliente': list(segmentos or []),
        'ticket_mensual_estimado': float(_money(ticket)),
        'capacidad_mensual_maxima': (
            float(_d(capacidad_unidades)) if _d(capacidad_unidades) > 0 else None
        ),
        'tam': tam_r['tam'],
        'sam': sam_r['sam'],
        'som_conservador': som_r['som_conservador'],
        'som_base': som_r['som_base'],
        'som_ambicioso': som_r['som_ambicioso'],
        'capacidad_valor': som_r.get('capacidad_valor'),
        'clientes_universo': tam_r['clientes_universo'],
        'factor_segmentos': sam_r['factor_segmentos'],
        'confianza_estimacion': conf['confianza_estimacion'],
        'nota_confianza': conf['nota_confianza'],
        'trazabilidad': traz,
    }


def simular(
    *,
    sam: Any,
    clientes: Any,
    ticket: Any,
    precio: Any,
    participacion_pct: Any,
    capacidad_unidades: Any = None,
) -> dict[str, Any]:
    """
    Simulador §17 — mismas fórmulas que backend; pensado para espejo en JS.
    ventas_mensuales = clientes × ticket
    SOM_sim = min(capacidad_valor, SAM × participación)
    También reporta ventas vs SAM capturado.
    """
    sam_d = _d(sam)
    clientes_d = _d(clientes)
    ticket_d = _d(ticket)
    ventas = _money(clientes_d * ticket_d)

    som_r = calcular_som(
        sam=sam_d,
        precio=precio,
        capacidad_unidades=capacidad_unidades,
        participacion_custom=participacion_pct,
    )
    som = _d(som_r.get('som_simulado', som_r.get('som_base', 0)))
    pct_sam = Decimal('0')
    if sam_d > 0:
        pct_sam = (som / sam_d * Decimal('100')).quantize(PCT_Q, rounding=ROUND_HALF_UP)

    return {
        'ventas_mensuales': float(ventas),
        'ventas_anuales': float(_money(ventas * Decimal('12'))),
        'som': float(som),
        'pct_sam_capturado': float(pct_sam),
        'capacidad_valor': som_r.get('capacidad_valor'),
        'participacion_usada': som_r.get('participacion_usada'),
    }
