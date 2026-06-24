"""Sesión del estudiante en el aula web (/aprende/)."""

from core.models import Estudiante

APRENDE_EST_SESSION_KEY = 'aprende_estudiante_id'


class AprendeEstudianteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.aprende_estudiante = None
        est_id = request.session.get(APRENDE_EST_SESSION_KEY)
        if est_id:
            try:
                request.aprende_estudiante = Estudiante.objects.select_related('cliente').get(
                    pk=est_id,
                    activo=True,
                )
            except Estudiante.DoesNotExist:
                request.session.pop(APRENDE_EST_SESSION_KEY, None)
        return self.get_response(request)
