"""Definición de pasos GEI por bloque (contexto M4 / balance M5)."""
from __future__ import annotations

PASOS_CONTEXTO = [
    {
        "orden": 1,
        "campo_destino": "nombre_finca",
        "pregunta_texto": (
            "¡Hola! *Primera parte* de los datos de su finca para la huella de carbono.\n\n"
            "¿Cómo se llama su finca o cómo le dice usted al lote donde produce?"
        ),
        "tipo_dato": "text",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "es_opcional": False,
        "usar_llm_parseo": False,
        "texto_reintento": (
            "No le entendí. Cuénteme nomás el nombre de la finca o lote, "
            "puede ser corto. Si no tiene nombre, escriba 'sin nombre'."
        ),
    },
    {
        "orden": 2,
        "campo_destino": "area_ha",
        "pregunta_texto": (
            "¿Cuántas hectáreas *productivas* tiene sembradas en esa finca? "
            "Si me dice en fanegadas también le entiendo (1 fanegada ≈ 0.64 ha)."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 10000.0,
        "unidad_parseo": "ha",
        "es_opcional": False,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Disculpe, no logré sacar el número. Mándeme solo la cantidad, "
            "por ejemplo: 2.5 ha, 5 hectáreas, o 3 fanegadas."
        ),
    },
    {
        "orden": 3,
        "campo_destino": "num_plantas",
        "pregunta_texto": (
            "Aproximadamente, ¿cuántas plantas productivas tiene en total? "
            "No tiene que ser exacto, una cifra cercana basta."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 1_000_000.0,
        "unidad_parseo": "plantas",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme solo el número aproximado de plantas (ej. 3000). "
            "Si no lo sabe, escriba OMITIR y seguimos."
        ),
    },
    {
        "orden": 4,
        "campo_destino": "tipo_fertilizante",
        "pregunta_texto": (
            "¿Qué tipo de fertilizante usa más? Responda *sintetico* (químico con % N en el bulto) "
            "u *organico* (compost, abono sin composición fija). Si no usa, escriba *otro* u OMITIR."
        ),
        "tipo_dato": "choice",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "opciones_choice": "sintetico|organico|otro",
        "es_opcional": True,
        "usar_llm_parseo": False,
        "texto_reintento": "Escriba: sintetico, organico u otro. O OMITIR si no aplica.",
    },
    {
        "orden": 5,
        "campo_destino": "fertilizante_kg",
        "pregunta_texto": (
            "¿Cuántos kilos de fertilizante usa *al año* en esa finca? "
            "Si es orgánico, cuente compost o abono en kg. "
            "Si lo mide en bultos, un bulto suele ser 50 kg."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 100_000.0,
        "unidad_parseo": "kg",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Cuénteme solo la cantidad al año, por ejemplo: 200 kg, 4 bultos. "
            "Si no usa fertilizante, escriba 0. Si no sabe, escriba OMITIR."
        ),
    },
    {
        "orden": 6,
        "campo_destino": "concentracion_n_pct",
        "pregunta_texto": (
            "¿Sabe el porcentaje de Nitrógeno (N) del fertilizante? "
            "Sale en el bulto, como '15-15-15' o '46-0-0'. "
            "Mándeme solo el primer número. "
            "Si es *orgánico* o no lo sabe, escriba *OMITIR*."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 100.0,
        "unidad_parseo": "%",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme solo un número entre 0 y 100 (% de N), o escriba OMITIR."
        ),
    },
    {
        "orden": 7,
        "campo_destino": "produccion_kg",
        "pregunta_texto": (
            "¿Cuántos kilos produjo *el año pasado* en esta finca? "
            "Si lo mide en arrobas (1 arroba ≈ 12.5 kg), también me sirve."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 10_000_000.0,
        "unidad_parseo": "kg",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Cuénteme solo la cantidad del último año. Ej: 1500 kg, 120 arrobas. "
            "Si no la recuerda, escriba OMITIR."
        ),
    },
    {
        "orden": 8,
        "campo_destino": "energia_kwh",
        "pregunta_texto": (
            "¿Cuántos kWh de luz eléctrica consume *al año* en la finca? "
            "Puede estimarlo desde el recibo (kWh/mes × 12). Si no usa luz, escriba 0."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 1_000_000.0,
        "unidad_parseo": "kWh",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme kWh al año, ej: 960 kWh/año, o 0. Si no sabe, escriba OMITIR."
        ),
    },
    {
        "orden": 9,
        "campo_destino": "anio_datos_energia",
        "pregunta_texto": (
            "¿Esos datos de energía son del *2025* o del *2026*? "
            "Responda 2025 o 2026. Si no sabe, escriba 2026 u OMITIR."
        ),
        "tipo_dato": "choice",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "opciones_choice": "2025|2026",
        "es_opcional": True,
        "usar_llm_parseo": False,
        "texto_reintento": "Escriba 2025 o 2026, o OMITIR.",
    },
]

