"""Fallos definitivos del webhook, hash del teléfono y límites de Celery."""
from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.test import RequestFactory
from django.utils import timezone


def test_telefono_hash_es_hmac_no_sha256_pelado():
    from core.locks import telefono_hash

    telefono = '573001112233'
    secreto = str(settings.SECRET_KEY).encode('utf-8')
    esperado = hmac.new(secreto, telefono.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    assert telefono_hash(telefono) == esperado
    assert telefono_hash(telefono) != hashlib.sha256(telefono.encode('utf-8')).hexdigest()[:16]


def test_acks_late_global_en_false_y_prefetch_1():
    assert settings.CELERY_TASK_ACKS_LATE is False
    assert settings.CELERY_TASK_REJECT_ON_WORKER_LOST is False
    assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1


def test_timeouts_de_llm_no_pasan_de_30():
    from core.openai_compat import LLM_HTTP_TIMEOUT_SEG
    from core.utils_ia import GEMINI_HTTP_TIMEOUT_SEG

    assert LLM_HTTP_TIMEOUT_SEG <= 30
    assert GEMINI_HTTP_TIMEOUT_SEG <= 30
    texto = Path('core/openai_compat.py').read_text(encoding='utf-8')
    assert 'timeout=22' in texto
    assert 'timeout=LLM_HTTP_TIMEOUT_SEG' in texto


def test_admin_webhook_fallido_es_solo_lectura_de_staff():
    from django.contrib.admin.sites import site
    from django.contrib.auth.models import AnonymousUser

    from core.webhook_evento import WebhookFallido

    admin_model = site._registry[WebhookFallido]
    request = RequestFactory().get('/admin/core/webhookfallido/')
    request.user = AnonymousUser()
    assert admin_model.has_view_permission(request) is False

    request.user = type('Staff', (), {'is_active': True, 'is_staff': True, 'is_superuser': True})()
    assert admin_model.has_view_permission(request) is True
    assert admin_model.has_add_permission(request) is False
    assert admin_model.has_change_permission(request) is False
    assert admin_model.has_delete_permission(request) is False


@pytest.mark.django_db
def test_purga_de_fallidos_a_los_10_dias():
    from core.webhook_evento import WebhookFallido, purgar_webhooks_fallidos

    tarea = Path('core/tasks.py').read_text(encoding='utf-8')
    assert 'purgar_webhooks_fallidos(10)' in tarea

    viejo = WebhookFallido.objects.create(canal='meta', external_id='wamid.viejo', payload={}, error='x')
    reciente = WebhookFallido.objects.create(canal='meta', external_id='wamid.nuevo', payload={}, error='x')
    WebhookFallido.objects.filter(pk=viejo.pk).update(creado=timezone.now() - timedelta(days=11))
    WebhookFallido.objects.filter(pk=reciente.pk).update(creado=timezone.now() - timedelta(days=9))

    assert purgar_webhooks_fallidos(10) == 1
    assert not WebhookFallido.objects.filter(external_id='wamid.viejo').exists()
    assert WebhookFallido.objects.filter(external_id='wamid.nuevo').exists()


@pytest.mark.django_db
def test_on_failure_guarda_el_fallo_sin_reintentar_soft_timeout():
    pytest.importorskip('celery')
    from celery.exceptions import SoftTimeLimitExceeded

    from core.salida_usuario import marcar_mensaje_salio, reset_mensaje_salio
    from core.tasks import _reintentar_si_lock, procesar_twilio_webhook_async
    from core.webhook_evento import WebhookFallido

    procesar_twilio_webhook_async.on_failure(
        RuntimeError('timeout'),
        'task-1',
        [{'MessageSid': 'SMfallo1', 'From': 'whatsapp:+573001112233', 'Body': 'hola'}],
        {},
        None,
    )
    fila = WebhookFallido.objects.get(external_id='SMfallo1')
    assert fila.canal == 'twilio'
    assert fila.payload['datos']['From'] == 'whatsapp:+573001112233'
    assert fila.payload['tarea'].endswith('procesar_twilio_webhook_async')
    assert '573001112233' not in fila.error

    class _Tarea:
        canal = 'twilio'

        def retry(self, **kwargs):
            raise AssertionError('no debe reintentar')

    reset_mensaje_salio()
    marcar_mensaje_salio()
    with pytest.raises(SoftTimeLimitExceeded):
        _reintentar_si_lock(_Tarea(), SoftTimeLimitExceeded())


@pytest.mark.django_db
def test_comando_reprocesar_encola_la_tarea_guardada():
    pytest.importorskip('celery')
    from unittest.mock import patch

    from django.core.management import call_command

    from core.webhook_evento import WebhookFallido

    fila = WebhookFallido.objects.create(
        canal='twilio',
        external_id='SMreplay',
        payload={
            'tarea': 'core.tasks.procesar_twilio_webhook_async',
            'datos': {'MessageSid': 'SMreplay', 'Body': 'listo'},
            'kwargs': {},
        },
        error='timeout',
    )
    resultado = type('Resultado', (), {'id': 'task-replay'})()
    with patch('core.tasks.procesar_twilio_webhook_async.delay', return_value=resultado) as delay:
        call_command('reprocesar_webhook_fallido', str(fila.pk))
    delay.assert_called_once_with({'MessageSid': 'SMreplay', 'Body': 'listo'})
    assert WebhookFallido.objects.filter(pk=fila.pk).exists()
