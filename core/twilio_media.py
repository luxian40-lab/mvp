"""Utilidades Twilio WhatsApp media: normalización, errores y fallback a enlace."""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Fallos de adjunto: sync (excepciona create) o async (status callback undelivered).
CODIGOS_FALLA_MEDIA_TWILIO = frozenset({'63019', '63021', '63005'})

_MEDIA_MARKER_RE = re.compile(r'\[MEDIA:(.+?)\]', re.DOTALL)


def es_error_media_twilio(err) -> bool:
    """True si el error/string/código indica rechazo o fallo de media WhatsApp."""
    if err is None:
        return False
    if isinstance(err, (int, float)):
        return str(int(err)) in CODIGOS_FALLA_MEDIA_TWILIO
    s = str(err)
    return any(code in s for code in CODIGOS_FALLA_MEDIA_TWILIO)


def normalizar_media_url_s3(url: Optional[str]) -> Optional[str]:
    """
    URL pública regional (us-east-2). Evita redirects .s3.amazonaws.com → región
    que suelen terminar en 63019/63021.
    """
    if not url:
        return None
    clean = str(url).strip()
    if not clean:
        return None
    if 'amazonaws.com' in clean and '.s3.amazonaws.com/' in clean and '.s3.us-east-2.amazonaws.com/' not in clean:
        clean = clean.replace('.s3.amazonaws.com/', '.s3.us-east-2.amazonaws.com/')
    return clean


def cuerpo_con_enlace_archivo(body: str, media_url: str) -> str:
    base = (body or '').strip()
    url = (media_url or '').strip()
    extra = f'📎 Archivo: {url}' if url else ''
    if not extra:
        return base
    if url and url in base:
        return base
    return f'{base}\n\n{extra}'.strip() if base else extra


def mensaje_log_con_media(texto: str, media_url: Optional[str], max_len: int = 1500) -> str:
    """Persiste el marcador [MEDIA:url] para poder reintentar por status callback."""
    body = (texto or '').strip()
    url = (media_url or '').strip()
    if not url:
        return body[:max_len]
    if f'[MEDIA:{url}]' in body or f'[MEDIA:{url[:80]}' in body:
        return body[:max_len]
    marker = f'[MEDIA:{url}]'
    if not body:
        return marker[:max_len]
    combined = f'{body}\n{marker}'
    return combined[:max_len]


def extraer_media_url_de_mensaje(mensaje: Optional[str]) -> Optional[str]:
    if not mensaje:
        return None
    m = _MEDIA_MARKER_RE.search(mensaje)
    if not m:
        return None
    return (m.group(1) or '').strip() or None


def url_no_es_media_directo(url: str) -> bool:
    """Páginas (YouTube/Drive/Vimeo) que Twilio no puede adjuntar como video."""
    u = (url or '').strip().lower()
    if not u:
        return False
    if u.endswith(('.mp4', '.mov', '.3gp', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.ogg', '.mp3')):
        return False
    if '/videoplayback' in u:
        return False
    host_hints = (
        'youtube.com/watch',
        'youtu.be/',
        'youtube.com/shorts/',
        'youtube.com/embed/',
        'vimeo.com/',
        'drive.google.com/',
        'docs.google.com/',
    )
    return any(h in u for h in host_hints)


def marcar_fallback_enlace(error_detalle: Optional[str]) -> str:
    base = (error_detalle or '').strip()
    tag = 'FALLBACK_ENLACE'
    if tag in base:
        return base
    return f'{base} | {tag}'.strip(' |') if base else tag


def ya_envio_fallback_enlace(log) -> bool:
    detalle = getattr(log, 'error_detalle', None) or ''
    mensaje = getattr(log, 'mensaje', None) or ''
    if 'FALLBACK_ENLACE' in detalle:
        return True
    if '📎 Archivo:' in mensaje and '[MEDIA:' not in mensaje:
        return True
    return False
