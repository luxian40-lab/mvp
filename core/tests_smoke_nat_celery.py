"""Smoke/regresión Nat async — importable por pytest."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test.utils import override_settings

from core.views import _encolar_bot_comercial_si_async, _encolar_twilio_edu_si_async


@pytest.mark.django_db
def test_celery_registra_tarea_nat():
    import core.tasks  # noqa: F401
    from mvp_project.celery import app

    assert 'core.tasks.procesar_bot_comercial_webhook_async' in app.tasks


@pytest.mark.django_db
@override_settings(NAT_WEBHOOK_CELERY_ASYNC=True, WEBHOOK_CELERY_ASYNC=True)
@patch('core.tasks.procesar_bot_comercial_webhook_async.delay')
@patch('core.tasks.procesar_twilio_webhook_async.delay')
def test_nat_y_edu_encolan_sin_mezclar(mock_edu, mock_nat):
    nat_post = {'MessageSid': 'SMnat1', 'Body': 'hola nat'}
    edu_post = {'MessageSid': 'SMedu1', 'Body': 'listo'}

    assert _encolar_bot_comercial_si_async(nat_post) is True
    assert _encolar_twilio_edu_si_async(edu_post) is True
    mock_nat.assert_called_once()
    mock_edu.assert_called_once()


@pytest.mark.django_db
@override_settings(NAT_WEBHOOK_CELERY_ASYNC=True)
@patch('core.tasks.procesar_bot_comercial_webhook_async.delay', side_effect=OSError('redis down'))
def test_nat_encolar_falla_abre_fallback_sync(_mock_delay):
    post = {'MessageSid': 'SMnat2', 'Body': 'hola'}
    assert _encolar_bot_comercial_si_async(post) is False


@pytest.mark.django_db
def test_status_callback_no_encola_nat():
    from core.views import _es_status_callback_twilio

    assert _es_status_callback_twilio({'MessageStatus': 'delivered', 'MessageSid': 'x'})

