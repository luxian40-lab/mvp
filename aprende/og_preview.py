"""Helpers de vista previa de enlaces (WhatsApp / Open Graph)."""

from __future__ import annotations

from django.contrib.staticfiles.storage import staticfiles_storage

from core.host_isolation import absolute_path

_CRAWLER_UA = (
    'whatsapp',
    'facebookexternalhit',
    'facebot',
    'twitterbot',
    'linkedinbot',
    'slackbot',
    'discordbot',
    'telegrambot',
    'preview',
)


def es_crawler_vista_previa(request) -> bool:
    ua = (request.META.get('HTTP_USER_AGENT') or '').lower()
    return any(n in ua for n in _CRAWLER_UA)


def url_og_image_aprende(request=None) -> str:
    """URL absoluta HTTPS de la imagen OG (1200×630) para WhatsApp."""
    path = staticfiles_storage.url('aprende/og-aprende.png')
    if path.startswith('http'):
        return path
    return absolute_path('aprende', path, request=request)
