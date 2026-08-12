"""Tests P0: firma Twilio en webhooks WhatsApp."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client, RequestFactory
from django.test.utils import override_settings
from twilio.request_validator import RequestValidator

from core.twilio_webhook_security import (
    looks_like_meta_whatsapp_payload,
    validate_twilio_request,
)


AUTH_TOKEN = 'test_twilio_auth_token_sec'


def _sign(url: str, params) -> str:
    return RequestValidator(AUTH_TOKEN).compute_signature(url, params)


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=True,
    TWILIO_AUTH_TOKEN=AUTH_TOKEN,
    SECURE_SSL_REDIRECT=False,
)
def test_whatsapp_webhook_sin_firma_403():
    client = Client()
    resp = client.post(
        '/webhook/whatsapp/',
        data={'From': 'whatsapp:+573001112233', 'Body': 'hola', 'To': 'whatsapp:+14155238886'},
        secure=True,
        HTTP_HOST='testserver',
    )
    assert resp.status_code == 403


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=True,
    TWILIO_AUTH_TOKEN=AUTH_TOKEN,
    SECURE_SSL_REDIRECT=False,
)
def test_whatsapp_webhook_firma_invalida_403():
    client = Client()
    resp = client.post(
        '/webhook/whatsapp/',
        data={'From': 'whatsapp:+573001112233', 'Body': 'hola', 'MessageSid': 'SMsec1'},
        secure=True,
        HTTP_HOST='testserver',
        HTTP_X_TWILIO_SIGNATURE='firma-falsa',
    )
    assert resp.status_code == 403


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=True,
    TWILIO_AUTH_TOKEN=AUTH_TOKEN,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views._procesar_twilio_webhook', return_value=None)
@patch('core.views._encolar_twilio_edu_si_async', return_value=False)
@patch('core.bot_comercial_routing.es_destino_bot_comercial', return_value=False)
def test_whatsapp_webhook_firma_valida_ok(mock_route, mock_async, mock_proc):
    client = Client()
    data = {
        'From': 'whatsapp:+573001112233',
        'To': 'whatsapp:+573000000000',
        'Body': 'listo',
        'MessageSid': 'SMsec2',
    }
    url = 'https://testserver/webhook/whatsapp/'
    sig = _sign(url, data)
    resp = client.post(
        '/webhook/whatsapp/',
        data=data,
        secure=True,
        HTTP_HOST='testserver',
        HTTP_X_TWILIO_SIGNATURE=sig,
    )
    assert resp.status_code == 200
    mock_proc.assert_called_once()


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=True,
    TWILIO_AUTH_TOKEN=AUTH_TOKEN,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views._procesar_bot_comercial_twilio_webhook')
def test_bot_comercial_webhook_sin_firma_403(mock_proc):
    client = Client()
    resp = client.post(
        '/webhook/ia-bot-comercial/',
        data={'From': 'whatsapp:+573001112233', 'Body': 'hola'},
        secure=True,
        HTTP_HOST='testserver',
    )
    assert resp.status_code == 403
    mock_proc.assert_not_called()


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=True,
    TWILIO_AUTH_TOKEN=AUTH_TOKEN,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views._procesar_bot_comercial_twilio_webhook')
def test_bot_comercial_webhook_firma_valida_ok(mock_proc):
    client = Client()
    data = {
        'From': 'whatsapp:+573001112233',
        'To': 'whatsapp:+14155238886',
        'Body': 'hola nat',
        'MessageSid': 'SMsec3',
    }
    url = 'https://testserver/webhook/ia-bot-comercial/'
    sig = _sign(url, data)
    resp = client.post(
        '/webhook/ia-bot-comercial/',
        data=data,
        secure=True,
        HTTP_HOST='testserver',
        HTTP_X_TWILIO_SIGNATURE=sig,
    )
    assert resp.status_code == 200
    mock_proc.assert_called_once()


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=True,
    TWILIO_AUTH_TOKEN=AUTH_TOKEN,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views._procesar_meta_webhook')
def test_meta_json_sin_firma_twilio_pasa(mock_meta):
    """Payload Meta (entry) no exige X-Twilio-Signature."""
    client = Client()
    payload = {
        'object': 'whatsapp_business_account',
        'entry': [{'id': '1', 'changes': []}],
    }
    resp = client.post(
        '/webhook/whatsapp/',
        data=payload,
        content_type='application/json',
        secure=True,
        HTTP_HOST='testserver',
    )
    assert resp.status_code == 200
    mock_meta.assert_called_once()


@override_settings(TWILIO_VALIDATE_SIGNATURE=False, TWILIO_AUTH_TOKEN=AUTH_TOKEN)
def test_validate_skip_cuando_flag_off():
    rf = RequestFactory()
    req = rf.post('/webhook/whatsapp/', {'Body': 'x'})
    assert validate_twilio_request(req) is None


def test_looks_like_meta():
    assert looks_like_meta_whatsapp_payload(b'{"entry":[]}')
    assert looks_like_meta_whatsapp_payload(b'{"object":"whatsapp_business_account"}')
    assert not looks_like_meta_whatsapp_payload(b'{"From":"whatsapp:+1"}')
    assert not looks_like_meta_whatsapp_payload(b'From=x')
