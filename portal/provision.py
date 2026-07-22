"""Provisión de usuarios portal: solo eki admin, sin staff, respeta cupos."""

from __future__ import annotations

import secrets
import string

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PortalUsuario


def generar_password_temporal(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def cupos_usados(cliente) -> int:
    return PortalUsuario.objects.filter(organizacion=cliente).count()


def cupos_totales(cliente) -> int:
    return int(getattr(cliente, 'cupos_portal', 0) or 0)


def cupos_restantes(cliente) -> int:
    return max(0, cupos_totales(cliente) - cupos_usados(cliente))


def puede_crear_usuario_portal(cliente) -> bool:
    return cupos_restantes(cliente) > 0


@transaction.atomic
def provisionar_usuario_portal(
    *,
    cliente,
    username: str,
    password: str | None = None,
    first_name: str = '',
    last_name: str = '',
    email: str = '',
    rol: str = 'viewer',
    is_active: bool = True,
    forzar_cambio: bool = True,
) -> tuple:
    """
    Crea User + PortalUsuario sin acceso Django admin.
    Returns (user, portal_usuario, password_plano).
    """
    if not puede_crear_usuario_portal(cliente):
        raise ValidationError(
            f'No hay cupos disponibles ({cupos_usados(cliente)}/{cupos_totales(cliente)}). '
            'Aumenta «Cupos de usuarios portal» en el cliente.'
        )

    User = get_user_model()
    username = (username or '').strip()
    if not username:
        raise ValidationError('El usuario es obligatorio.')
    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError('Ya existe un usuario con ese nombre.')

    password_plano = (password or '').strip() or generar_password_temporal()
    if rol not in dict(PortalUsuario.ROL_CHOICES):
        rol = 'viewer'

    user = User(
        username=username,
        first_name=(first_name or '').strip(),
        last_name=(last_name or '').strip(),
        email=(email or '').strip(),
        is_staff=False,
        is_superuser=False,
        is_active=bool(is_active),
    )
    user.set_password(password_plano)
    user.save()

    pu = PortalUsuario.objects.create(
        user=user,
        organizacion=cliente,
        rol=rol,
        debe_cambiar_credenciales=forzar_cambio,
        password_temporal=password_plano if forzar_cambio else '',
    )
    return user, pu, password_plano


@transaction.atomic
def resetear_password_temporal(portal_usuario: PortalUsuario, password: str | None = None) -> str:
    """Nueva temporal visible en admin; fuerza primer acceso de nuevo."""
    password_plano = (password or '').strip() or generar_password_temporal()
    user = portal_usuario.user
    user.is_staff = False
    user.is_superuser = False
    user.set_password(password_plano)
    user.save(update_fields=['password', 'is_staff', 'is_superuser'])
    portal_usuario.password_temporal = password_plano
    portal_usuario.debe_cambiar_credenciales = True
    portal_usuario.save(update_fields=['password_temporal', 'debe_cambiar_credenciales'])
    return password_plano


@transaction.atomic
def completar_primer_acceso(portal_usuario: PortalUsuario, *, first_name: str, last_name: str, password: str) -> None:
    user = portal_usuario.user
    user.first_name = (first_name or '').strip()
    user.last_name = (last_name or '').strip()
    user.is_staff = False
    user.is_superuser = False
    user.set_password(password)
    user.save()
    portal_usuario.debe_cambiar_credenciales = False
    portal_usuario.password_temporal = ''
    portal_usuario.save(update_fields=['debe_cambiar_credenciales', 'password_temporal'])


@transaction.atomic
def establecer_password_admin(
    portal_usuario: PortalUsuario,
    password: str,
    *,
    forzar_primer_acceso: bool = False,
) -> str:
    """
    Staff define la contraseña desde el admin.
    Por defecto queda definitiva (sin forzar /portal/primer-acceso/).
    """
    password_plano = (password or '').strip()
    if not password_plano:
        raise ValidationError('La contraseña no puede estar vacía.')
    if len(password_plano) < 8:
        raise ValidationError('La contraseña debe tener al menos 8 caracteres.')

    user = portal_usuario.user
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_password(password_plano)
    user.save(update_fields=['password', 'is_active', 'is_staff', 'is_superuser'])

    if forzar_primer_acceso:
        portal_usuario.password_temporal = password_plano
        portal_usuario.debe_cambiar_credenciales = True
        portal_usuario.save(update_fields=['password_temporal', 'debe_cambiar_credenciales'])
    else:
        portal_usuario.password_temporal = password_plano  # visible para el staff al entregar
        portal_usuario.debe_cambiar_credenciales = False
        portal_usuario.save(update_fields=['password_temporal', 'debe_cambiar_credenciales'])
    return password_plano


def destino_post_autenticacion(portal_usuario: PortalUsuario) -> str:
    """Profesores van al aula; eki_ops al hub ops; el resto al home B2B."""
    if portal_usuario.rol == 'profesor':
        return '/aprende/profesor/'
    if portal_usuario.rol == 'eki_ops':
        return '/portal/ops/'
    from .capabilities import portal_home_url

    return portal_home_url(portal_usuario.organizacion)
