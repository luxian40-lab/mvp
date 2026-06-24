"""Helpers de acceso para el aula web."""

from functools import wraps

from django.shortcuts import redirect

from portal.models import PortalUsuario

ROLES_PROFESOR = frozenset({'admin', 'profesor'})


def es_profesor_aprende(request) -> bool:
    pu = getattr(request, 'portal_usuario', None)
    return bool(pu and pu.rol in ROLES_PROFESOR)


def requiere_estudiante_aprende(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'aprende_estudiante', None):
            return redirect('/aprende/estudiante/login/')
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_profesor_aprende(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not es_profesor_aprende(request):
            return redirect('/aprende/profesor/login/')
        return view_func(request, *args, **kwargs)

    return wrapper
