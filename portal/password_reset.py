"""Recuperación de contraseña del portal (token Django + email)."""
from __future__ import annotations

import logging

from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods

from portal.models import PortalUsuario

logger = logging.getLogger(__name__)


def _usuario_portal_por_identificador(ident: str):
    """Busca PortalUsuario por username o email (activo)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    ident = (ident or '').strip()
    if not ident:
        return None
    user = User.objects.filter(username__iexact=ident, is_active=True).first()
    if user is None and '@' in ident:
        user = User.objects.filter(email__iexact=ident, is_active=True).first()
    if not user:
        return None
    return PortalUsuario.objects.filter(user=user, user__is_active=True).select_related(
        'user', 'organizacion',
    ).first()


def _enviar_email_reset(request, pu: PortalUsuario) -> bool:
    from core.email_service import get_email_service

    user = pu.user
    email = (user.email or '').strip()
    if not email:
        return False
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse('portal_recuperar_confirmar', kwargs={'uidb64': uid, 'token': token})
    link = request.build_absolute_uri(path)
    org = pu.organizacion.nombre if pu.organizacion_id else 'eki'
    subject = 'Restablecer contraseña — portal eki'
    body = (
        f'Hola,\n\n'
        f'Recibimos una solicitud para restablecer la contraseña del portal eki '
        f'({org}).\n\n'
        f'Abra este enlace (válido por tiempo limitado):\n{link}\n\n'
        f'Si usted no lo pidió, ignore este mensaje.\n\n'
        f'— eki\n'
    )
    try:
        get_email_service().send_email(
            to_emails=[email],
            subject=subject,
            body=body,
        )
        return True
    except Exception as e:
        logger.warning('portal reset email: %s', e)
        return False


@require_http_methods(['GET', 'POST'])
def portal_recuperar(request):
    """Solicitud de reset: siempre mensaje genérico (no filtrar usuarios)."""
    if getattr(request, 'portal_usuario', None):
        return redirect('/portal/')
    mensaje = None
    if request.method == 'POST':
        ident = request.POST.get('identificador') or request.POST.get('email') or ''
        pu = _usuario_portal_por_identificador(ident)
        if pu and (pu.user.email or '').strip():
            _enviar_email_reset(request, pu)
        elif pu and not (pu.user.email or '').strip():
            logger.info('portal reset sin email user_id=%s', pu.user_id)
        mensaje = (
            'Si la cuenta existe y tiene correo registrado, enviamos un enlace '
            'para restablecer la contraseña. Revise su bandeja (y spam).'
        )
    return render(request, 'portal/recuperar.html', {'mensaje': mensaje})


@require_http_methods(['GET', 'POST'])
def portal_recuperar_confirmar(request, uidb64, token):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    error = None
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except Exception:
        user = None

    pu = None
    if user:
        pu = PortalUsuario.objects.filter(user=user).first()
    valido = bool(
        user and pu and default_token_generator.check_token(user, token)
    )

    if request.method == 'POST' and valido:
        p1 = request.POST.get('password1') or ''
        p2 = request.POST.get('password2') or ''
        if len(p1) < 8:
            error = 'La contraseña debe tener al menos 8 caracteres.'
        elif p1 != p2:
            error = 'Las contraseñas no coinciden.'
        else:
            user.set_password(p1)
            user.save(update_fields=['password'])
            pu.password_temporal = ''
            pu.debe_cambiar_credenciales = False
            pu.save(update_fields=['password_temporal', 'debe_cambiar_credenciales'])
            return render(request, 'portal/recuperar_listo.html')

    if not valido:
        error = error or 'El enlace no es válido o ya expiró. Solicite uno nuevo.'
    return render(request, 'portal/recuperar_confirmar.html', {
        'valido': valido,
        'error': error,
    })
