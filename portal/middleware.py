from django.shortcuts import redirect

from .models import PortalUsuario


PORTAL_SESSION_KEY = 'portal_usuario_id'


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
                ).get(pk=portal_usuario_id, user__is_active=True, user__is_staff=False)
            except PortalUsuario.DoesNotExist:
                request.session.pop(PORTAL_SESSION_KEY, None)

        if (
            request.path.startswith('/portal/')
            and not request.path.startswith('/portal/login')
            and not request.path.startswith('/portal/logout')
            and not request.path.startswith('/portal/suscripcion-vencida')
        ):
            if not request.portal_usuario:
                return redirect('/portal/login/')
            if not request.portal_usuario.organizacion.suscripcion_activa:
                return redirect('/portal/suscripcion-vencida/')

        return self.get_response(request)