PASOS_BALANCE = [
    {
        "orden": 1,
        "campo_destino": "combustible_gal",
        "pregunta_texto": (
            "🧮 *Segunda parte* — datos para su balance GEI.\n\n"
            "¿Cuántos galones de gasolina o diésel usa *al año* en la finca? "
            "(motobomba, fumigadora, vehículo). Si no usa, escriba 0."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 50_000.0,
        "unidad_parseo": "galones",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme galones al año (ej. 120 galones) o 0. Si no sabe, escriba OMITIR."
        ),
    },
    {
        "orden": 2,
        "campo_destino": "tipo_combustible",
        "pregunta_texto": (
            "¿Qué combustible usa más? Responda: *diesel*, *gasolina*, *glp* u *otro*. "
            "Si no usa combustible, escriba *otro* u OMITIR."
        ),
        "tipo_dato": "choice",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "opciones_choice": "diesel|gasolina|glp|otro",
        "es_opcional": True,
        "usar_llm_parseo": False,
        "texto_reintento": "Escriba: diesel, gasolina, glp u otro. O OMITIR.",
    },
    {
        "orden": 3,
        "campo_destino": "residuos_ton",
        "pregunta_texto": (
            "¿Cuántas toneladas de residuos orgánicos (poda, cáscara, pulpa) genera *al año*? "
            "Estimación basta. Si casi no genera, escriba 0 u OMITIR."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 10_000.0,
        "unidad_parseo": "toneladas",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": "Mándeme toneladas al año o 0. Si no sabe, OMITIR.",
    },
    {
        "orden": 4,
        "campo_destino": "manejo_residuos",
        "pregunta_texto": (
            "¿Qué hace con esos residuos? *compost*, *suelo_directo*, *externo*, *quemado* u *otro*. "
            "(compost = compostaje; suelo_directo = los deja en el suelo). Si no aplica, OMITIR."
        ),
        "tipo_dato": "choice",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "opciones_choice": "compost|suelo_directo|externo|quemado|otro",
        "es_opcional": True,
        "usar_llm_parseo": False,
        "texto_reintento": "Escriba: compost, suelo_directo, externo, quemado u otro. O OMITIR.",
    },
    {
        "orden": 5,
        "campo_destino": "tipo_cultivo",
        "pregunta_texto": (
            "¿Qué tipo de cultivo tiene? *perenne* (café, cacao, plátano), "
            "*transitorio* (maíz, papa, hortalizas) o *arroz* (inundación). "
            "Si no sabe, escriba perenne u OMITIR."
        ),
        "tipo_dato": "choice",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "opciones_choice": "perenne|transitorio|arroz",
        "es_opcional": True,
        "usar_llm_parseo": False,
        "texto_reintento": "Escriba: perenne, transitorio o arroz. O OMITIR.",
    },
    {
        "orden": 6,
        "campo_destino": "alta_mecanizacion",
        "pregunta_texto": (
            "¿Usa maquinaria pesada con frecuencia (tractor, cosechadora)? "
            "Responda *sí* o *no*. Si no sabe, escriba OMITIR."
        ),
        "tipo_dato": "bool",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "es_opcional": True,
        "usar_llm_parseo": False,
        "texto_reintento": "Responda sí o no, por favor. O OMITIR.",
    },
    {
        "orden": 7,
        "campo_destino": "usa_enmiendas_cal",
        "pregunta_texto": (
            "¿Aplica enmiendas como *cal* u otros corretivos al suelo? "
            "Responda *sí* o *no*. Si no sabe, escriba OMITIR."
        ),
        "tipo_dato": "bool",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "es_opcional": True,
        "usar_llm_parseo": False,
        "texto_reintento": "Responda sí o no, por favor. O OMITIR.",
    },
    {
        "orden": 8,
        "campo_destino": "tiene_bosque",
        "pregunta_texto": (
            "¿Tiene áreas de bosque natural, setos o cobertura arbórea que *conserva* "
            "(no cultiva)? Responda *sí* o *no*."
        ),
        "tipo_dato": "bool",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "es_opcional": False,
        "usar_llm_parseo": False,
        "texto_reintento": "Responda solo sí o no, por favor.",
    },
    {
        "orden": 9,
        "campo_destino": "area_bosque_ha",
        "pregunta_texto": (
            "¿Cuántas hectáreas de bosque o cobertura conserva? "
            "Si respondió *no* antes, escriba 0 u *OMITIR*."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 10_000.0,
        "unidad_parseo": "ha",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme hectáreas (ej. 0.5 ha). Si no tiene bosque, 0 u OMITIR."
        ),
    },
]

BLOQUES_GEI = {
    "contexto": {
        "pasos": PASOS_CONTEXTO,
        "nombre_suffix": "Contexto",
        "descripcion": "Datos de contexto y variables base (disparo al completar módulo 4).",
    },
    "balance": {
        "pasos": PASOS_BALANCE,
        "nombre_suffix": "Balance",
        "descripcion": "Combustible, residuos, perfil y bosque para el balance (disparo al completar módulo 5).",
    },
}


def es_formulario_balance_gei(tipo_formulario) -> bool:
    """True si el flujo incluye el paso de bosque (bloque balance)."""
    if tipo_formulario is None:
        return False
    return tipo_formulario.flujo_pasos.filter(campo_destino="tiene_bosque").exists()
