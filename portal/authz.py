"""Autorización en el portal B2B."""

from functools import wraps

from django.shortcuts import redirect


def requiere_portal_admin(view_func):
    """Solo usuarios portal con rol admin."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        pu = getattr(request, 'portal_usuario', None)
        if not pu or pu.rol != 'admin':
            return redirect('/portal/dashboard/')
        return view_func(request, *args, **kwargs)

    return wrapper
