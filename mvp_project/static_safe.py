"""static() que no tumba el admin si falta el manifiesto (EB setenv sin collectstatic)."""

from __future__ import annotations

from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static


def static_safe(path: str) -> str:
    try:
        return static(path)
    except ValueError:
        try:
            return staticfiles_storage.url(path)
        except Exception:
            return f'/static/{path.lstrip("/")}'
