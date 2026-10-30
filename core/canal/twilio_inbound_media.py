"""Descarga de media inbound Twilio (notas de voz / fotos) sin romper redirects a S3."""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_REDIRECTS = frozenset({301, 302, 303, 307, 308})


def es_audio_inbound_twilio(
    num_media, media_type: Optional[str], media_url: Optional[str]
) -> bool:
    """True si el webhook trae una nota de voz (aunque el MIME venga vacío)."""
    try:
        n = int(num_media or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return False
    t = (media_type or '').lower()
    u = (media_url or '').lower()
    if any(k in t for k in ('audio', 'ogg', 'opus', 'amr', 'mpeg', 'mp4', 'aac', 'wav', 'webm')):
        if t.startswith('image/') or t.startswith('video/'):
            return 'audio' in t
        if t.startswith('video/') and 'audio' not in t:
            return False
        return True
    if t.startswith('image/') or t.startswith('video/'):
        return False
    if 'api.twilio.com' in u and '/media/' in u:
        return True
    if any(ext in u for ext in ('.ogg', '.opus', '.amr', '.m4a', '.mp3', '.wav', '.webm')):
        return True
    return False


def descargar_bytes_twilio(media_url: str, *, timeout: int = 25) -> tuple[bytes, str]:
    """
    GET autenticado a Twilio; si redirige a S3, el segundo GET va **sin** Basic auth.
    (Si se reenvía el auth al bucket, S3 responde 403 y Whisper no recibe el audio.)
    """
    if not media_url:
        return b'', ''
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '') or ''
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '') or ''
    auth = (sid, token) if sid and token else None
    resp = requests.get(
        media_url, auth=auth, timeout=timeout, allow_redirects=False,
    )
    if resp.status_code in _REDIRECTS:
        loc = (resp.headers.get('Location') or '').strip()
        if not loc:
            resp.raise_for_status()
            return b'', ''
        loc = urljoin(media_url, loc)
        resp = requests.get(loc, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp.content or b'', (resp.headers.get('Content-Type') or '')
