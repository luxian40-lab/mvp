"""
Router de modelos para Nat — Opción C (75% mini / 5% nano / 20% GPT-5).

Un solo agente comercial+agrónomo; el usuario no ve el cambio de modelo.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Agro amplio: no solo plagas — nutrición, suelo, clima, ganadería, poscosecha, etc.
_PATRON_TECNICO = re.compile(
    r'\b('
    r'roya|broca|plaga|enfermed|síntoma|sintoma|deficien|clorosis|nutrici|fertiliz|'
    r'dosis|hectárea|hectarea|aplicaci|abono|nitr|fósfor|fosfor|potasio|cal dol|'
    r'suelo|ph\b|riego|sequía|sequia|humedad|mildiu|oidio|gusano|ácaro|acaro|'
    r'cosecha|rendim|variedad|siembra|pod[aá]|poda|injerto|poscosecha|beneficio|'
    r'pollito|ave|bovino|porcino|lote|pasto|forraje|herbic|fungic|insectic|'
    r'café|cafe|cacao|platano|plátano|maíz|maiz|papa|tomate|aguacate|arroz|'
    r'diagnóst|diagnost|mancha|necrosis|marchit|clorof|tensi[oó]n|'
    r'precio|cotiz|catálogo|catalogo|insumo|producto|ficha|'
    r')\b',
    re.I,
)

_PATRON_JERGA_Densa = re.compile(
    r'\b(ppm|mg/l|kg/ha|l/ha|cc/ha|ppm|ph\s*\d|n-p-k|npk|bpm|ica|agrosavia)\b',
    re.I,
)

_SALUDOS = re.compile(
    r'^(hola|buenas|buenos dias|buen día|buenas tardes|buenas noches|hey|gracias|ok|listo)\b',
    re.I,
)


@dataclass(frozen=True)
class NatRoutingDecision:
    modelo: str
    modo: str  # conversacion | tecnico | catalogo | ambiguo
    usar_web: bool
    escala_premium: bool
    razon: str
    rag_max_similitud: float | None = None
    rag_chunks_utiles: int = 0


def _cfg(name: str, default: str) -> str:
    return str(getattr(settings, name, default) or default).strip()


def umbral_similitud_rag() -> float:
    try:
        return float(getattr(settings, 'BOT_COMERCIAL_RAG_MIN_SIMILARITY', 0.52) or 0.52)
    except (TypeError, ValueError):
        return 0.52


def filtrar_chunks_por_similitud(
    chunks: list[dict] | None,
    umbral: float | None = None,
    *,
    incluir_sin_score: bool = False,
) -> list[dict]:
    """
    Quedarse solo con chunks semánticamente útiles para el prompt.
    Por defecto descarta similitud < umbral y los que no traen score.
    """
    if not chunks:
        return []
    if umbral is None:
        umbral = umbral_similitud_rag()
    out: list[dict] = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        s = c.get('similitud')
        if s is None:
            if incluir_sin_score:
                out.append(c)
            continue
        try:
            val = float(s)
        except (TypeError, ValueError):
            continue
        if val >= umbral:
            out.append(c)
    return out


def evaluar_calidad_rag(chunks: list[dict] | None) -> tuple[float | None, int]:
    """Devuelve (max_similitud entre todos, cantidad de chunks >= umbral)."""
    if not chunks:
        return None, 0
    umbral = umbral_similitud_rag()
    sims: list[float] = []
    utiles = 0
    for c in chunks:
        s = c.get('similitud') if isinstance(c, dict) else None
        if s is None:
            continue
        try:
            val = float(s)
        except (TypeError, ValueError):
            continue
        sims.append(val)
        if val >= umbral:
            utiles += 1
    if not sims:
        return None, 0
    return max(sims), utiles


def _densidad_tecnica(mensaje: str) -> int:
    return len(_PATRON_TECNICO.findall(mensaje or '')) + len(_PATRON_JERGA_Densa.findall(mensaje or ''))


def _es_catalogo(mensaje: str) -> bool:
    return bool(re.search(r'precio|precios|cotiz|lista|cat[aá]logo|cu[aá]nto cuesta|valor', mensaje or '', re.I))


def _contexto_agro_suficiente(ctx_agro) -> bool:
    if not ctx_agro:
        return False
    if hasattr(ctx_agro, 'completitud_pct') and ctx_agro.completitud_pct() >= 40:
        return True
    if hasattr(ctx_agro, 'campos_llenos') and len(ctx_agro.campos_llenos()) >= 2:
        return True
    return False


def _clasificar_con_nano(mensaje: str) -> str | None:
    """Clasificador ligero (solo casos ambiguos). Retorna modo o None si falla."""
    if not getattr(settings, 'BOT_COMERCIAL_ROUTER_USE_NANO', True):
        return None
    api_key = (getattr(settings, 'OPENAI_API_KEY', '') or '').strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        from core.openai_compat import chat_completion_token_kwargs

        client = OpenAI(api_key=api_key)
        modelo = _cfg('BOT_COMERCIAL_MODEL_ROUTER', 'gpt-5-nano')
        resp = client.chat.completions.create(
            model=modelo,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Clasifica consultas agrícolas WhatsApp. Responde UNA palabra: '
                        'conversacion, tecnico, catalogo o ambiguo. '
                        'tecnico=plagas, suelo, nutrición, diagnóstico, manejo. '
                        'catalogo=precios/lista productos. '
                        'ambiguo=mensaje confuso o muy corto sin contexto.'
                    ),
                },
                {'role': 'user', 'content': (mensaje or '')[:500]},
            ],
            **chat_completion_token_kwargs(modelo, 24, 0),
        )
        raw = (resp.choices[0].message.content or '').strip().lower()
        for modo in ('catalogo', 'tecnico', 'ambiguo', 'conversacion'):
            if modo in raw:
                return modo
    except Exception as e:
        logger.debug('Nat router nano omitido: %s', e)
    return None


def decidir_routing_nat(
    mensaje: str,
    *,
    rag_chunks: list[dict] | None = None,
    tiene_rag_texto: bool = False,
    contexto_rag_chars: int = 0,
    ctx_agro=None,
    diagnostico_vision: str = '',
    es_saludo: bool = False,
) -> NatRoutingDecision:
    """
    Elige modelo OpenAI y si conviene web complementaria.

    GPT-5 (premium) cuando hace falta lectura precisa de RAG, razonamiento técnico
    o mensaje ambiguo/complejo — no solo plagas.
    """
    modelo_chat = _cfg('BOT_COMERCIAL_OPENAI_MODEL', 'gpt-5-mini')
    modelo_premium = _cfg('BOT_COMERCIAL_MODEL_TECNICO', 'gpt-5')

    texto = (mensaje or '').strip()
    if es_saludo or (len(texto) < 25 and _SALUDOS.match(texto.lower())):
        return NatRoutingDecision(
            modelo=modelo_chat,
            modo='conversacion',
            usar_web=False,
            escala_premium=False,
            razon='saludo_o_cortesia',
        )

    max_sim, chunks_utiles = evaluar_calidad_rag(rag_chunks)
    rag_fuerte = chunks_utiles >= 1 and (max_sim or 0) >= float(
        getattr(settings, 'BOT_COMERCIAL_RAG_MIN_SIMILARITY', 0.52) or 0.52
    )
    if not rag_fuerte and tiene_rag_texto and contexto_rag_chars >= 350:
        rag_fuerte = True
    rag_debil = tiene_rag_texto and not rag_fuerte
    sin_rag = not tiene_rag_texto and not rag_chunks

    densidad = _densidad_tecnica(texto)
    catalogo = _es_catalogo(texto)
    ctx_ok = _contexto_agro_suficiente(ctx_agro)
    tiene_vision = bool((diagnostico_vision or '').strip())
    msg_corto_confuso = len(texto) < 18 and densidad == 0
    msg_denso = len(texto) > 120 or densidad >= 3 or bool(_PATRON_JERGA_Densa.search(texto))

    modo = 'conversacion'
    if catalogo:
        modo = 'catalogo'
    elif densidad >= 1 or tiene_vision or msg_denso:
        modo = 'tecnico'
    elif msg_corto_confuso:
        modo = 'ambiguo'
    elif densidad == 0 and len(texto) > 40:
        modo = 'conversacion'

    if modo == 'conversacion' and densidad == 0 and 18 <= len(texto) <= 80:
        nano_modo = _clasificar_con_nano(texto)
        if nano_modo:
            modo = nano_modo

    usar_web = False
    if getattr(settings, 'BOT_COMERCIAL_WEB_FALLBACK_ENABLED', True):
        if sin_rag and modo in ('tecnico', 'catalogo', 'ambiguo'):
            usar_web = True
        elif rag_debil and modo in ('tecnico', 'catalogo'):
            usar_web = True

    escala_premium = False
    razon = 'conversacion_standard'

    if modo == 'catalogo' and (rag_fuerte or tiene_rag_texto):
        escala_premium = True
        razon = 'catalogo_lectura_precisa_rag'
    elif modo == 'tecnico' and (rag_fuerte or ctx_ok or tiene_vision):
        escala_premium = True
        razon = 'tecnico_contexto_suficiente'
    elif modo == 'tecnico' and (rag_debil or sin_rag) and msg_denso:
        escala_premium = True
        razon = 'tecnico_complejo_sin_rag_fuerte'
    elif modo == 'ambiguo' and (densidad >= 1 or rag_fuerte or tiene_vision):
        escala_premium = True
        razon = 'ambiguo_requiere_precision'
    elif modo == 'tecnico' and rag_fuerte:
        escala_premium = True
        razon = 'tecnico_rag_indexado'

    modelo = modelo_premium if escala_premium else modelo_chat

    return NatRoutingDecision(
        modelo=modelo,
        modo=modo,
        usar_web=usar_web,
        escala_premium=escala_premium,
        razon=razon,
        rag_max_similitud=max_sim,
        rag_chunks_utiles=chunks_utiles,
    )
