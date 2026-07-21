"""Registro e inicio de sesión con correo y contraseña (CuentaAula)."""

from __future__ import annotations

import re

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.db import transaction

from core.models import Estudiante

from .models import CuentaAula

CUENTA_AULA_SESSION_KEY = 'cuenta_aula_id'
STUDIO_EST_SESSION_KEY = 'studio_estudiante_id'


def _normalizar_email(email: str) -> str:
    return email.strip().lower()


def _email_valido(email: str) -> bool:
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))


def _telefono_web_sintetico(cuenta_id: int) -> str:
    """Teléfono único para estudiantes solo-web (no usan WhatsApp)."""
    return f'57WEB{cuenta_id:09d}'


@transaction.atomic
def registrar_cuenta_aula(
    *,
    email: str,
    password: str,
    nombre: str,
) -> tuple[CuentaAula | None, str | None]:
    email = _normalizar_email(email)
    nombre = nombre.strip()

    if not _email_valido(email):
        return None, 'Ingresa un correo electrónico válido.'
    if len(password) < 8:
        return None, 'La contraseña debe tener al menos 8 caracteres.'
    if not nombre:
        return None, 'Indica tu nombre.'
    if User.objects.filter(username=email).exists():
        return None, 'Ya existe una cuenta con ese correo. Inicia sesión.'

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=nombre[:30],
    )
    cuenta = CuentaAula.objects.create(
        user=user,
        nombre_visible=nombre,
    )
    est = Estudiante.objects.create(
        cedula=f'WEB{cuenta.pk:08d}',
        nombre=nombre,
        telefono=_telefono_web_sintetico(cuenta.pk),
        activo=True,
        cliente=None,
    )
    cuenta.estudiante = est
    cuenta.save(update_fields=['estudiante', 'actualizado'])
    return cuenta, None


def autenticar_cuenta_aula(
    *,
    email: str,
    password: str,
) -> tuple[CuentaAula | None, str | None]:
    email = _normalizar_email(email)
    user = authenticate(username=email, password=password)
    if user is None:
        return None, 'Correo o contraseña incorrectos.'
    try:
        cuenta = user.cuenta_aula
    except CuentaAula.DoesNotExist:
        return None, 'Esta cuenta no tiene acceso al aula. Regístrate en Studio.'
    if not cuenta.activo:
        return None, 'Cuenta desactivada. Contacta a soporte.'
    return cuenta, None


def _request_es_staff(request) -> bool:
    """Evita pisar sesión staff si alguien prueba Studio en el mismo host local."""
    u = getattr(request, 'user', None)
    return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))


def iniciar_sesion_cuenta(request, cuenta: CuentaAula) -> Estudiante:
    # Solo sesión de Studio. No escribe aprende_estudiante_id (productos separados).
    if not _request_es_staff(request):
        login(request, cuenta.user)
    request.session[CUENTA_AULA_SESSION_KEY] = cuenta.pk
    request.session.pop(STUDIO_EST_SESSION_KEY, None)
    return cuenta.estudiante


def iniciar_sesion_estudiante_studio(request, estudiante: Estudiante) -> None:
    """Login B2B WhatsApp en Studio (sin CuentaAula)."""
    request.session[STUDIO_EST_SESSION_KEY] = estudiante.pk
    request.session.pop(CUENTA_AULA_SESSION_KEY, None)


def cerrar_sesion_cuenta(request) -> None:
    request.session.pop(CUENTA_AULA_SESSION_KEY, None)
    request.session.pop(STUDIO_EST_SESSION_KEY, None)
    request.session.pop('aprende_estudiante_id', None)


def cerrar_sesion_studio(request) -> None:
    """Sale de Studio sin cerrar sesión de staff/admin."""
    cerrar_sesion_cuenta(request)
    if not _request_es_staff(request):
        from django.contrib.auth import logout

        logout(request)


def cuenta_desde_request(request) -> CuentaAula | None:
    if hasattr(request, 'cuenta_aula') and request.cuenta_aula:
        return request.cuenta_aula
    cid = request.session.get(CUENTA_AULA_SESSION_KEY)
    if not cid:
        return None
    return CuentaAula.objects.filter(pk=cid, activo=True).select_related(
        'user', 'estudiante', 'estudiante__cliente',
    ).first()
