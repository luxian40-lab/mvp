"""Expone request.cuenta_aula y sincroniza sesión del estudiante."""

from .cuenta_service import CUENTA_AULA_SESSION_KEY
from .models import CuentaAula


class StudioCuentaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cuenta_aula = None
        cid = request.session.get(CUENTA_AULA_SESSION_KEY)
        if cid:
            cuenta = CuentaAula.objects.filter(pk=cid, activo=True).select_related(
                'user', 'estudiante', 'estudiante__cliente',
            ).first()
            if cuenta:
                request.cuenta_aula = cuenta
                if cuenta.estudiante_id:
                    request.aprende_estudiante = cuenta.estudiante
                    request.session['aprende_estudiante_id'] = cuenta.estudiante_id
        return self.get_response(request)
