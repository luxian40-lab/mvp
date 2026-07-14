"""Sesión del estudiante en el aula web (/aprende/)."""

from core.models import Estudiante

APRENDE_EST_SESSION_KEY = 'aprende_estudiante_id'


class AprendeEstudianteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.aprende_estudiante = None
        est_id = request.session.get(APRENDE_EST_SESSION_KEY)

        # Si entró por Studio (correo), sincronizar estudiante al aula
        # sin pedir login otra vez (misma cookie de sesión).
        if not est_id:
            try:
                from studio.cuenta_service import CUENTA_AULA_SESSION_KEY
                from studio.models import CuentaAula

                cid = request.session.get(CUENTA_AULA_SESSION_KEY)
                if cid:
                    cuenta = (
                        CuentaAula.objects.filter(pk=cid, activo=True)
                        .select_related('estudiante', 'estudiante__cliente')
                        .first()
                    )
                    if cuenta and cuenta.estudiante_id:
                        est_id = cuenta.estudiante_id
                        request.session[APRENDE_EST_SESSION_KEY] = est_id
            except Exception:
                pass

        if est_id:
            try:
                request.aprende_estudiante = Estudiante.objects.select_related('cliente').get(
                    pk=est_id,
                    activo=True,
                )
            except Estudiante.DoesNotExist:
                request.session.pop(APRENDE_EST_SESSION_KEY, None)
        return self.get_response(request)
