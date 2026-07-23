"""Tests: reintento media, formato 3G, reset portal, métricas."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator

from core.media_entrega import (
    avisos_formato_3g,
    contar_reintentos_en_log,
    metricas_media_cliente,
    reintentar_media_desde_log,
)
from core.models import Cliente, Estudiante, WhatsappLog
from core.twilio_media import mensaje_log_con_media


pytestmark = pytest.mark.django_db
User = get_user_model()


def test_avisos_formato_3g_video_grande():
    avisos = avisos_formato_3g(
        nombre_archivo='clase.mp4',
        size_bytes=40 * 1024 * 1024,
        content_type='video/mp4',
    )
    assert avisos
    assert any('3G' in a or 'MB' in a for a in avisos)


def test_avisos_formato_3g_ok_sin_alerta():
    avisos = avisos_formato_3g(
        nombre_archivo='clip.mp4',
        size_bytes=5 * 1024 * 1024,
        content_type='video/mp4',
    )
    assert avisos == []


@override_settings(MEDIA_REINTENTOS_AUTO=2)
def test_callback_63019_reintenta_media_una_vez():
    from core.views import _registrar_estado_twilio_callback

    url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/demo.mp4'
    log = WhatsappLog.objects.create(
        telefono='573026480629',
        mensaje=mensaje_log_con_media('Material del módulo', url),
        mensaje_id='MM_retry_test_001',
        tipo='SENT',
        estado='SENT',
    )
    with patch('core.utils.enviar_whatsapp_twilio') as send_mock:
        send_mock.return_value = {'success': True, 'mensaje_id': 'MMretry2'}
        with patch('core.media_entrega.preparar_url_media_whatsapp', create=True):
            with patch('core.twilio_media.preparar_url_media_whatsapp', side_effect=lambda u: u):
                _registrar_estado_twilio_callback({
                    'MessageSid': log.mensaje_id,
                    'MessageStatus': 'undelivered',
                    'ErrorCode': '63019',
                    'ErrorMessage': 'Media download failed',
                })
        send_mock.assert_called_once()
        kwargs = send_mock.call_args.kwargs
        assert kwargs.get('media_url')
        assert 'amazonaws.com' not in (kwargs.get('texto') or '')

    log.refresh_from_db()
    assert log.estado == 'UNDELIVERED'
    assert 'RETRY:1' in (log.error_detalle or '')
    assert contar_reintentos_en_log(log) == 1


@override_settings(MEDIA_REINTENTOS_AUTO=2)
def test_reintento_respeta_maximo():
    url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/demo.mp4'
    log = WhatsappLog.objects.create(
        telefono='573026480629',
        mensaje=mensaje_log_con_media('Material', url),
        mensaje_id='MM_retry_max',
        tipo='SENT',
        estado='FAILED',
        error_detalle='63019 | RETRY:2',
    )
    with patch('core.utils.enviar_whatsapp_twilio') as send_mock:
        ok = reintentar_media_desde_log(log, '63019')
        assert ok is False
        send_mock.assert_not_called()


def test_metricas_media_cuenta_fallos():
    cli = Cliente.objects.create(
        nombre='Org Media', nit='900MEDIA-1', contacto_principal='A',
        email='m@x.co', telefono='573001111111', activo=True,
    )
    Estudiante.objects.create(
        cedula='M001', nombre='Est', telefono='573009990001',
        cliente=cli, activo=True, acepto_terminos=True,
    )
    url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/x.mp4'
    WhatsappLog.objects.create(
        telefono='573009990001',
        mensaje=mensaje_log_con_media('ok', url),
        mensaje_id='MM1', tipo='SENT', estado='DELIVERED',
    )
    WhatsappLog.objects.create(
        telefono='573009990001',
        mensaje=mensaje_log_con_media('bad', url),
        mensaje_id='MM2', tipo='SENT', estado='UNDELIVERED',
        error_detalle='63019 fail',
    )
    m = metricas_media_cliente(cli, dias=30)
    assert m['con_media'] == 2
    assert m['fallidos'] == 1
    assert m['entregados'] == 1
    assert m['pct_fallo'] == 50.0


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
def test_portal_recuperar_contraseña_flujo():
    from portal.models import PortalUsuario
    from django.core import mail

    cli = Cliente.objects.create(
        nombre='Org Reset', nit='900RESET-1', contacto_principal='A',
        email='r@x.co', telefono='573002222222', activo=True,
        fecha_fin_suscripcion=date.today() + timedelta(days=60),
    )
    user = User.objects.create_user(
        username='coord_reset', email='coord@org.co', password='OldPass123!',
    )
    PortalUsuario.objects.create(
        user=user, organizacion=cli, rol='admin',
        debe_cambiar_credenciales=False, password_temporal='',
    )
    http = Client()
    r = http.get('/portal/recuperar/')
    assert r.status_code == 200

    with patch('core.email_service.get_email_service') as mock_svc:
        svc = MagicMock()
        svc.send_email.return_value = True
        mock_svc.return_value = svc
        r2 = http.post('/portal/recuperar/', {'identificador': 'coord_reset'})
        assert r2.status_code == 200
        assert b'enlace' in r2.content.lower() or b'correo' in r2.content.lower()
        assert svc.send_email.called

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    r3 = http.post(
        f'/portal/recuperar/{uid}/{token}/',
        {'password1': 'NuevaPass99!', 'password2': 'NuevaPass99!'},
    )
    assert r3.status_code == 200
    user.refresh_from_db()
    assert user.check_password('NuevaPass99!')


@override_settings(SECURE_SSL_REDIRECT=False)
def test_portal_suscripcion_pagina():
    from portal.models import PortalUsuario
    from portal.middleware import PORTAL_SESSION_KEY

    cli = Cliente.objects.create(
        nombre='Org Sub', nit='900SUB-1', contacto_principal='A',
        email='s@x.co', telefono='573003333333', activo=True,
        fecha_fin_suscripcion=date.today() + timedelta(days=10),
        cupos_portal=5,
    )
    user = User.objects.create_user(username='coord_sub', password='Pass12345!')
    pu = PortalUsuario.objects.create(
        user=user, organizacion=cli, rol='admin',
        debe_cambiar_credenciales=False,
    )
    http = Client()
    session = http.session
    session[PORTAL_SESSION_KEY] = pu.id
    session.save()
    r = http.get('/portal/suscripcion/')
    assert r.status_code == 200
    assert b'Suscripci' in r.content or b'Cupos' in r.content or b'cupos' in r.content.lower()
