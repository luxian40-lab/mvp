"""Clasificación y metadatos de multimedia para el aula (solo visualización)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

TIPO_YOUTUBE = 'youtube'
TIPO_VIDEO = 'video'
TIPO_IMAGEN = 'imagen'
TIPO_AUDIO = 'audio'
TIPO_PDF = 'pdf'
TIPO_H5P = 'h5p'
TIPO_EMBED = 'embed'


@dataclass
class MediaAula:
    titulo: str
    url: str
    tipo: str
    youtube_id: str | None = None


def es_url_h5p(url: str) -> bool:
    u = (url or '').lower()
    return 'h5p.org' in u or '/h5p/' in u or 'h5p.com' in u


def youtube_embed_id(url: str) -> str | None:
    if not url:
        return None
    m = re.search(
        r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})',
        url,
    )
    return m.group(1) if m else None


def clasificar_media_url(url: str, tipo_hint: str = '') -> str:
    hint = (tipo_hint or '').lower().strip()
    if hint == 'video':
        if youtube_embed_id(url):
            return TIPO_YOUTUBE
        return TIPO_VIDEO
    if hint in ('imagen', 'infografia'):
        return TIPO_IMAGEN
    if hint == 'audio':
        return TIPO_AUDIO
    if hint == 'pdf':
        return TIPO_PDF

    if youtube_embed_id(url):
        return TIPO_YOUTUBE

    if es_url_h5p(url) or hint in ('h5p', 'interactivo'):
        return TIPO_H5P

    path = urlparse(url).path.lower()
    if path.endswith(('.mp4', '.webm', '.mov', '.m4v')):
        return TIPO_VIDEO
    if path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg')):
        return TIPO_IMAGEN
    if path.endswith(('.mp3', '.wav', '.ogg', '.m4a')):
        return TIPO_AUDIO
    if path.endswith('.pdf') or 'pdf' in path:
        return TIPO_PDF
    return TIPO_EMBED


def media_desde_url(titulo: str, url: str, tipo_hint: str = '') -> MediaAula | None:
    u = (url or '').strip()
    if not u:
        return None
    tipo = clasificar_media_url(u, tipo_hint)
    return MediaAula(
        titulo=(titulo or '').strip() or 'Material',
        url=u,
        tipo=tipo,
        youtube_id=youtube_embed_id(u) if tipo == TIPO_YOUTUBE else None,
    )
