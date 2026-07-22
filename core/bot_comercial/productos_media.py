"""Adjuntar fotos de productos del catálogo Nat en WhatsApp."""
from __future__ import annotations

import re
from typing import Sequence

from django.db.models import Q

from core.utils import enviar_whatsapp_twilio


_RE_SKU = re.compile(r'(?im)^\s*SKU:\s*([A-Za-z0-9\-_.\/]+)\s*$')
_RE_PACK = re.compile(r'(?im)^\s*📦\s*(.+?)\s*$')


def _url_publica_imagen(producto) -> str:
    img = getattr(producto, 'imagen', None)
    if not img:
        return ''
    try:
        url = (img.url or '').strip()
    except Exception:
        return ''
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url
    # MEDIA relativo: Twilio necesita URL absoluta pública
    try:
        from django.conf import settings

        base = (
            getattr(settings, 'APP_PUBLIC_URL', None)
            or getattr(settings, 'MEDIA_HOST', None)
            or ''
        ).rstrip('/')
        if base and url.startswith('/'):
            return f'{base}{url}'
    except Exception:
        pass
    return url


def extraer_claves_productos_respuesta(texto: str) -> tuple[list[str], list[str]]:
    """Devuelve (skus, nombres) mencionados en la respuesta de Nat."""
    t = texto or ''
    skus = [m.group(1).strip() for m in _RE_SKU.finditer(t) if m.group(1).strip()]
    nombres = []
    for m in _RE_PACK.finditer(t):
        nom = (m.group(1) or '').strip()
        # Quitar markdown residual
        nom = nom.strip('*_ ')
        if nom and nom.lower() not in {'producto', 'productos'}:
            nombres.append(nom)
    # únicos preservando orden
    def _uniq(items: list[str]) -> list[str]:
        out, seen = [], set()
        for x in items:
            k = x.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(x)
        return out

    return _uniq(skus), _uniq(nombres)


def fotos_productos_para_whatsapp(
    cliente,
    texto_respuesta: str,
    *,
    limite: int = 2,
) -> list[dict]:
    """
    Productos del catálogo con imagen que Nat mencionó en la respuesta.

    Retorna lista de dicts: {nombre, url, sku}.
    """
    if not cliente or not (texto_respuesta or '').strip():
        return []

    from core.models import ProductoCatalogo

    skus, nombres = extraer_claves_productos_respuesta(texto_respuesta)
    if not skus and not nombres:
        return []

    qs = ProductoCatalogo.objects.filter(cliente=cliente, activo=True).exclude(
        Q(imagen='') | Q(imagen__isnull=True)
    )
    limite = max(1, min(int(limite or 2), 3))
    elegidos: list[dict] = []
    vistos: set[int] = set()

    def _add(prod) -> None:
        if prod.id in vistos or len(elegidos) >= limite:
            return
        url = _url_publica_imagen(prod)
        if not url:
            return
        vistos.add(prod.id)
        elegidos.append({
            'nombre': prod.nombre,
            'sku': (prod.sku or '').strip(),
            'url': url,
        })

    if skus:
        for sku in skus:
            prod = qs.filter(sku__iexact=sku).first()
            if prod:
                _add(prod)

    if len(elegidos) < limite and nombres:
        for nom in nombres:
            prod = qs.filter(nombre__iexact=nom).first()
            if not prod:
                prod = qs.filter(nombre__icontains=nom).first()
            if prod:
                _add(prod)

    return elegidos


def enviar_fotos_productos_whatsapp(
    telefono: str,
    productos: Sequence[dict],
    *,
    from_number: str | None = None,
) -> list[dict]:
    """Envía cada foto como mensaje WhatsApp aparte (caption = nombre)."""
    resultados = []
    for item in productos or []:
        url = (item.get('url') or '').strip()
        nombre = (item.get('nombre') or 'Producto').strip()
        if not url:
            continue
        caption = f'📦 {nombre}'
        res = enviar_whatsapp_twilio(
            telefono,
            caption,
            media_url=url,
            from_number=from_number,
            canal_evento='whatsapp_comercial',
            agente_evento='nati',
        )
        resultados.append({'nombre': nombre, 'url': url, **(res or {})})
    return resultados
