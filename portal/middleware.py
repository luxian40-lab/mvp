from django.shortcuts import redirect

from .models import PortalUsuario


PORTAL_SESSION_KEY = 'portal_usuario_id'

_PATHS_SIN_SESION = (
    '/portal/login',
    '/portal/logout',
    '/portal/suscripcion-vencida',
)

_PATHS_SIN_PRIMER_ACCESO = (
    '/portal/login',
    '/portal/logout',
    '/portal/primer-acceso',
    '/portal/suscripcion-vencida',
)


class SuscripcionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.portal_usuario = None
        portal_usuario_id = request.session.get(PORTAL_SESSION_KEY)
        if portal_usuario_id:
            try:
                request.portal_usuario = PortalUsuario.objects.select_related(
                    'user',
                    'organizacion',
                ).get(pk=portal_usuario_id, user__is_active=True)
            except PortalUsuario.DoesNotExist:
                request.session.pop(PORTAL_SESSION_KEY, None)

        path = request.path
        if path.startswith('/portal/') and not any(path.startswith(p) for p in _PATHS_SIN_SESION):
            if not request.portal_usuario:
                return redirect('/portal/login/')
            if not request.portal_usuario.organizacion.suscripcion_activa:
                return redirect('/portal/suscripcion-vencida/')
            if (
                request.portal_usuario.debe_cambiar_credenciales
                and not any(path.startswith(p) for p in _PATHS_SIN_PRIMER_ACCESO)
            ):
                return redirect('/portal/primer-acceso/')

        return self.get_response(request)
