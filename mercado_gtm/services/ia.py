"""Capa IA: extracción, GTM y chat — reutiliza OPENAI_API_KEY (gpt-4o-mini). Sin credenciales nuevas."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

MODELO = 'gpt-4o-mini'
URL_MARGEN = '/calculadora-margen/'


def _limpiar_json(raw: str) -> str:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _openai_json(prompt: str, *, max_tokens: int = 1200) -> dict[str, Any]:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('Servicio de IA no disponible.')

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = os.getenv('MERCADO_GTM_MODEL', MODELO)
        response = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.35,
            max_tokens=max_tokens,
            response_format={'type': 'json_object'},
        )
        raw = response.choices[0].message.content or ''
    except Exception as exc:
        logger.warning('mercado_gtm IA error: %s', exc)
        raise RuntimeError('No se pudo completar la consulta de IA.') from exc

    try:
        data = json.loads(_limpiar_json(raw))
    except json.JSONDecodeError as exc:
        raise RuntimeError('La IA devolvió un formato inválido.') from exc
    if not isinstance(data, dict):
        raise RuntimeError('La IA devolvió un formato inválido.')
    return data


def extraer_contexto(texto_libre: str) -> dict[str, Any]:
    texto = (texto_libre or '').strip()
    if len(texto) < 8:
        raise ValueError('Cuéntanos un poco más: qué vendes y dónde quieres venderlo.')

    prompt = f"""Eres asesor comercial agro-rural de eki (Colombia). Extrae datos del texto del productor.
Responde SOLO JSON con esta forma exacta:
{{
  "producto": "",
  "categoria": "",
  "ubicacion_actual": "",
  "mercado_objetivo": "",
  "cliente_actual": "",
  "cliente_potencial": "",
  "tipo_negocio": "B2B|B2C|mixto",
  "presentacion": "",
  "unidad_venta": "unidad|kg|litro|bulto|caja"
}}
Si algo no está claro, deja string vacío. No inventes precios ni números de mercado.
Texto del usuario:
\"\"\"{texto[:2000]}\"\"\""""

    data = _openai_json(prompt, max_tokens=600)
    # Normalizar claves
    out = {
        'producto': str(data.get('producto') or '').strip()[:200],
        'categoria': str(data.get('categoria') or '').strip()[:120],
        'ubicacion_actual': str(data.get('ubicacion_actual') or '').strip()[:200],
        'mercado_objetivo': str(data.get('mercado_objetivo') or '').strip()[:200],
        'cliente_actual': str(data.get('cliente_actual') or '').strip()[:200],
        'cliente_potencial': str(data.get('cliente_potencial') or '').strip()[:200],
        'tipo_negocio': str(data.get('tipo_negocio') or 'mixto').strip()[:20],
        'presentacion': str(data.get('presentacion') or '').strip()[:120],
        'unidad_venta': str(data.get('unidad_venta') or 'unidad').strip()[:40],
    }
    if out['tipo_negocio'] not in ('B2B', 'B2C', 'mixto'):
        out['tipo_negocio'] = 'mixto'
    return out


def generar_gtm(escenario: dict[str, Any]) -> dict[str, Any]:
    """GTM + explicación embudo. Números ya calculados — la IA no debe inventar cifras."""
    falta_margen = not escenario.get('tiene_margen') and (
        _safe_float(escenario.get('precio')) <= 0
        or escenario.get('recomendar_margen')
    )

    prompt = f"""Eres asesor GTM de eki para pymes agro-rurales colombianas. Lenguaje sencillo, sin jerga.
eki siempre en minúsculas. No inventes ni corrijas cifras: usa solo las del escenario.

Escenario (números YA calculados):
{json.dumps(escenario, ensure_ascii=False, default=str)[:4500]}

Responde SOLO JSON:
{{
  "explicacion_embudo": "texto corto TAM→SAM→SOM en lenguaje llano",
  "segmento_recomendado": {{"nombre": "", "por_que": ""}},
  "gtm": {{
    "cliente_prioritario": {{"quien": "", "por_que": ""}},
    "oferta_inicial": "",
    "canal_prioritario": ["máx 2 canales"],
    "mensaje_comercial": "texto listo para copiar/pegar",
    "meta_comercial": "meta 30 días concreta",
    "plan_30_dias": {{
      "semana_1": ["máx 5 acciones"],
      "semana_2": ["máx 5 acciones"],
      "semana_3": ["máx 5 acciones"],
      "semana_4": ["máx 5 acciones"]
    }}
  }},
  "recomienda_calculadora_margen": true/false,
  "nota_margen": "si aplica, recomienda usar la Calculadora de Costos, Precio y Margen de eki"
}}
{"IMPORTANTE: falta información de margen/precio sólido — recomienda explícitamente usar la Calculadora de Costos, Precio y Margen (" + URL_MARGEN + ") y NO inventes un margen." if falta_margen else "Si el precio parece sólido, recomienda_calculadora_margen puede ser false."}"""

    data = _openai_json(prompt, max_tokens=1800)
    gtm = data.get('gtm') if isinstance(data.get('gtm'), dict) else {}
    if falta_margen:
        data['recomienda_calculadora_margen'] = True
        if not data.get('nota_margen'):
            data['nota_margen'] = (
                'Para fijar precio y oferta con margen real, usa la Calculadora de Costos, '
                f'Precio y Margen de eki ({URL_MARGEN}).'
            )
    return {
        'explicacion_embudo': str(data.get('explicacion_embudo') or ''),
        'segmento_recomendado': data.get('segmento_recomendado') or {},
        'gtm': gtm,
        'recomienda_calculadora_margen': bool(data.get('recomienda_calculadora_margen')),
        'nota_margen': str(data.get('nota_margen') or ''),
    }


def responder_pregunta(pregunta: str, escenario: dict[str, Any]) -> dict[str, Any]:
    q = (pregunta or '').strip()
    if len(q) < 3:
        raise ValueError('Escribe tu pregunta.')

    prompt = f"""Eres el chat de la herramienta eki | Encuentra tu mercado.
Responde en español sencillo. Usa SOLO los números del escenario; no recalcules a ojo.
Si el usuario pide simular (“qué pasaría si”), indícale que use el simulador de la pantalla
(no inventes cifras nuevas). Si falta margen para decidir precio, recomienda la Calculadora de margen.

Escenario:
{json.dumps(escenario, ensure_ascii=False, default=str)[:4000]}

Pregunta: {q[:800]}

Responde SOLO JSON: {{"respuesta": "texto claro y accionable"}}"""

    data = _openai_json(prompt, max_tokens=700)
    return {'respuesta': str(data.get('respuesta') or '').strip()}


def _safe_float(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0
