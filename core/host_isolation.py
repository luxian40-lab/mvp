"""Aislamiento por subdominio: cada producto solo en su host.

Evita que /admin/ sea usable desde app/aprende/studio y que las rutas
cruzadas queden abiertas en producción.
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

ADMIN_HOSTS = frozenset({'admin.eki.technology'})
APP_HOSTS = frozenset({'app.eki.technology'})
STUDIO_HOSTS = frozenset({'studio.eki.technology'})
APRENDE_HOSTS = frozenset({'aprende.eki.technology', 'aula.eki.technology'})

# Prefijos siempre permitidos en cualquier host (health, webhooks, estáticos).
_ALWAYS_OK_PREFIXES = (
    '/health/',
    '/healthz/',
    '/webhook/',
    '/static/',
    '/media/',
    '/verificar-certificado/',
    '/verificar/',
    '/descargar-certificado/',
    '/api/certificados/',
)


def hostname(request) -> str:
    return (request.get_host() or '').split(':')[0].lower().strip()


def host_isolation_disabled(request) -> bool:
    """Local / tests: no bloquear (un solo host sirve todos los paths)."""
    if getattr(settings, 'EKI_DISABLE_HOST_ISOLATION', False):
        return True
    if settings.DEBUG:
        return True
    h = hostname(request)
    return h in {'localhost', '127.0.0.1', 'testserver', '0.0.0.0'} or h.endswith('.local')


def public_base(product: str, request=None) -> str:
    """Base URL canónica de un producto (sin slash final)."""
    overrides = {
        'admin': getattr(settings, 'ADMIN_PUBLIC_URL', '') or 'https://admin.eki.technology',
        'app': getattr(settings, 'APP_PUBLIC_URL', '') or 'https://app.eki.technology',
        'studio': getattr(settings, 'STUDIO_PUBLIC_URL', '') or 'https://studio.eki.technology',
        'aprende': getattr(settings, 'APRENDE_PUBLIC_URL', '') or 'https://aprende.eki.technology',
    }
    base = (overrides.get(product) or '').rstrip('/')
    if request is not None and host_isolation_disabled(request):
        # Mismo origen en local/tests.
        return ''
    return base


def absolute_path(product: str, path: str, request=None) -> str:
    if not path.startswith('/'):
        path = '/' + path
    base = public_base(product, request)
    return f'{base}{path}' if base else path


class HostIsolationMiddleware:
    """
    - /admin/ solo en admin.*
    - /portal/ solo en app.*
    - /studio/ solo en studio.* (webhook Wompi permitido global por ALWAYS)
    - /aprende/ solo en aprende.* / aula.*
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if host_isolation_disabled(request):
            return self.get_response(request)

        path = request.path or '/'
        for prefix in _ALWAYS_OK_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)
        # Webhook Wompi vive bajo /studio/ pero lo llama Wompi sin cookie de host.
        if path.startswith('/studio/webhook/'):
            return self.get_response(request)

        host = hostname(request)
        target = self._required_product(path)
        if target is None:
            return self.get_response(request)

        allowed = {
            'admin': ADMIN_HOSTS,
            'app': APP_HOSTS,
            'studio': STUDIO_HOSTS,
            'aprende': APRENDE_HOSTS,
        }[target]

        if host in allowed:
            return self.get_response(request)

        # Redirigir al host correcto (mismo path + query).
        dest = absolute_path(target, path, request=None)
        qs = request.META.get('QUERY_STRING', '')
        if qs:
            dest = f'{dest}?{qs}'
        if dest.startswith('http'):
            return redirect(dest)
        return HttpResponseForbidden('Host no autorizado para esta ruta.')

    @staticmethod
    def _required_product(path: str) -> str | None:
        if path.startswith('/admin'):
            return 'admin'
        if path.startswith('/portal'):
            return 'app'
        if path.startswith('/studio'):
            return 'studio'
        if path.startswith('/aprende'):
            return 'aprende'
        return None
