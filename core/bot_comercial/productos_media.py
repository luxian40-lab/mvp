"""Adjuntar fotos de productos del catálogo Nat en WhatsApp."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Sequence

from django.db.models import Q

from core.utils import enviar_whatsapp_twilio

logger = logging.getLogger(__name__)

# Formatos flexibles (Nat a veces omite emoji o cambia el layout)
_RE_SKU = re.compile(
    r'(?i)\bSKU\s*[:\-–]?\s*([A-Za-z0-9][A-Za-z0-9\-_.\/]{1,79})\b'
)
_RE_PACK = re.compile(
    r'(?im)^\s*(?:📦|🛍️|🛒)\s*(?:\*\*)?([^*\n]{3,120}?)(?:\*\*)?\s*$'
)
_RE_PRODUCTO_LABEL = re.compile(
    r'(?im)^\s*(?:producto(?:\s+recomendado)?|recomiendo|le recomiendo)\s*[:\-–]\s*(.+?)\s*$'
)


def _uniq(items: list[str]) -> list[str]:
    out, seen = [], set()
    for x in items:
        k = (x or '').strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x.strip())
    return out


def _url_cruda_imagen(producto) -> str:
    img = getattr(producto, 'imagen', None)
    if not img:
        return ''
    try:
        url = (img.url or '').strip()
    except Exception:
        return ''
    if not url:
        return ''
    if url.startswith('https://'):
        return url
    if url.startswith('http://'):
        return 'https://' + url[len('http://'):]
    try:
        from django.conf import settings

        base = (
            getattr(settings, 'APP_PUBLIC_URL', None)
            or getattr(settings, 'MEDIA_HOST', None)
            or ''
        ).rstrip('/')
        if base and url.startswith('/'):
            abs_url = f'{base}{url}'
            if abs_url.startswith('http://'):
                abs_url = 'https://' + abs_url[len('http://'):]
            if abs_url.startswith('https://'):
                return abs_url
    except Exception:
        pass
    return ''


def _asegurar_url_publica_whatsapp(url: str) -> str:
    """
    Twilio necesita URL HTTPS pública.
    Si el objeto S3 es privado, descarga con credenciales y re-sube a
    media/whatsapp_ready/nat_productos/ con ACL public-read.
    """
    url = (url or '').strip()
    if not url.startswith('https://'):
        return ''
    if '/media/whatsapp_ready/nat_productos/' in url:
        return url

    try:
        from core.twilio_media import (
            _descargar_bytes,
            _public_s3_url,
            _subir_bytes_s3,
            normalizar_media_url_s3,
        )
    except Exception:
        return url

    clean = normalizar_media_url_s3(url) or url
    # Ya en bucket eki con path conocido: aún así republicamos si puede ser privado
    try:
        raw = _descargar_bytes(clean, timeout=45)
    except Exception as exc:
        logger.warning('Nat producto: no se pudo leer imagen | %s', exc)
        return clean

    if not raw or len(raw) < 32:
        return clean
    if len(raw) > 4 * 1024 * 1024:
        logger.warning('Nat producto: imagen demasiado grande (%s)', len(raw))
        return ''

    digest = hashlib.sha1(raw).hexdigest()[:20]
    # Detectar extensión básica
    ext = 'jpg'
    low = clean.lower().split('?', 1)[0]
    if low.endswith('.png'):
        ext = 'png'
    elif low.endswith('.webp'):
        ext = 'webp'
    elif low.endswith('.gif'):
        ext = 'gif'
    ctype = {
        'jpg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif',
    }.get(ext, 'image/jpeg')

    key = f'media/whatsapp_ready/nat_productos/{digest}.{ext}'
    # Cache hit
    cached = _public_s3_url(key)
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            's3',
            config=Config(signature_version='s3v4', region_name='us-east-2'),
        )
        client.head_object(Bucket='eki-produccion', Key=key)
        return cached
    except Exception:
        pass

    subida = _subir_bytes_s3(key, raw, ctype)
    if subida:
        logger.info('Nat producto: imagen republicada pública | %s', key)
        return subida
    return clean


def _url_publica_imagen(producto) -> str:
    cruda = _url_cruda_imagen(producto)
    if not cruda:
        return ''
    if 'amazonaws.com' in cruda or 's3.' in cruda:
        return _asegurar_url_publica_whatsapp(cruda) or ''
    return cruda


def extraer_claves_productos_respuesta(texto: str) -> tuple[list[str], list[str]]:
    """Devuelve (skus, nombres) mencionados en la respuesta de Nat."""
    t = texto or ''
    skus = [m.group(1).strip() for m in _RE_SKU.finditer(t) if m.group(1).strip()]
    nombres: list[str] = []
    for m in _RE_PRODUCTO_LABEL.finditer(t):
        nom = (m.group(1) or '').strip().strip('*_ ')
        if nom:
            nombres.append(nom)
    for m in _RE_PACK.finditer(t):
        nom = (m.group(1) or '').strip().strip('*_ ')
        # Evitar títulos genéricos
        low = nom.lower()
        if low.startswith(('sku', 'dosis', 'precio', 'sirve', 'stock', 'comprar', 'verifique')):
            continue
        if nom and low not in {'producto', 'productos', 'recomendado'}:
            nombres.append(nom)
    return _uniq(skus), _uniq(nombres)


def _match_por_nombre_en_texto(qs, texto: str, limite: int, ya: set[int]) -> list:
    """Si el nombre del catálogo aparece en la respuesta, cuenta como mención."""
    t = (texto or '').lower()
    hits = []
    for prod in qs:
        if prod.id in ya:
            continue
        nombre = (prod.nombre or '').strip()
        if len(nombre) < 4:
            continue
        if nombre.lower() in t:
            hits.append(prod)
        if len(hits) >= limite:
            break
    return hits


def fotos_productos_para_whatsapp(
    cliente,
    texto_respuesta: str,
    *,
    limite: int = 2,
) -> list[dict]:
    """
    Productos del catálogo con imagen que Nat mencionó en la respuesta.

    Matching (en orden): SKU flexible → etiquetas/📦 → nombre del catálogo en el texto.
    """
    if not cliente or not (texto_respuesta or '').strip():
        return []

    from core.models import ProductoCatalogo

    skus, nombres = extraer_claves_productos_respuesta(texto_respuesta)
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
            if not prod:
                prod = qs.filter(sku__icontains=sku).first()
            if prod:
                _add(prod)

    if len(elegidos) < limite and nombres:
        for nom in nombres:
            prod = qs.filter(nombre__iexact=nom).first()
            if not prod:
                prod = qs.filter(nombre__icontains=nom).first()
            if prod:
                _add(prod)

    if len(elegidos) < limite:
        for prod in _match_por_nombre_en_texto(
            qs, texto_respuesta, limite - len(elegidos), vistos,
        ):
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
