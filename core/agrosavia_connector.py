"""Conector AGROSAVIA Nivel 1 — consulta en vivo vía API DSpace."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = 'https://repository.agrosavia.co/server/api'
TIMEOUT = 12


def agrosavia_habilitado() -> bool:
    return bool(getattr(settings, 'BOT_COMERCIAL_AGROSAVIA_ENABLED', True))


def buscar_agrosavia(query: str, *, size: int = 3) -> list[dict[str, Any]]:
    """Busca ítems en el repositorio AGROSAVIA. Devuelve lista con título, resumen, handle."""
    if not agrosavia_habilitado() or not (query or '').strip():
        return []

    size = max(1, min(int(size or 3), 8))
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


def formatear_contexto_agrosavia(items: list[dict], max_chars: int = 2200) -> str:
    if not items:
        return ''
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
