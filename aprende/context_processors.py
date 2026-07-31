"""Contexto OG / WhatsApp para plantillas Aprende."""

from __future__ import annotations


def aprende_social(request):
    path = request.path or ''
    if not path.startswith('/aprende'):
        return {}
    from aprende.og_preview import url_og_image_aprende

    return {
        'aprende_og_image': url_og_image_aprende(request),
        'aprende_og_url': request.build_absolute_uri(path.split('?')[0] or '/aprende/'),
    }
