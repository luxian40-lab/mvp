"""
Agente de retención / Centro de Éxito (portal).

Independiente de Nat (comercial/agro). Responde al coordinador con el
contexto analítico del programa. Usa OpenAI si hay API key; si no,
explica con reglas a partir de los datos.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres el consultor de retención de eki (Centro de Éxito del Programa).
Hablas con el coordinador B2B en español claro y accionable.
NO eres Nat (asesor comercial agrícola). Tu foco es: quién abandona, por qué, qué hacer hoy.
Usa SOLO los datos del JSON de contexto. Si falta un dato, dilo.
Responde en párrafos cortos o viñetas. Incluye siempre una recomendación concreta.
"""


def _contexto_compacto(data: dict[str, Any]) -> dict[str, Any]:
    """Reduce el payload analítico para el LLM / reglas."""
    k = data.get('kpis') or {}
    r = (data.get('riesgo') or {}).get('resumen') or {}
    alto = (data.get('riesgo') or {}).get('alto') or []
    curso = data.get('curso')
    if curso is not None and not isinstance(curso, dict):
        curso_nombre = getattr(curso, 'nombre', None)
    elif isinstance(curso, dict):
        curso_nombre = curso.get('nombre')
    else:
        curso_nombre = None
    return {
        'curso': curso_nombre,
        'kpis': {
            'inscritos': k.get('inscritos'),
            'activos': k.get('activos'),
            'inactivos': k.get('inactivos'),
            'certificados': k.get('certificados'),
            'pct_certificacion': k.get('pct_certificacion'),
            'modulo_mayor_abandono': k.get('modulo_mayor_abandono'),
            'tiempo_promedio_abandono_dias': k.get('tiempo_promedio_abandono_dias'),
        },
        'riesgo': r,
        'probabilidad_promedio': r.get('probabilidad_promedio'),
        'ejemplos_alto_riesgo': [
            {
                'nombre': a.get('nombre'),
                'score': a.get('score'),
                'probabilidad_terminar': a.get('probabilidad_terminar'),
                'razones': a.get('razones'),
                'recomendacion': a.get('recomendacion'),
            }
            for a in alto[:8]
        ],
        'mapa_abandono': data.get('mapa_abandono') or [],
        'curva_abandono': data.get('curva_abandono') or [],
        'cohortes': data.get('cohortes') or {},
        'recomendaciones': data.get('recomendaciones') or [],
        'comparativa_eki': data.get('comparativa_eki') or {},
        'whatsapp_health': {
            k2: (data.get('whatsapp_health') or {}).get(k2)
            for k2 in (
                'hora_favorita_programa',
                'dias_favoritos_programa',
                'tiempo_promedio_respuesta_h',
                'mediana_dias_ultimo_mensaje',
            )
        },
    }


