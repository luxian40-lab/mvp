"""Recomendaciones cualitativas vía OpenAI (gpt-4o-mini) — sin cálculos."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

MODELO = 'gpt-4o-mini'


def _limpiar_json_markdown(raw: str) -> str:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _armar_prompt(datos: dict[str, Any]) -> str:
    desglose_lineas = []
    for item in datos.get('desglose_costos') or []:
        desglose_lineas.append(f"- {item['rubro']}: ${item['monto']:,.0f}")
    desglose_txt = '\n'.join(desglose_lineas) if desglose_lineas else '(sin desglose)'

    return f"""Eres un asesor de negocios agropecuarios de eki, experto en costos y precios para
pequeños productores en Colombia.

Datos del negocio:
- Producto: {datos.get('producto', '')}
- Producción: {datos.get('cantidad_producida')} {datos.get('unidad', '')}
- Costo unitario estimado: ${datos.get('costo_unitario', 0):,.0f}
- Precio de venta actual: ${datos.get('precio_actual', 0):,.0f}
- Margen actual: {datos.get('margen_actual', 0)}%
- Precio sugerido para margen del 25%: ${datos.get('precio_sugerido_25', 0):,.0f}
- Desglose de costos:
{desglose_txt}
- El rubro que más pesa en el costo es "{datos.get('mayor_costo', '')}" con {datos.get('mayor_costo_pct', 0)}% del costo variable.

Responde SOLO con un objeto JSON (sin markdown, sin texto adicional) con esta forma:
{{
  "resumen": "una frase corta y directa sobre la situación de margen de este negocio",
  "recomendaciones": ["lista de exactamente 5 recomendaciones concretas y accionables,
  en español sencillo, específicas a estos números y a este producto agropecuario.
  Deben variar entre: revisar costos puntuales, negociar el insumo más pesado,
  evaluar venta directa, ajustar precio, y simular escenarios de producción.
  No uses relleno genérico, usa los números reales dados."]
}}"""


def generar_recomendaciones_ia(datos: dict[str, Any]) -> dict[str, Any]:
    """
    Llama OpenAI (misma credencial OPENAI_API_KEY del proyecto).
    Devuelve {"resumen": str, "recomendaciones": list[str]} o lanza RuntimeError.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('Servicio de recomendaciones no disponible.')

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv('CALCULADORA_MARGEN_MODEL', MODELO),
            messages=[
                {'role': 'user', 'content': _armar_prompt(datos)},
            ],
            temperature=0.4,
            max_tokens=900,
            response_format={'type': 'json_object'},
        )
        raw = response.choices[0].message.content or ''
    except Exception as exc:
        logger.warning('calculadora_margen IA error: %s', exc)
        raise RuntimeError('No se pudieron generar recomendaciones.') from exc

    try:
        parsed = json.loads(_limpiar_json_markdown(raw))
    except json.JSONDecodeError as exc:
        logger.warning('calculadora_margen JSON inválido: %s', raw[:300])
        raise RuntimeError('Respuesta de IA inválida.') from exc

    resumen = str(parsed.get('resumen', '')).strip()
    recs = parsed.get('recomendaciones') or []
    if not isinstance(recs, list):
        recs = []
    recs = [str(r).strip() for r in recs if str(r).strip()][:5]
    while len(recs) < 5:
        recs.append('Revise sus costos con un asesor local y compare precios de mercado.')

    return {'resumen': resumen, 'recomendaciones': recs}
