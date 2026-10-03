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


def test_external_id_de_las_tres_tareas():
    """Twilio y Nat usan MessageSid. Meta copia el wamid (message.id) a MessageSid."""
    from core.sandbox_canal import inbound_desde_meta_message
    from core.webhook_evento import external_id_de_payload

    twilio = {'MessageSid': 'SMtwilio', 'From': 'whatsapp:+573001112233', 'Body': 'listo'}
    assert external_id_de_payload(twilio) == 'SMtwilio'

    inbound = inbound_desde_meta_message(
        {'id': 'wamid.META1', 'from': '573001112233', 'type': 'text', 'text': {'body': 'hola'}},
        {'metadata': {'display_phone_number': '15550001111', 'phone_number_id': '1'}},
    )
    assert inbound['MessageSid'] == 'wamid.META1'
    assert external_id_de_payload(inbound) == 'wamid.META1'
    assert external_id_de_payload({'id': 'wamid.SOLO'}) == 'wamid.SOLO'


class _RedisFalso:
    def __init__(self):
        self.valores = {}
        self.ttls = {}

    def incr(self, clave):
        self.valores[clave] = int(self.valores.get(clave, 0)) + 1
        return self.valores[clave]

    def ttl(self, clave):
        return self.ttls.get(clave, -1)

    def expire(self, clave, segundos):
        self.ttls[clave] = segundos
        return True

    def close(self):
        return None


@pytest.mark.django_db
@pytest.mark.parametrize(
    'nombre,canal,sid,kwargs,cuerpo',
    [
        ('procesar_twilio_webhook_async', 'twilio', 'SMre1', {}, 'core.views._procesar_twilio_webhook'),
        (
            'procesar_bot_comercial_webhook_async',
            'twilio',
            'SMnat1',
            {'forzar_canal': True},
            'core.bot_comercial.webhook._procesar_bot_comercial_twilio_webhook',
        ),
        ('procesar_sandbox_meta_async', 'meta', 'wamid.RE1', {}, 'core.views._aplicar_sandbox_menu'),
    ],
)
def test_la_tercera_entrega_no_ejecuta_y_guarda_el_wamid(nombre, canal, sid, kwargs, cuerpo):
    pytest.importorskip('celery')
    from contextlib import contextmanager
    from unittest.mock import patch

    from core import tasks as tasks_mod
    from core.locks import ENTREGA_TTL_SEG
    from core.webhook_evento import WebhookFallido

    @contextmanager
    def _abierto(*args, **kw):
        yield

    falso = _RedisFalso()
    datos = {'MessageSid': sid, 'From': 'whatsapp:+573009998877', 'Body': 'hola'}
    if canal == 'meta':
        datos['id'] = sid
    tarea = getattr(tasks_mod, nombre)
    with patch('core.locks._cliente_redis', return_value=falso), \
            patch('core.locks.telefono_lock', _abierto), \
            patch(cuerpo) as proc:
        for _ in range(2):
            tarea.apply(args=[datos], kwargs=kwargs, throw=True)
        assert proc.call_count == 2
        tarea.apply(args=[datos], kwargs=kwargs, throw=True)
        assert proc.call_count == 2

    fila = WebhookFallido.objects.get(external_id=sid)
    assert fila.canal == canal
    assert fila.error == 'reentregas_excedidas'
    assert falso.ttls[f'eki:wa:entrega:{canal}:{sid}'] == ENTREGA_TTL_SEG
    if nombre == 'procesar_bot_comercial_webhook_async':
        assert fila.payload['kwargs']['forzar_canal'] is True


@pytest.mark.django_db
def test_on_failure_de_meta_guarda_el_wamid_aunque_solo_venga_id():
    pytest.importorskip('celery')
    from core.tasks import procesar_sandbox_meta_async
    from core.webhook_evento import WebhookFallido

    procesar_sandbox_meta_async.on_failure(
        RuntimeError('graph'),
        'task-meta',
        [{'id': 'wamid.SOLOID', 'From': 'whatsapp:+573001112233', 'Body': 'foto'}],
        {},
        None,
    )
    fila = WebhookFallido.objects.get(external_id='wamid.SOLOID')
    assert fila.canal == 'meta'
