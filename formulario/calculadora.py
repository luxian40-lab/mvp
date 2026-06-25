"""
Motor de balance GEI a partir de FichaGEI.

Factores alineados con metodología simplificada acordada (GWP N₂O=273, red Colombia).
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

# Conversión N₂O-N → CO₂e
GWP_N2O = 273.0
N2O_TO_CO2 = 44.0 / 28.0

FACTORES: dict[str, float] = {
    # kg CO₂e / galón
    "gasolina_gal": 7.62,
    "diesel_gal": 10.28,
    "ambos_gal": 8.95,
    # Red nacional Colombia (kg CO₂e / kWh)
    "electricidad_kwh_2026": 0.126,
    "electricidad_kwh_2025": 0.097,
    # Residuos orgánicos (kg CO₂e / kg residuo)
    "residuos_compost_kg": 0.1899,
    "residuos_suelo_directo_kg": 0.026,
    "residuos_externo_kg": 0.0085,
    "residuos_quemado_kg": 0.058,
    "residuos_otro_kg": 0.026,
    "residuos_default_kg": 0.026,
    # Fertilizante orgánico sin composición establecida (% N asumido)
    "organico_n_pct": 0.016,
    "organico_ef_directo": 0.003,
    "sintetico_ef_directo": 0.01,
    # Remoción bosque (t CO₂e / ha / año) → se convierte a kg en el cálculo
    "bosque_conservacion_ha": 3.67,
    # Benchmark café (kg CO₂e / kg producto)
    "intensidad_cafe_eficiente": 1.5,
    "intensidad_cafe_promedio": 2.8,
}


def factores_para_cliente_id(cliente_id) -> dict[str, float]:
    """Factores globales + overrides guardados en Cliente.gei_factores_json."""
    merged = dict(FACTORES)
    if not cliente_id:
        return merged
    try:
        from core.models import Cliente

        raw = Cliente.objects.filter(pk=cliente_id).values_list('gei_factores_json', flat=True).first()
        if isinstance(raw, dict):
            for key, val in raw.items():
                if key in merged:
                    try:
                        merged[key] = float(val)
                    except (TypeError, ValueError):
                        continue
    except Exception:
        pass
    return merged


def _factor_residuos_por_manejo(manejo: str, factores: dict | None = None) -> float:
    f = factores or FACTORES
    m = (manejo or "").strip().lower()
    if m == "compost":
        return f["residuos_compost_kg"]
    if m == "suelo_directo":
        return f["residuos_suelo_directo_kg"]
    if m == "externo":
        return f["residuos_externo_kg"]
    if m == "quemado":
        return f["residuos_quemado_kg"]
    if m == "otro":
        return f["residuos_otro_kg"]
    return f["residuos_default_kg"]


def _factor_combustible_gal(tipo: str, factores: dict | None = None) -> float:
    f = factores or FACTORES
    t = (tipo or "").strip().lower()
    if t == "gasolina":
        return f["gasolina_gal"]
    if t == "diesel":
        return f["diesel_gal"]
    return f["ambos_gal"]


def _factor_electricidad_kwh(anio: int | None, factores: dict | None = None) -> float:
    f = factores or FACTORES
    if anio is not None and int(anio) <= 2025:
        return f["electricidad_kwh_2025"]
    return f["electricidad_kwh_2026"]


def _emision_n2o_desde_kg_n(kg_n: float, ef_directo: float) -> float:
    """Tres términos: emisión directa + volatilización + lixiviación (Tier 1 simplificado)."""
    if kg_n <= 0:
        return 0.0
    t1 = kg_n * ef_directo * N2O_TO_CO2 * GWP_N2O
    t2 = kg_n * 0.1 * 0.01 * N2O_TO_CO2 * GWP_N2O
    t3 = kg_n * 0.3 * 0.0075 * N2O_TO_CO2 * GWP_N2O
    return t1 + t2 + t3


def _calcular_emision_fertilizante(ficha, factores: dict | None = None) -> tuple[float | None, str | None]:
    """
    Devuelve (kg CO₂e, motivo_faltante).
    Orgánico: kg fertilizante con 1,6% N fijo. Sintético: kg × % N.
    """
    if ficha.fertilizante_kg is None:
        return None, "fertilizante"
    kg_fert = float(ficha.fertilizante_kg)
    if kg_fert == 0:
        return 0.0, None

    tipo = (getattr(ficha, "tipo_fertilizante", None) or "sintetico").strip().lower()
    f = factores or FACTORES
    if tipo == "organico":
        kg_n = kg_fert * f["organico_n_pct"]
        return _emision_n2o_desde_kg_n(kg_n, f["organico_ef_directo"]), None

    if ficha.concentracion_n_pct is None:
        return None, "fertilizante / % nitrógeno"
    kg_n = kg_fert * (float(ficha.concentracion_n_pct) / 100.0)
    return _emision_n2o_desde_kg_n(kg_n, f["sintetico_ef_directo"]), None


def estimar_cobertura_metodologica(ficha) -> dict[str, Any]:
    """
    Cobertura aproximada del inventario operativo (no confundir con completitud de datos).
    """
    tipo_cultivo = (getattr(ficha, "tipo_cultivo", None) or "perenne").strip().lower()

    if tipo_cultivo == "arroz":
        return {
            "pct_min": None,
            "pct_max": None,
            "nota": (
                "Este método no se recomienda para cultivos en inundación como el arroz. "
                "Use el resultado solo como referencia orientativa."
            ),
            "advertencia_fuerte": True,
        }

    alta_mec = getattr(ficha, "alta_mecanizacion", None)
    usa_cal = getattr(ficha, "usa_enmiendas_cal", None)

    if tipo_cultivo == "transitorio" or alta_mec is True:
        return {
            "pct_min": 50,
            "pct_max": 60,
            "nota": (
                "En fincas muy mecanizadas o de cultivo transitorio, este balance suele cubrir "
                "entre el 50% y 60% de las emisiones directas u operativas."
            ),
            "advertencia_fuerte": False,
        }

    if usa_cal is True:
        return {
            "pct_min": 70,
            "pct_max": 80,
            "nota": (
                "Al usar enmiendas como cal u otros insumos no incluidos aquí, este balance "
                "podría cubrir entre el 70% y 80% de las emisiones operativas."
            ),
            "advertencia_fuerte": False,
        }

    return {
        "pct_min": 80,
        "pct_max": 90,
        "nota": (
            "En un escenario sencillo donde la fertilización es la principal fuente, "
            "este balance suele cubrir entre el 80% y 90% de las emisiones operativas."
        ),
        "advertencia_fuerte": False,
    }


def formatear_nota_cobertura(cobertura: dict[str, Any]) -> str:
    if cobertura.get("advertencia_fuerte"):
        return cobertura["nota"]
    pmin = cobertura.get("pct_min")
    pmax = cobertura.get("pct_max")
    if pmin is not None and pmax is not None:
        return f"ℹ️ Cobertura estimada: {pmin}–{pmax}% de emisiones operativas. {cobertura['nota']}"
    return cobertura.get("nota", "")


def calcular_balance_gei(ficha) -> dict[str, Any]:
    """
    Devuelve dict con emisiones, remociones, balance, intensidad, completitud y faltantes.
    `ficha` debe ser instancia de FichaGEI.
    """
    F = factores_para_cliente_id(getattr(ficha, 'cliente_id', None))
    resultado: dict[str, Any] = {
        "emisiones": {},
        "remociones": {},
        "balance_neto_tco2e": 0.0,
        "intensidad_kg_co2e_por_kg": None,
        "comparacion_benchmark": None,
        "completitud_calculo_pct": 0,
        "campos_faltantes": [],
        "cobertura_metodologica": estimar_cobertura_metodologica(ficha),
    }

    emisiones_kg = 0.0
    campos_usados = 0

    # 1. Fertilizante nitrogenado
    em_fert, falta_fert = _calcular_emision_fertilizante(ficha, F)
    if em_fert is not None:
        resultado["emisiones"]["fertilizante_kg_co2e"] = round(em_fert, 2)
        emisiones_kg += em_fert
        campos_usados += 1
    elif falta_fert:
        resultado["campos_faltantes"].append(falta_fert)

    # 2. Combustible
    if ficha.combustible_gal is not None:
        factor = _factor_combustible_gal(getattr(ficha, "tipo_combustible", "") or "", F)
        em_comb = float(ficha.combustible_gal) * factor
        resultado["emisiones"]["combustible_kg_co2e"] = round(em_comb, 2)
        emisiones_kg += em_comb
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("combustible")

    # 3. Energía eléctrica (kWh/año)
    if ficha.energia_kwh is not None:
        anio = getattr(ficha, "anio_datos_energia", None)
        em_elec = float(ficha.energia_kwh) * _factor_electricidad_kwh(anio, F)
        resultado["emisiones"]["energia_kg_co2e"] = round(em_elec, 2)
        emisiones_kg += em_elec
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("energía eléctrica")

    # 4. Residuos orgánicos (ton → kg × factor kg/kg)
    if ficha.residuos_ton is not None and (ficha.manejo_residuos or "").strip():
        factor_res = _factor_residuos_por_manejo(ficha.manejo_residuos, F)
        em_res = float(ficha.residuos_ton) * 1000.0 * factor_res
        resultado["emisiones"]["residuos_kg_co2e"] = round(em_res, 2)
        emisiones_kg += em_res
        campos_usados += 1
    else:
        resultado["campos_faltantes"].append("residuos orgánicos")

    # 5. Remociones — bosque
    remociones_kg = 0.0
    if ficha.tiene_bosque is False:
        campos_usados += 1
    elif ficha.tiene_bosque is True and ficha.area_bosque_ha is not None:
        rem_bosque = float(ficha.area_bosque_ha) * F["bosque_conservacion_ha"] * 1000.0
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
            if intensidad < F["intensidad_cafe_eficiente"]
            else "bueno"
            if intensidad < F["intensidad_cafe_promedio"]
            else "mejorable"
        )
        resultado["comparacion_benchmark"] = {
            "valor_finca": round(intensidad, 3),
            "promedio_sectorial": F["intensidad_cafe_promedio"],
            "escenario_eficiente": F["intensidad_cafe_eficiente"],
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
    cobertura = data.get("cobertura_metodologica") or {}
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
                "nota_cobertura": formatear_nota_cobertura(cobertura),
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

    if r.nota_cobertura:
        msg += f"{r.nota_cobertura}\n\n"

    if r.campos_faltantes:
        msg += f"⚠️ Datos que faltaron: {', '.join(r.campos_faltantes)}\n"
        msg += f"(El cálculo es {r.completitud_calculo_pct}% completo)\n\n"

    msg += "Su certificado lo recibe al completar el módulo 6. 🎓"
    return msg
