"""Factores GEI: valores por defecto y overrides por organización."""

from __future__ import annotations

from formulario.calculadora import FACTORES, factores_para_cliente_id

FACTOR_LABELS: dict[str, str] = {
    'gasolina_gal': 'Gasolina (kg CO₂e / galón)',
    'diesel_gal': 'Diésel (kg CO₂e / galón)',
    'ambos_gal': 'Combustible mixto (kg CO₂e / galón)',
    'electricidad_kwh_2026': 'Electricidad red Colombia 2026 (kg CO₂e / kWh)',
    'electricidad_kwh_2025': 'Electricidad red Colombia 2025 (kg CO₂e / kWh)',
    'residuos_compost_kg': 'Residuos → compostaje (kg CO₂e / kg)',
    'residuos_suelo_directo_kg': 'Residuos → suelo directo (kg CO₂e / kg)',
    'residuos_externo_kg': 'Residuos → manejo externo (kg CO₂e / kg)',
    'residuos_quemado_kg': 'Residuos quemados (kg CO₂e / kg)',
    'residuos_otro_kg': 'Residuos otro manejo (kg CO₂e / kg)',
    'residuos_default_kg': 'Residuos por defecto (kg CO₂e / kg)',
    'organico_n_pct': 'Fertilizante orgánico — % N asumido (decimal)',
    'organico_ef_directo': 'Fertilizante orgánico — factor emisión directa',
    'sintetico_ef_directo': 'Fertilizante sintético — factor emisión directa',
    'bosque_conservacion_ha': 'Remoción bosque (t CO₂e / ha / año)',
    'intensidad_cafe_eficiente': 'Benchmark café eficiente (kg CO₂e / kg)',
    'intensidad_cafe_promedio': 'Benchmark café promedio sector (kg CO₂e / kg)',
}


def factores_para_cliente(cliente) -> dict[str, float]:
    """Merge FACTORES globales con overrides de la organización."""
    if cliente is None:
        return dict(FACTORES)
    return factores_para_cliente_id(getattr(cliente, 'pk', None))


def filas_factores_portal(org) -> list[dict]:
    """Filas para template: clave, etiqueta, default, actual, personalizado."""
    efectivos = factores_para_cliente(org)
    overrides = getattr(org, 'gei_factores_json', None) or {}
    filas = []
    for key in FACTORES:
        filas.append({
            'clave': key,
            'label': FACTOR_LABELS.get(key, key),
            'default': FACTORES[key],
            'actual': efectivos[key],
            'personalizado': key in overrides,
        })
    return filas
