"""Conector FAO para Ventas eki. Repositorio público DSpace, igual que Agrosavia.

El WAF de openknowledge.fao.org responde 403 al User-Agent de requests.
Verificado el 8 de octubre de 2026: hace falta un User-Agent de navegador.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = 'https://openknowledge.fao.org/server/api'
HANDLE_BASE = 'https://openknowledge.fao.org/handle'
TIMEOUT = 12
# Verificado 2026-10-08: sin este encabezado Graph/WAF de FAO devuelve 403.
_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
)

_VENTAS_HINTS = re.compile(
    r'\b('
    r'vent[aeo]|vend[eio]|cliente|precio|margen|negoci|objeci[oó]n|comprador|'
    r'mercado|asociaci[oó]n|cooperativa|cierre|prospect|comercial|'
    r'descuento|ganancia|utilidad|oferta|pedido'
    r')\b',
    re.IGNORECASE,
)


def fao_habilitado() -> bool:
    return bool(getattr(settings, 'BOT_VENTAS_FAO_ENABLED', True))


def _fao_size() -> int:
    try:
        v = int(getattr(settings, 'BOT_VENTAS_FAO_SIZE', 3) or 3)
    except (TypeError, ValueError):
        v = 3
    return max(1, min(v, 5))


def _fao_max_chars() -> int:
    try:
        v = int(getattr(settings, 'BOT_VENTAS_FAO_MAX_CHARS', 1800) or 1800)
    except (TypeError, ValueError):
        v = 1800
    return max(400, min(v, 3000))


def debe_consultar_fao(query: str) -> bool:
    """Solo preguntas comerciales. Plagas, hábitos e IA no consultan la FAO."""
    if not fao_habilitado():
        return False
    q = (query or '').strip()
    if len(q) < 8:
        return False
    return bool(_VENTAS_HINTS.search(q))


def buscar_fao(query: str, *, size: int | None = None) -> list[dict[str, Any]]:
    if not fao_habilitado() or not (query or '').strip():
        return []
    size = _fao_size() if size is None else max(1, min(int(size or 3), 5))
    try:
        resp = requests.get(
            f'{API_BASE}/discover/search/objects',
            params={'query': query.strip(), 'size': size, 'dsoType': 'Item'},
            timeout=TIMEOUT,
            headers={
                'Accept': 'application/json',
                'User-Agent': _USER_AGENT,
                'Referer': 'https://openknowledge.fao.org/',
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning('[FAO] Búsqueda falló: %s', exc)
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
        tipo = _primer_valor(meta, 'dc.type') or ''
        url = f'{HANDLE_BASE}/{handle}' if handle else ''
        items.append({
            'titulo': titulo[:300],
            'abstract': abstract[:900],
            'handle': handle,
            'url': url,
            'tipo': tipo,
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


def formatear_contexto_fao(items: list[dict], max_chars: int | None = None) -> str:
    if not items:
        return ''
    if max_chars is None:
        max_chars = _fao_max_chars()
    partes = [
        'FUENTE INSTITUCIONAL FAO (cite el documento y atribuya a la FAO; '
        'no invente precios ni cifras que no estén aquí):',
    ]
    for i, it in enumerate(items, 1):
        bloque = f"\n[{i}] {it.get('titulo', '')}"
        if it.get('tipo'):
            bloque += f" ({it['tipo']})"
        if it.get('abstract'):
            bloque += f"\n{it['abstract']}"
        if it.get('url'):
            bloque += f"\nReferencia: {it['url']}"
        partes.append(bloque)
    texto = '\n'.join(partes)
    if len(texto) > max_chars:
        texto = texto[: max_chars - 20] + '\n…[truncado]'
    return texto


def enriquecer_contexto_fao(
    consulta: str,
    contexto_rag: str = '',
) -> tuple[str, dict[str, Any]]:
    """Consulta la FAO si la pregunta es de ventas y concatena al conocimiento ya aprobado."""
    meta: dict[str, Any] = {
        'fao_usada': False,
        'fao_items': 0,
        'fao_chars': 0,
        'fao_consultada': False,
    }
    rag = (contexto_rag or '').strip()
    if not debe_consultar_fao(consulta):
        return rag, meta

    meta['fao_consultada'] = True
    items = buscar_fao(consulta)
    ctx = formatear_contexto_fao(items)
    if not ctx:
        return rag, meta

    meta['fao_usada'] = True
    meta['fao_items'] = len(items)
    meta['fao_chars'] = len(ctx)
    logger.info(
        'ventas_fao_uso | items=%s chars=%s rag_prev=%s',
        meta['fao_items'],
        meta['fao_chars'],
        len(rag),
    )
    if rag:
        return f'{rag}\n\n{ctx}'.strip(), meta
    return ctx, meta
