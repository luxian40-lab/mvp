"""Expone request.cuenta_aula / request.studio_estudiante (solo Studio)."""

from core.models import Estudiante

from .cuenta_service import CUENTA_AULA_SESSION_KEY, STUDIO_EST_SESSION_KEY
from .models import CuentaAula


class StudioCuentaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cuenta_aula = None
        request.studio_estudiante = None

        cid = request.session.get(CUENTA_AULA_SESSION_KEY)
        if cid:
            cuenta = CuentaAula.objects.filter(pk=cid, activo=True).select_related(
                'user', 'estudiante', 'estudiante__cliente',
            ).first()
            if cuenta:
                request.cuenta_aula = cuenta
                if cuenta.estudiante_id:
                    request.studio_estudiante = cuenta.estudiante
                    return self.get_response(request)

        sid = request.session.get(STUDIO_EST_SESSION_KEY)
        if sid:
            est = Estudiante.objects.filter(pk=sid, activo=True).select_related('cliente').first()
            if est:
                request.studio_estudiante = est
            else:
                request.session.pop(STUDIO_EST_SESSION_KEY, None)

        return self.get_response(request)
