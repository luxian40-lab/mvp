"""Cálculo determinístico de margen — sin IA."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

RUBROS_VARIABLES = (
    ('materias_primas', 'Materias primas e insumos'),
    ('mano_obra', 'Mano de obra'),
    ('transporte', 'Transporte'),
    ('empaque', 'Empaque'),
    ('otros_costos', 'Otros costos'),
)


def _d(value: Any) -> Decimal:
    if value is None or value == '':
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def precio_para_margen(costo_unitario: Decimal, margen_deseado_pct: Decimal) -> Decimal | None:
    divisor = Decimal('1') - margen_deseado_pct / Decimal('100')
    if divisor <= 0:
        return None
    return (costo_unitario / divisor).quantize(Decimal('0.01'))


def nivel_alerta_desde_margen(margen: Decimal) -> str:
    if margen < Decimal('15'):
        return 'bajo'
    if margen < Decimal('30'):
        return 'medio'
    return 'saludable'


def calcular_margen(
    *,
    producto: str,
    cantidad_producida: Any,
    unidad: str,
    materias_primas: Any = 0,
    mano_obra: Any = 0,
    transporte: Any = 0,
    empaque: Any = 0,
    otros_costos: Any = 0,
    costos_fijos: Any = 0,
    precio_actual: Any = 0,
) -> dict[str, Any]:
    """
    Aplica las fórmulas del MVP. Devuelve dict serializable (floats/str).
    Lanza ValueError si los datos no permiten calcular.
    """
    cantidad = _d(cantidad_producida)
    if cantidad <= 0:
        raise ValueError('La cantidad producida debe ser mayor que cero.')

    mp = _d(materias_primas)
    mo = _d(mano_obra)
    tr = _d(transporte)
    em = _d(empaque)
    oc = _d(otros_costos)
    cf = _d(costos_fijos)
    precio = _d(precio_actual)

    total_variable = mp + mo + tr + em + oc
    costo_unitario = ((total_variable + cf) / cantidad).quantize(Decimal('0.0001'))

    if precio > 0:
        margen_actual = ((precio - costo_unitario) / precio * Decimal('100')).quantize(Decimal('0.01'))
    else:
        margen_actual = Decimal('0')

    precio_sug = precio_para_margen(costo_unitario, Decimal('25'))
    nivel = nivel_alerta_desde_margen(margen_actual)

    rubros = {
        'materias_primas': mp,
        'mano_obra': mo,
        'transporte': tr,
        'empaque': em,
        'otros_costos': oc,
    }
    mayor_key = max(rubros, key=lambda k: rubros[k])
    mayor_valor = rubros[mayor_key]
    mayor_label = dict(RUBROS_VARIABLES)[mayor_key]
    if total_variable > 0:
        mayor_pct = (mayor_valor / total_variable * Decimal('100')).quantize(Decimal('0.01'))
    else:
        mayor_pct = Decimal('0')

    desglose = [
        {'rubro': label, 'clave': key, 'monto': float(rubros[key])}
        for key, label in RUBROS_VARIABLES
    ]

    return {
        'producto': (producto or '').strip(),
        'cantidad_producida': float(cantidad),
        'unidad': (unidad or 'unidades').strip() or 'unidades',
        'materias_primas': float(mp),
        'mano_obra': float(mo),
        'transporte': float(tr),
        'empaque': float(em),
        'otros_costos': float(oc),
        'costos_fijos': float(cf),
        'precio_actual': float(precio),
        'total_variable': float(total_variable),
        'costo_unitario': float(costo_unitario),
        'margen_actual': float(margen_actual),
        'precio_sugerido_25': float(precio_sug) if precio_sug is not None else None,
        'nivel_alerta': nivel,
        'mayor_costo': mayor_label,
        'mayor_costo_clave': mayor_key,
        'mayor_costo_valor': float(mayor_valor),
        'mayor_costo_pct': float(mayor_pct),
        'desglose_costos': desglose,
    }


def margen_para_precio(costo_unitario: Decimal | float, precio: Decimal | float) -> float:
    """Recalcula margen % para simulador de precio (sin IA)."""
    cu = _d(costo_unitario)
    p = _d(precio)
    if p <= 0:
        return 0.0
    return float(((p - cu) / p * Decimal('100')).quantize(Decimal('0.01')))
