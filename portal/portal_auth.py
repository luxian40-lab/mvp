"""Autenticación compartida portal B2B y aula docente (/aprende/profesor/)."""

from __future__ import annotations

from portal.models import PortalUsuario

ROLES_PORTAL = frozenset({'admin', 'profesor', 'viewer'})
ROLES_AULA_DOCENTE = frozenset({'admin', 'profesor'})


def portal_usuario_de_user(user) -> PortalUsuario | None:
    """PortalUsuario activo vinculado al User (incluye is_staff si tiene organización)."""
    if not user or not user.is_active:
        return None
    try:
        return PortalUsuario.objects.select_related('user', 'organizacion').get(user=user)
    except PortalUsuario.DoesNotExist:
        return None


def puede_acceder_portal(pu: PortalUsuario | None) -> bool:
    return bool(pu and pu.rol in ROLES_PORTAL)


def puede_acceder_aula_docente(pu: PortalUsuario | None) -> bool:
    return bool(pu and pu.rol in ROLES_AULA_DOCENTE)


def iniciar_sesion_portal(request, portal_usuario: PortalUsuario) -> None:
    from portal.middleware import PORTAL_SESSION_KEY

    request.session[PORTAL_SESSION_KEY] = portal_usuario.pk
    request.portal_usuario = portal_usuario
