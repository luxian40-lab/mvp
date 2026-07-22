"""Autorización en el portal B2B."""

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect


def es_eki_ops(request_or_pu) -> bool:
    """True si el usuario portal tiene rol equipo eki (ops)."""
    pu = request_or_pu
    if hasattr(request_or_pu, 'portal_usuario') or hasattr(request_or_pu, 'META'):
        pu = getattr(request_or_pu, 'portal_usuario', None)
    return bool(pu and getattr(pu, 'rol', None) == 'eki_ops')


def requiere_portal_admin(view_func):
    """Solo usuarios portal con rol admin (cliente B2B)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .capabilities import portal_home_url

        pu = getattr(request, 'portal_usuario', None)
        if not pu or pu.rol != 'admin':
            org = getattr(pu, 'organizacion', None) if pu else None
            return redirect(portal_home_url(org) if org else '/portal/login/')
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_eki_ops(view_func):
    """Solo equipo eki (semi-admin). Clientes B2B no entran."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .capabilities import portal_home_url

        pu = getattr(request, 'portal_usuario', None)
        if not es_eki_ops(pu):
            wants_json = (
                request.headers.get('Accept', '').find('application/json') >= 0
                or request.path.startswith('/portal/ops/api/')
            )
            if wants_json:
                return JsonResponse({'ok': False, 'error': 'Sin permiso'}, status=403)
            org = getattr(pu, 'organizacion', None) if pu else None
            return redirect(portal_home_url(org) if org else '/portal/login/')
        return view_func(request, *args, **kwargs)

    return wrapper
