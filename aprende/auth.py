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
        est = getattr(request, 'aprende_estudiante', None)
        if not est:
            # Fallback: sesión Studio aún no sincronizada al request
            cuenta = getattr(request, 'cuenta_aula', None)
            if cuenta and cuenta.estudiante_id:
                from .middleware import APRENDE_EST_SESSION_KEY

                request.session[APRENDE_EST_SESSION_KEY] = cuenta.estudiante_id
                request.aprende_estudiante = cuenta.estudiante
                est = cuenta.estudiante
        if not est:
            return redirect('/aprende/estudiante/login/')
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_profesor_aprende(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not es_profesor_aprende(request):
            return redirect('/aprende/profesor/login/')
        pu = request.portal_usuario
        if pu.debe_cambiar_credenciales and not request.path.startswith('/portal/primer-acceso'):
            return redirect('/portal/primer-acceso/')
        return view_func(request, *args, **kwargs)

    return wrapper
