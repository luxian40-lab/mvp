"""Desglose paso a paso del cálculo GEI para la ficha de cada productor."""
from __future__ import annotations

from typing import Any

from formulario.calculadora import (
    FACTORES,
    GWP_N2O,
    N2O_TO_CO2,
    _emision_n2o_desde_kg_n,
    _factor_combustible_gal,
    _factor_electricidad_kwh,
    _factor_residuos_por_manejo,
    factores_para_cliente_id,
)
from portal.gei_sandbox import margen_error_pct

MARGEN_OBJETIVO_PCT = 5.0


def _r(valor: float | None, nd: int = 2) -> float | None:
    if valor is None:
        return None
    return round(float(valor), nd)


def desglose_calculo_ficha(ficha) -> dict[str, Any]:
    """
    Pasos numerados desde datos de inventario hasta balance neto,
    con fórmulas, factores y aporte relativo para localizar desviaciones.
    """
    F = factores_para_cliente_id(getattr(ficha, 'cliente_id', None))
    pasos: list[dict[str, Any]] = []
    emisiones_kg = 0.0
    remociones_kg = 0.0

    # --- 1. Fertilizante ---
    paso_fert: dict[str, Any] = {
        'n': 1,
        'id': 'fertilizante',
        'titulo': 'Fertilizante nitrogenado',
        'estado': 'faltante',
        'lineas': [],
        'resultado_kg': None,
        'unidad': 'kg CO₂e',
    }
    if ficha.fertilizante_kg is None:
        paso_fert['lineas'].append('Falta fertilizante (kg).')
    else:
        kg_fert = float(ficha.fertilizante_kg)
        tipo = (getattr(ficha, 'tipo_fertilizante', None) or 'sintetico').strip().lower()
        tipo_label = 'orgánico' if tipo == 'organico' else 'sintético'
        paso_fert['lineas'].append(f'Dato: {kg_fert:g} kg fertilizante ({tipo_label}).')
        if kg_fert == 0:
            paso_fert['estado'] = 'ok'
            paso_fert['resultado_kg'] = 0.0
            paso_fert['lineas'].append('Emisión = 0 (sin fertilizante).')
        elif tipo == 'organico':
            pct_n = F['organico_n_pct'] * 100
            kg_n = kg_fert * F['organico_n_pct']
            ef = F['organico_ef_directo']
            em = _emision_n2o_desde_kg_n(kg_n, ef)
            t1 = kg_n * ef * N2O_TO_CO2 * GWP_N2O
            t2 = kg_n * 0.1 * 0.01 * N2O_TO_CO2 * GWP_N2O
            t3 = kg_n * 0.3 * 0.0075 * N2O_TO_CO2 * GWP_N2O
            paso_fert['lineas'].extend([
                f'N asumido orgánico: {pct_n:g}% → kg N = {kg_fert:g} × {F["organico_n_pct"]} = {_r(kg_n, 4)}',
                f'Directa: kg N × EF({ef}) × (44/28) × GWP({GWP_N2O:g}) = {_r(t1)}',
                f'Volatilización: {_r(t2)} · Lixiviación: {_r(t3)}',
                f'Suma fertilizante = {_r(em)} kg CO₂e',
            ])
            paso_fert['resultado_kg'] = _r(em)
            paso_fert['estado'] = 'ok'
            emisiones_kg += em
        elif ficha.concentracion_n_pct is None:
            paso_fert['lineas'].append('Falta % de nitrógeno para fertilizante sintético.')
        else:
            pct = float(ficha.concentracion_n_pct)
            kg_n = kg_fert * (pct / 100.0)
            ef = F['sintetico_ef_directo']
            em = _emision_n2o_desde_kg_n(kg_n, ef)
            t1 = kg_n * ef * N2O_TO_CO2 * GWP_N2O
            t2 = kg_n * 0.1 * 0.01 * N2O_TO_CO2 * GWP_N2O
            t3 = kg_n * 0.3 * 0.0075 * N2O_TO_CO2 * GWP_N2O
            paso_fert['lineas'].extend([
                f'kg N = {kg_fert:g} × ({pct:g} / 100) = {_r(kg_n, 4)}',
                f'Directa: kg N × EF({ef}) × (44/28) × GWP({GWP_N2O:g}) = {_r(t1)}',
                f'Volatilización: {_r(t2)} · Lixiviación: {_r(t3)}',
                f'Suma fertilizante = {_r(em)} kg CO₂e',
            ])
            paso_fert['resultado_kg'] = _r(em)
            paso_fert['estado'] = 'ok'
            emisiones_kg += em
    pasos.append(paso_fert)

    # --- 2. Combustible ---
    paso_comb: dict[str, Any] = {
        'n': 2,
        'id': 'combustible',
        'titulo': 'Combustible',
        'estado': 'faltante',
        'lineas': [],
        'resultado_kg': None,
        'unidad': 'kg CO₂e',
    }
    if ficha.combustible_gal is None:
        paso_comb['lineas'].append('Falta combustible (gal).')
    else:
        gal = float(ficha.combustible_gal)
        tipo_c = getattr(ficha, 'tipo_combustible', '') or ''
        factor = _factor_combustible_gal(tipo_c, F)
        em = gal * factor
        tipo_c_label = tipo_c or 'ambos/mixto'
        paso_comb['lineas'].extend([
            f'Dato: {gal:g} gal ({tipo_c_label}).',
            f'Factor: {factor:g} kg CO₂e / gal.',
            f'{gal:g} × {factor:g} = {_r(em)} kg CO₂e',
        ])
        paso_comb['resultado_kg'] = _r(em)
        paso_comb['estado'] = 'ok'
        emisiones_kg += em
    pasos.append(paso_comb)

    # --- 3. Energía ---
    paso_en: dict[str, Any] = {
        'n': 3,
        'id': 'energia',
        'titulo': 'Energía eléctrica',
        'estado': 'faltante',
        'lineas': [],
        'resultado_kg': None,
        'unidad': 'kg CO₂e',
    }
    if ficha.energia_kwh is None:
        paso_en['lineas'].append('Falta energía (kWh).')
    else:
        kwh = float(ficha.energia_kwh)
        anio = getattr(ficha, 'anio_datos_energia', None)
        factor = _factor_electricidad_kwh(anio, F)
        em = kwh * factor
        anio_txt = str(anio) if anio else '≥2026 (default)'
        paso_en['lineas'].extend([
            f'Dato: {kwh:g} kWh (año ref. {anio_txt}).',
            f'Factor red Colombia: {factor:g} kg CO₂e / kWh.',
            f'{kwh:g} × {factor:g} = {_r(em)} kg CO₂e',
        ])
        paso_en['resultado_kg'] = _r(em)
        paso_en['estado'] = 'ok'
        emisiones_kg += em
    pasos.append(paso_en)

    # --- 4. Residuos ---
    paso_res: dict[str, Any] = {
        'n': 4,
        'id': 'residuos',
        'titulo': 'Residuos orgánicos',
        'estado': 'faltante',
        'lineas': [],
        'resultado_kg': None,
        'unidad': 'kg CO₂e',
    }
    manejo = (ficha.manejo_residuos or '').strip()
    if ficha.residuos_ton is None or not manejo:
        paso_res['lineas'].append('Falta residuos (ton) y/o manejo.')
    else:
        ton = float(ficha.residuos_ton)
        factor = _factor_residuos_por_manejo(manejo, F)
        kg_res = ton * 1000.0
        em = kg_res * factor
        paso_res['lineas'].extend([
            f'Dato: {ton:g} t · manejo «{manejo}».',
            f'Convertir a kg: {ton:g} × 1000 = {kg_res:g} kg residuo.',
            f'Factor: {factor:g} kg CO₂e / kg residuo.',
            f'{kg_res:g} × {factor:g} = {_r(em)} kg CO₂e',
        ])
        paso_res['resultado_kg'] = _r(em)
        paso_res['estado'] = 'ok'
        emisiones_kg += em
    pasos.append(paso_res)

    # --- 5. Bosque ---
    paso_bos: dict[str, Any] = {
        'n': 5,
        'id': 'bosque',
        'titulo': 'Remoción por bosque / cobertura',
        'estado': 'faltante',
        'lineas': [],
        'resultado_kg': None,
        'unidad': 'kg CO₂e (remoción)',
        'es_remocion': True,
    }
    if ficha.tiene_bosque is False:
        paso_bos['lineas'].append('Sin bosque: remoción = 0.')
        paso_bos['resultado_kg'] = 0.0
        paso_bos['estado'] = 'ok'
    elif ficha.tiene_bosque is True and ficha.area_bosque_ha is not None:
        ha = float(ficha.area_bosque_ha)
        factor_ha = F['bosque_conservacion_ha']
        rem = ha * factor_ha * 1000.0
        paso_bos['lineas'].extend([
            f'Dato: {ha:g} ha de bosque/cobertura.',
            f'Factor: {factor_ha:g} t CO₂e / ha / año → × 1000 = kg.',
            f'{ha:g} × {factor_ha:g} × 1000 = {_r(rem)} kg CO₂e removidos',
        ])
        paso_bos['resultado_kg'] = _r(rem)
        paso_bos['estado'] = 'ok'
        remociones_kg += rem
    elif ficha.tiene_bosque is True:
        paso_bos['lineas'].append('Indicó bosque pero falta área (ha).')
    else:
        paso_bos['lineas'].append('Falta indicar si tiene bosque.')
    pasos.append(paso_bos)

    # Aporte % sobre emisiones (para ver qué peso tiene cada fuente)
    for p in pasos:
        if p.get('es_remocion'):
            p['aporte_pct'] = None
            continue
        if p['resultado_kg'] is None or emisiones_kg <= 0:
            p['aporte_pct'] = None
        else:
            p['aporte_pct'] = _r((float(p['resultado_kg']) / emisiones_kg) * 100.0, 1)

    balance_kg = emisiones_kg - remociones_kg
    balance_t = balance_kg / 1000.0
    ref = getattr(ficha, 'referencia_balance_tco2e', None)
    margen = margen_error_pct(balance_t, ref)
    bajo_umbral = margen is not None and margen <= MARGEN_OBJETIVO_PCT

    # --- 6. Cierre ---
    paso_cierre = {
        'n': 6,
        'id': 'balance',
        'titulo': 'Balance neto',
        'estado': 'ok',
        'lineas': [
            f'Emisiones totales = {_r(emisiones_kg)} kg CO₂e',
            f'Remociones bosque = {_r(remociones_kg)} kg CO₂e',
            f'Balance = emisiones − remociones = {_r(balance_kg)} kg = {_r(balance_t, 3)} t CO₂e/año',
        ],
        'resultado_kg': _r(balance_kg),
        'resultado_t': _r(balance_t, 3),
        'unidad': 't CO₂e/año',
        'aporte_pct': None,
    }
    if ficha.produccion_kg is not None and float(ficha.produccion_kg) > 0:
        intensidad = balance_kg / float(ficha.produccion_kg)
        paso_cierre['lineas'].append(
            f'Intensidad = {_r(balance_kg)} / {float(ficha.produccion_kg):g} kg producto '
            f'= {_r(intensidad, 3)} kg CO₂e / kg'
        )
    pasos.append(paso_cierre)

    faltantes = [p['titulo'] for p in pasos if p['estado'] == 'faltante' and p['id'] != 'balance']

    return {
        'pasos': pasos,
        'emisiones_total_kg': _r(emisiones_kg),
        'remociones_total_kg': _r(remociones_kg),
        'balance_kg': _r(balance_kg),
        'balance_tco2e': _r(balance_t, 3),
        'referencia_tco2e': _r(float(ref), 3) if ref is not None else None,
        'margen_error_pct': margen,
        'margen_objetivo_pct': MARGEN_OBJETIVO_PCT,
        'margen_ok': bajo_umbral,
        'faltantes': faltantes,
        'factores_base': {
            'gwp_n2o': GWP_N2O,
            'diesel_gal': F.get('diesel_gal', FACTORES['diesel_gal']),
            'gasolina_gal': F.get('gasolina_gal', FACTORES['gasolina_gal']),
        },
    }