def _respuesta_reglas(pregunta: str, ctx: dict[str, Any]) -> str:
    """Fallback sin LLM: arma explicación con los datos."""
    q = (pregunta or '').lower()
    lineas: list[str] = []

    r = ctx.get('riesgo') or {}
    alto_n = r.get('alto') or 0
    medio_n = r.get('medio') or 0
    pred = r.get('probabilidad_promedio')

    lineas.append(
        f"En este filtro hay **{alto_n} en riesgo alto** y **{medio_n} en riesgo medio**."
    )
    if pred is not None:
        lineas.append(f"Probabilidad promedio de terminar (estimada): **{pred}%**.")

    mod = (ctx.get('kpis') or {}).get('modulo_mayor_abandono')
    if mod:
        lineas.append(
            f"El mayor cuello de botella está en el **módulo {mod.get('modulo_numero')}** "
            f"({mod.get('modulo_titulo')}): {mod.get('caidas')} personas no pasaron al siguiente "
            f"(tasa {mod.get('tasa_pct')}%)."
        )

    ejemplos = ctx.get('ejemplos_alto_riesgo') or []
    if ejemplos and any(w in q for w in ('quién', 'quien', 'riesgo', 'juan', 'persona', 'estudiante')):
        lineas.append('')
        lineas.append('Ejemplos en riesgo alto:')
        for e in ejemplos[:3]:
            razones = '; '.join(e.get('razones') or [])
            lineas.append(
                f"- **{e.get('nombre')}** (score {e.get('score')}, "
                f"prob. terminar {e.get('probabilidad_terminar')}%): {razones}"
            )
            if e.get('recomendacion'):
                lineas.append(f"  → {e['recomendacion']}")

    if any(w in q for w in ('por qué', 'porque', 'abandona', 'deserci', 'módulo', 'modulo')):
        mapa = ctx.get('mapa_abandono') or []
        if mapa:
            peor = max(mapa, key=lambda m: m.get('caidas') or 0)
            if peor.get('caidas'):
                lineas.append('')
                lineas.append(
                    f"En el mapa de abandono, el pico está tras el módulo {peor.get('modulo_numero')}: "
                    f"desertan {peor.get('caidas')} personas."
                )

    cohortes = ctx.get('cohortes') or {}
    if cohortes.get('insight') and any(w in q for w in ('cohorte', 'mes', 'julio', 'agosto', 'septiembre')):
        lineas.append('')
        lineas.append(cohortes['insight'])

    wa = ctx.get('whatsapp_health') or {}
    if any(w in q for w in ('whatsapp', 'hora', 'mensaje', 'campaña', 'campana')):
        lineas.append('')
        if wa.get('hora_favorita_programa'):
            lineas.append(
                f"WhatsApp Health: hora favorita del programa **{wa['hora_favorita_programa']}**; "
                f"días {', '.join(wa.get('dias_favoritos_programa') or []) or '—'}."
            )

    recs = ctx.get('recomendaciones') or []
    if recs:
        lineas.append('')
        lineas.append('**Qué hacer hoy:**')
        for rec in recs[:3]:
            lineas.append(f"- {rec.get('titulo')}: {rec.get('detalle')}")

    comp = ctx.get('comparativa_eki') or {}
    if comp.get('disponible') and comp.get('eki_pct') is not None:
        lineas.append('')
        lineas.append(
            f"Comparativa: {comp.get('etiqueta_tu')} **{comp.get('tu_pct')}%** vs promedio eki **{comp.get('eki_pct')}%**."
        )

    return '\n'.join(lineas)


def _llamar_openai(pregunta: str, ctx: dict[str, Any]) -> str | None:
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        return None
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        payload = json.dumps(ctx, ensure_ascii=False, default=str)[:12000]
        resp = client.chat.completions.create(
            model=getattr(settings, 'OPENAI_MODEL_RETENCION', None) or 'gpt-4o-mini',
            temperature=0.3,
            max_tokens=700,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': (
                        f'Datos del programa (JSON):\n{payload}\n\n'
                        f'Pregunta del coordinador:\n{pregunta.strip()}'
                    ),
                },
            ],
        )
        text = (resp.choices[0].message.content or '').strip()
        return text or None
    except Exception as exc:
        logger.warning('Agente retención OpenAI falló: %s', exc)
        return None


def responder_agente_retencion(pregunta: str, data_analitica: dict[str, Any]) -> dict[str, Any]:
    """
    Punto de entrada del agente.

    Returns:
        {respuesta, fuente: 'ia'|'reglas', contexto_usado: bool}
    """
    pregunta = (pregunta or '').strip()
    if not pregunta:
        return {
            'respuesta': 'Escriba una pregunta, por ejemplo: ¿Por qué están abandonando en el módulo 3?',
            'fuente': 'reglas',
            'contexto_usado': False,
        }

    ctx = _contexto_compacto(data_analitica)

    ia = _llamar_openai(pregunta, ctx)
    if ia:
        return {'respuesta': ia, 'fuente': 'ia', 'contexto_usado': True}
    return {
        'respuesta': _respuesta_reglas(pregunta, ctx),
        'fuente': 'reglas',
        'contexto_usado': True,
    }
