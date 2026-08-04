"""Contrato de sesión Aprende: no mezclar estudiante y docente en la misma cookie.

Puertas de estudiante (misma clave de sesión, origen etiquetado):
- whatsapp — *aula* → solo código OTP de 6 dígitos (sin handoff Studio)
- studio   — CuentaAula → /studio/ir-a-aprende/ → handoff firmado (solo Studio)

Docente usa PORTAL_SESSION_KEY (portal B2B). Al abrir una puerta se limpia la otra.
Hosts distintos (studio.* vs aprende.*) ya no comparten cookie; esto cubre el mismo host.
"""

from __future__ import annotations

from portal.middleware import PORTAL_SESSION_KEY

from .middleware import APRENDE_EST_SESSION_KEY

APRENDE_AUTH_VIA_KEY = 'aprende_auth_via'

VIA_WHATSAPP = 'whatsapp'
VIA_STUDIO = 'studio'
VIAS_ESTUDIANTE = frozenset({VIA_WHATSAPP, VIA_STUDIO})


def iniciar_sesion_estudiante(request, estudiante_id: int, *, via: str) -> None:
    via = (via or VIA_WHATSAPP).strip().lower()
    if via not in VIAS_ESTUDIANTE:
        via = VIA_WHATSAPP
    request.session.pop(PORTAL_SESSION_KEY, None)
    request.session[APRENDE_EST_SESSION_KEY] = int(estudiante_id)
    request.session[APRENDE_AUTH_VIA_KEY] = via
    request.session.cycle_key()


def cerrar_sesion_estudiante(request) -> None:
    request.session.pop(APRENDE_EST_SESSION_KEY, None)
    request.session.pop(APRENDE_AUTH_VIA_KEY, None)


def limpiar_estudiante_al_entrar_docente(request) -> None:
    """Al login docente en aprende.*, no dejar sesión de estudiante colgada."""
    cerrar_sesion_estudiante(request)
