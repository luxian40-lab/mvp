"""Rate limit para endpoints de IA de mercado_gtm."""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


def _client_ip(request) -> str:
    xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if xff:
        return xff.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip() or 'unknown'


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or 'anon'


def rate_limit_ia(request) -> JsonResponse | None:
    """Máx. 20 llamadas IA / hora por sesión + IP."""
    limit = int(getattr(settings, 'MERCADO_GTM_IA_RATE_LIMIT', 20) or 20)
    period = int(getattr(settings, 'MERCADO_GTM_IA_RATE_PERIOD', 3600) or 3600)
    if limit <= 0:
        return None

    ip = _client_ip(request)
    sid = _session_key(request)
    cache_key = f'mercado_gtm_ia:{sid}:{ip}'
    count = cache.get(cache_key, 0)
    if count >= limit:
        return JsonResponse(
            {'success': False, 'error': 'Has alcanzado el límite de consultas. Intenta más tarde.'},
            status=429,
        )
    cache.set(cache_key, count + 1, period)
    return None
