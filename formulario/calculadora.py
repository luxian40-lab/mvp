"""
Motor de balance GEI (simplificado) a partir de FichaGEI.

Factores alineados con IPCC 2006 Tier 1 (simplificado) y factor red Colombia (UPME ~2023).
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

# Factores de emisión — referencia técnica simplificada
FACTORES: dict[str, float] = {
    # N aplicado → N2O-N directo (EF1) → N2O → CO2e (GWP AR4 298)
    "n2o_suelo_directo": 0.01,  # fracción del N que se emite como N2O-N
    "gwp_n2o": 298.0,
    # kg CO2e / galón (combustión móvil/estacionaria, valores típicos reportados)
    "gasolina_gal": 8.78,
    "diesel_gal": 10.15,
    "ambos_gal": 9.46,
    # Red nacional Colombia (kg CO2e / kWh), orden de magnitud UPME
    "electricidad_kwh": 0.126,
    # Residuos orgánicos (kg CO2e / tonelada tratada según manejo simplificado)
    "residuos_compost": 4.0,
    "residuos_externo": 8.5,
    "residuos_quemado": 58.0,
    "residuos_otro": 8.5,
    "residuos_default": 8.5,
    # Remoción bosque (t CO2e / ha / año) → se convierte a kg en el cálculo
    "bosque_conservacion_ha": 3.67,
    # Benchmark café (kg CO2e / kg producto)
    "intensidad_cafe_eficiente": 1.5,
    "intensidad_cafe_promedio": 2.8,
}


def _factor_residuos_por_manejo(manejo: str) -> float:
    m = (manejo or "").strip().lower()
    if m == "compost":
        return FACTORES["residuos_compost"]
    if m == "externo":
        return FACTORES["residuos_externo"]
    if m == "quemado":
        return FACTORES["residuos_quemado"]
    if m == "otro":
        return FACTORES["residuos_otro"]
    return FACTORES["residuos_default"]


def _factor_combustible_gal(tipo: str) -> float:
    t = (tipo or "").strip().lower()
    if t == "gasolina":
        return FACTORES["gasolina_gal"]
    if t == "diesel":
        return FACTORES["diesel_gal"]
    return FACTORES["ambos_gal"]


def calcular_balance_gei(ficha) -> dict[str, Any]:
    """
    Devuelve dict con emisiones, remociones, balance, intensidad, completitud y faltantes.
    `ficha` debe ser instancia de FichaGEI.
    """
    resultado: dict[str, Any] = {
        "emisiones": {},
        "remociones": {},
        "balance_neto_tco2e": 0.0,
        "intensidad_kg_co2e_por_kg": None,
        "comparacion_benchmark": None,
        "completitud_calculo_pct": 0,
        "campos_faltantes": [],
    }

    emisiones_kg = 0.0
    campos_usados = 0

    # 1. Fertilizante nitrogenado
    if ficha.fertilizante_kg is not None and ficha.concentracion_n_pct is not None:
        kg_n = float(ficha.fertilizante_kg) * (float(ficha.concentracion_n_pct) / 100.0)
        conv = FACTORES["n2o_suelo_directo"] * (44.0 / 28.0) * FACTORES["gwp_n2o"]
        em_fert = kg_n * conv
        resultado["emisiones"]["fertilizante_kg_co2e"] = round(em_fert, 2)
        emisiones_kg += em_fert
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("fertilizante / % nitrógeno")

    # 2. Combustible
    if ficha.combustible_gal is not None:
        factor = _factor_combustible_gal(getattr(ficha, "tipo_combustible", "") or "")
        em_comb = float(ficha.combustible_gal) * factor
        resultado["emisiones"]["combustible_kg_co2e"] = round(em_comb, 2)
        emisiones_kg += em_comb
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("combustible")

    # 3. Energía eléctrica
    if ficha.energia_kwh is not None:
        em_elec = float(ficha.energia_kwh) * FACTORES["electricidad_kwh"]
        resultado["emisiones"]["energia_kg_co2e"] = round(em_elec, 2)
        emisiones_kg += em_elec
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("energía eléctrica")

    # 4. Residuos orgánicos
    if ficha.residuos_ton is not None and (ficha.manejo_residuos or "").strip():
        factor_res = _factor_residuos_por_manejo(ficha.manejo_residuos)
        em_res = float(ficha.residuos_ton) * factor_res
        resultado["emisiones"]["residuos_kg_co2e"] = round(em_res, 2)
        emisiones_kg += em_res
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("residuos orgánicos")

    # 5. Remociones — bosque
    remociones_kg = 0.0
    if ficha.tiene_bosque is False:
        campos_usados += 1
    elif ficha.tiene_bosque and ficha.area_bosque_ha is not None:
        rem_bosque = float(ficha.area_bosque_ha) * FACTORES["bosque_conservacion_ha"] * 1000.0
        resultado["remociones"]["bosque_kg_co2e"] = round(rem_bosque, 2)
        remociones_kg += rem_bosque
        campos_usados += 1
    elif ficha.tiene_bosque is True:
        resultado["campos_faltantes"].append("área de bosque (ha)")
    else:
        resultado["campos_faltantes"].append("información de bosque")

    balance_neto_kg = emisiones_kg - remociones_kg
    resultado["emisiones"]["total_kg_co2e"] = round(emisiones_kg, 2)
    resultado["emisiones"]["total_tco2e"] = round(emisiones_kg / 1000.0, 3)
    resultado["remociones"]["total_kg_co2e"] = round(remociones_kg, 2)
    resultado["balance_neto_tco2e"] = round(balance_neto_kg / 1000.0, 3)

    # 6. Intensidad por kg de producto + benchmark café
    if ficha.produccion_kg is not None and float(ficha.produccion_kg) > 0:
        intensidad = balance_neto_kg / float(ficha.produccion_kg)
        resultado["intensidad_kg_co2e_por_kg"] = round(intensidad, 3)
        ev = (
            "excelente"
            if intensidad < FACTORES["intensidad_cafe_eficiente"]
            else "bueno"
            if intensidad < FACTORES["intensidad_cafe_promedio"]
            else "mejorable"
        )
        resultado["comparacion_benchmark"] = {
            "valor_finca": round(intensidad, 3),
            "promedio_sectorial": FACTORES["intensidad_cafe_promedio"],
            "escenario_eficiente": FACTORES["intensidad_cafe_eficiente"],
            "evaluacion": ev,
        }
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("producción anual")

    resultado["completitud_calculo_pct"] = int(round(campos_usados / 6.0 * 100.0))
    return resultado


def persistir_resultado_gei(ficha) -> None:
    """Persiste en BD el resultado del cálculo para una ficha (idempotente)."""
    from .models import ResultadoGEI

    data = calcular_balance_gei(ficha)
    comp = data.get("comparacion_benchmark") or {}
    with transaction.atomic():
        ResultadoGEI.objects.update_or_create(
            ficha=ficha,
            defaults={
                "em_fertilizante_kg": data["emisiones"].get("fertilizante_kg_co2e"),
                "em_combustible_kg": data["emisiones"].get("combustible_kg_co2e"),
                "em_energia_kg": data["emisiones"].get("energia_kg_co2e"),
                "em_residuos_kg": data["emisiones"].get("residuos_kg_co2e"),
                "em_total_kg": data["emisiones"].get("total_kg_co2e"),
                "rem_bosque_kg": data["remociones"].get("bosque_kg_co2e"),
                "balance_neto_tco2e": data["balance_neto_tco2e"],
                "intensidad_kg_co2e_por_kg": data.get("intensidad_kg_co2e_por_kg"),
                "evaluacion": comp.get("evaluacion"),
                "completitud_calculo_pct": data["completitud_calculo_pct"],
                "campos_faltantes": data["campos_faltantes"],
            },
        )


def generar_mensaje_resultado_whatsapp(ficha) -> str:
    """Texto listo para WhatsApp con el balance (tras módulo 5 o cuando exista resultado)."""
    from .models import ResultadoGEI

    try:
        r = ficha.resultado
    except ResultadoGEI.DoesNotExist:
        return "Aún estamos calculando su balance. En unos minutos le enviamos el resultado."

    emojis = {"excelente": "🏆", "bueno": "✅", "mejorable": "⚠️"}
    emoji = emojis.get((r.evaluacion or "").lower(), "📊")

    em_total = r.em_total_kg or 0.0
    balance = r.balance_neto_tco2e if r.balance_neto_tco2e is not None else 0.0

    msg = "📊 *Resultado del Balance GEI de su finca*\n\n"
    msg += f"🌍 Emisiones totales: {em_total / 1000.0:.2f} tCO₂e/año\n"

    if r.rem_bosque_kg:
        msg += f"🌳 Remociones (bosque): {(r.rem_bosque_kg or 0.0) / 1000.0:.2f} tCO₂e/año\n"

    msg += f"⚖️ *Balance neto: {balance:.2f} tCO₂e/año*\n\n"

    if r.intensidad_kg_co2e_por_kg is not None:
        msg += f"📈 Intensidad: {r.intensidad_kg_co2e_por_kg:.2f} kg CO₂e / kg producto\n"
        msg += f"📉 Promedio sectorial: {FACTORES['intensidad_cafe_promedio']:.2f} kg CO₂e / kg\n"
        msg += f"{emoji} Evaluación: *{(r.evaluacion or '').upper()}*\n\n"

    if r.campos_faltantes:
        msg += f"⚠️ Datos que faltaron: {', '.join(r.campos_faltantes)}\n"
        msg += f"(El cálculo es {r.completitud_calculo_pct}% completo)\n\n"

    msg += "Su certificado lo recibe al completar el módulo 6. 🎓"
    return msg
