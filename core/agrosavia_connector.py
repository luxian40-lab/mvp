"""Conector AGROSAVIA Nivel 1 — consulta en vivo vía API DSpace."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = 'https://repository.agrosavia.co/server/api'
TIMEOUT = 12

# Señales de consulta técnica agro (P0: enriquecer aunque RAG no esté vacío).
_AGRO_HINTS = re.compile(
    r'\b('
    r'plaga|enfermedad|hongo|virus|bacteri|nematod|insecto|ácaro|acaro|'
    r'fertiliz|abono|dosis|siembra|cosecha|riego|suelo|ph\b|nutri|'
    r'mancha|clorosis|marchitez|pudrici[oó]n|Roya|antracnosis|'
    r'caf[eé]|cacao|arroz|ma[ií]z|papa|aguacate|c[ií]trico|banano|'
    r'ca[nñ]a|palma|tomate|cebolla|frijol|fr[ií]jol|yuca|pasto|'
    r'herbicida|fungicida|insecticida|MIP|BPA|ICA|Agrosavia'
    r')\b',
    re.IGNORECASE,
)


def agrosavia_habilitado() -> bool:
    return bool(getattr(settings, 'BOT_COMERCIAL_AGROSAVIA_ENABLED', True))


def _agrosavia_min_rag_chars() -> int:
    try:
        v = int(getattr(settings, 'BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS', 1400) or 1400)
    except (TypeError, ValueError):
        v = 1400
    return max(200, min(v, 4000))


def _agrosavia_size() -> int:
    try:
        v = int(getattr(settings, 'BOT_COMERCIAL_AGROSAVIA_SIZE', 3) or 3)
    except (TypeError, ValueError):
        v = 3
    return max(1, min(v, 8))


def _agrosavia_max_chars() -> int:
    try:
        v = int(getattr(settings, 'BOT_COMERCIAL_AGROSAVIA_MAX_CHARS', 2200) or 2200)
    except (TypeError, ValueError):
        v = 2200
    return max(600, min(v, 4000))


def debe_consultar_agrosavia(query: str, *, contexto_rag_chars: int = 0) -> bool:
    """Decide si conviene consultar el repo público en vivo.

    P0: más agresivo que el umbral fijo de 500 chars —
    - RAG corto → siempre (si hay query).
    - RAG medio + consulta con pistas agro → también.
    """
    if not agrosavia_habilitado():
        return False
    q = (query or '').strip()
    if len(q) < 3:
        return False
    try:
        chars = int(contexto_rag_chars or 0)
    except (TypeError, ValueError):
        chars = 0
    chars = max(0, chars)
    min_rag = _agrosavia_min_rag_chars()
    if chars < min_rag:
        return True
    # Con RAG ya largo, solo si la pregunta parece técnica de campo.
    if chars < min_rag + 800 and _AGRO_HINTS.search(q):
        return True
    return False


def buscar_agrosavia(query: str, *, size: int | None = None) -> list[dict[str, Any]]:
    """Busca ítems en el repositorio AGROSAVIA. Devuelve lista con título, resumen, handle."""
    if not agrosavia_habilitado() or not (query or '').strip():
        return []

    size = _agrosavia_size() if size is None else max(1, min(int(size or 3), 8))
    try:
        resp = requests.get(
            f'{API_BASE}/discover/search/objects',
            params={'query': query.strip(), 'size': size, 'dsoType': 'Item'},
            timeout=TIMEOUT,
            headers={'Accept': 'application/json'},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning('[Agrosavia] Búsqueda falló: %s', exc)
        return []

    items = []
    embedded = (data.get('_embedded') or {}).get('searchResult', {})
    for obj in (embedded.get('_embedded') or {}).get('objects', []):
        indexable = (obj.get('_embedded') or {}).get('indexableObject', {})
        if not indexable:
            continue
        meta = _metadata_map(indexable.get('metadata') or {})
        titulo = _primer_valor(meta, 'dc.title') or indexable.get('name') or ''
        abstract = _primer_valor(meta, 'dc.description.abstract') or ''
        handle = indexable.get('handle') or ''
        tipo = _primer_valor(meta, 'dc.type.local') or ''
        cultivo = _primer_valor(meta, 'dc.subject.agrovoc') or ''
        url = f'https://repository.agrosavia.co/handle/{handle}' if handle else ''
        items.append({
            'titulo': titulo[:300],
            'abstract': abstract[:1200],
            'handle': handle,
            'url': url,
            'tipo': tipo,
            'cultivo': cultivo,
        })
    return items


def _metadata_map(raw: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for key, vals in (raw or {}).items():
        if isinstance(vals, list):
            out[key] = [v.get('value', '') for v in vals if isinstance(v, dict)]
    return out


def _primer_valor(meta: dict, key: str) -> str:
    vals = meta.get(key) or []
    return (vals[0] or '').strip() if vals else ''


def formatear_contexto_agrosavia(items: list[dict], max_chars: int | None = None) -> str:
    if not items:
        return ''
    if max_chars is None:
        max_chars = _agrosavia_max_chars()
    partes = [
        'FUENTE INSTITUCIONAL AGROSAVIA (cite la cartilla o manual; atribuya a AGROSAVIA):',
    ]
    for i, it in enumerate(items, 1):
        bloque = f"\n[{i}] {it.get('titulo', '')}"
        if it.get('tipo'):
            bloque += f" ({it['tipo']})"
        if it.get('cultivo'):
            bloque += f" — {it['cultivo']}"
        if it.get('abstract'):
            bloque += f"\n{it['abstract']}"
        if it.get('url'):
            bloque += f"\nReferencia: {it['url']}"
        partes.append(bloque)
    texto = '\n'.join(partes)
    if len(texto) > max_chars:
        texto = texto[: max_chars - 20] + '\n…[truncado]'
    return texto


def enriquecer_contexto_con_agrosavia(
    consulta: str,
    contexto_rag: str = '',
) -> tuple[str, dict[str, Any]]:
    """Consulta live si aplica y concatena al contexto RAG.

    Returns:
        (contexto_actualizado, meta) donde meta incluye usada/items/chars para EventoIA.
    """
    meta: dict[str, Any] = {
        'agrosavia_usada': False,
        'agrosavia_items': 0,
        'agrosavia_chars': 0,
        'agrosavia_consultada': False,
    }
    rag = (contexto_rag or '').strip()
    if not debe_consultar_agrosavia(consulta, contexto_rag_chars=len(rag)):
        return rag, meta

    meta['agrosavia_consultada'] = True
    items = buscar_agrosavia(consulta)
    ctx = formatear_contexto_agrosavia(items)
    if not ctx:
        return rag, meta

    meta['agrosavia_usada'] = True
    meta['agrosavia_items'] = len(items)
    meta['agrosavia_chars'] = len(ctx)
    logger.info(
        'nat_agrosavia_uso | items=%s chars=%s rag_prev=%s',
        meta['agrosavia_items'],
        meta['agrosavia_chars'],
        len(rag),
    )
    if rag:
        return f'{rag}\n\n{ctx}'.strip(), meta
    return ctx, meta
