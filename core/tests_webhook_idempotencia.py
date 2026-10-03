"""Idempotencia del webhook por wamid / MessageSid."""
from __future__ import annotations

import json
import threading
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.test.utils import override_settings
from django.utils import timezone

from core.webhook_evento import CANAL_META, CANAL_TWILIO, WebhookEventoProcesado, reclamar_evento


def _meta(messages=None, statuses=None, field='messages'):
    value = {}
    if messages is not None:
        value['messages'] = messages
    if statuses is not None:
        value['statuses'] = statuses
    return {
        'object': 'whatsapp_business_account',
        'entry': [{'changes': [{'field': field, 'value': value}]}],
    }


def _post_json(client, payload, **extra):
    return client.post(
        '/webhook/whatsapp/',
        data=json.dumps(payload),
        content_type='application/json',
        secure=True,
        HTTP_HOST='testserver',
        **extra,
    )


@pytest.mark.django_db
@override_settings(
    SANDBOX_PROVEEDOR='twilio',
    SANDBOX_MENU_ENABLED=False,
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
    WHATSAPP_APP_SECRET='',
)
@patch('core.views.entrada._procesar_meta_webhook')
def test_segundo_post_identico_no_procesa(mock_proc):
    client = Client()
    payload = _meta([{'from': '57300111', 'id': 'wamid.uno', 'type': 'text', 'text': {'body': 'hola'}}])
    assert _post_json(client, payload).status_code == 200
    assert _post_json(client, payload).status_code == 200
    mock_proc.assert_called_once()
    assert WebhookEventoProcesado.objects.filter(canal=CANAL_META, external_id='wamid.uno').count() == 1


@pytest.mark.django_db
@override_settings(
    SANDBOX_PROVEEDOR='twilio',
    SANDBOX_MENU_ENABLED=False,
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
    WHATSAPP_APP_SECRET='',
)
@patch('core.views.entrada._procesar_meta_webhook')
def test_dos_mensajes_distintos_se_procesan(mock_proc):
    client = Client()
    payload = _meta([
        {'from': '57300111', 'id': 'wamid.a', 'type': 'text', 'text': {'body': 'uno'}},
        {'from': '57300111', 'id': 'wamid.b', 'type': 'text', 'text': {'body': 'dos'}},
    ])
    assert _post_json(client, payload).status_code == 200
    assert mock_proc.call_count == 2
    ids = []
    for call in mock_proc.call_args_list:
        mensajes = call.args[0]['entry'][0]['changes'][0]['value']['messages']
        assert len(mensajes) == 1
        ids.append(mensajes[0]['id'])
    assert ids == ['wamid.a', 'wamid.b']
    assert WebhookEventoProcesado.objects.filter(canal=CANAL_META).count() == 2


@pytest.mark.django_db
@override_settings(
    SANDBOX_MENU_ENABLED=False,
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
    WHATSAPP_APP_SECRET='',
)
@patch('core.views.entrada._procesar_meta_webhook')
def test_statuses_no_se_deduplican(mock_proc):
    client = Client()
    payload = _meta(statuses=[{'id': 'wamid.out', 'status': 'delivered'}, {'id': 'wamid.out', 'status': 'read'}])
    assert _post_json(client, payload).status_code == 200
    assert _post_json(client, payload).status_code == 200
    assert mock_proc.call_count == 2
    assert WebhookEventoProcesado.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=False,
    SANDBOX_MENU_ENABLED=False,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views.entrada._procesar_twilio_webhook', return_value=None)
@patch('core.bot_comercial_routing.es_destino_bot_comercial', return_value=False)
def test_status_callback_twilio_no_se_deduplica(mock_route, mock_proc):
    client = Client()
    data = {
        'From': 'whatsapp:+573001112233',
        'To': 'whatsapp:+14155238886',
        'MessageSid': 'SMstatus1',
        'MessageStatus': 'delivered',
    }
    assert client.post('/webhook/whatsapp/', data=data, secure=True, HTTP_HOST='testserver').status_code == 200
    assert client.post('/webhook/whatsapp/', data=data, secure=True, HTTP_HOST='testserver').status_code == 200
    assert mock_proc.call_count == 2
    assert WebhookEventoProcesado.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    WHATSAPP_REQUIRE_SIGNATURE=False,
    WHATSAPP_APP_SECRET='',
    SANDBOX_PROVEEDOR='twilio',
    SANDBOX_MENU_ENABLED=False,
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views.entrada._procesar_meta_webhook')
def test_sin_exigir_firma_un_secreto_vacio_no_rechaza(mock_proc):
    client = Client()
    payload = _meta([{'from': '57300111', 'id': 'wamid.abierto', 'type': 'text', 'text': {'body': 'hola'}}])
    resp = _post_json(client, payload)
    assert resp.status_code == 200
    mock_proc.assert_called_once()
    assert WebhookEventoProcesado.objects.filter(external_id='wamid.abierto').exists()


@pytest.mark.django_db
@override_settings(
    WHATSAPP_REQUIRE_SIGNATURE=True,
    WHATSAPP_APP_SECRET='',
    SANDBOX_PROVEEDOR='twilio',
    SANDBOX_MENU_ENABLED=False,
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views.entrada._procesar_meta_webhook')
def test_firma_obligatoria_sin_secreto_responde_403_sin_reclamo(mock_proc):
    client = Client()
    payload = _meta([{'from': '57300111', 'id': 'wamid.cerrado', 'type': 'text', 'text': {'body': 'hola'}}])
    resp = _post_json(client, payload)
    assert resp.status_code == 403
    mock_proc.assert_not_called()
    assert not WebhookEventoProcesado.objects.filter(external_id='wamid.cerrado').exists()


@pytest.mark.django_db
@override_settings(
    WHATSAPP_REQUIRE_SIGNATURE=True,
    WHATSAPP_APP_SECRET='sekreto-test',
    SANDBOX_PROVEEDOR='twilio',
    SANDBOX_MENU_ENABLED=False,
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views.entrada._procesar_meta_webhook')
def test_firma_obligatoria_con_firma_invalida_responde_403_sin_reclamo(mock_proc):
    client = Client()
    payload = _meta([{'from': '57300111', 'id': 'wamid.mala', 'type': 'text', 'text': {'body': 'hola'}}])
    resp = _post_json(client, payload, HTTP_X_HUB_SIGNATURE_256='sha256=00')
    assert resp.status_code == 403
    mock_proc.assert_not_called()
    assert not WebhookEventoProcesado.objects.filter(external_id='wamid.mala').exists()


@pytest.mark.django_db
@override_settings(
    WHATSAPP_APP_SECRET='sekreto-test',
    TWILIO_VALIDATE_SIGNATURE=True,
    TWILIO_AUTH_TOKEN='test_twilio_auth_token_sec',
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views.entrada._procesar_meta_webhook')
def test_firma_invalida_no_crea_registro(mock_proc):
    client = Client()
    payload = _meta([{'from': '57300111', 'id': 'wamid.bad', 'type': 'text', 'text': {'body': 'hola'}}])
    resp = _post_json(client, payload, HTTP_X_HUB_SIGNATURE_256='sha256=00')
    assert resp.status_code == 403
    mock_proc.assert_not_called()
    assert WebhookEventoProcesado.objects.count() == 0

    resp_tw = client.post(
        '/webhook/whatsapp/',
        data={'From': 'whatsapp:+573001112233', 'Body': 'hola', 'MessageSid': 'SMbad'},
        secure=True,
        HTTP_HOST='testserver',
        HTTP_X_TWILIO_SIGNATURE='firma-falsa',
    )
    assert resp_tw.status_code == 403
    assert WebhookEventoProcesado.objects.filter(canal=CANAL_TWILIO).count() == 0


@pytest.mark.django_db
@override_settings(
    TWILIO_VALIDATE_SIGNATURE=False,
    SANDBOX_MENU_ENABLED=False,
    SECURE_SSL_REDIRECT=False,
)
@patch('core.views.entrada._procesar_twilio_webhook', return_value=None)
@patch('core.views.entrada._encolar_twilio_edu_si_async')
@patch('core.bot_comercial_routing.es_destino_bot_comercial', return_value=False)
def test_fallo_al_encolar_borra_reclamo_y_el_reintento_procesa(mock_route, mock_encolar, mock_proc):
    client = Client()
    data = {
        'From': 'whatsapp:+573001112233',
        'To': 'whatsapp:+14155238886',
        'Body': 'listo',
        'MessageSid': 'SMretry1',
    }
    mock_encolar.side_effect = ConnectionError('redis')
    resp = client.post('/webhook/whatsapp/', data=data, secure=True, HTTP_HOST='testserver')
    assert resp.status_code == 500
    mock_proc.assert_not_called()
    assert not WebhookEventoProcesado.objects.filter(external_id='SMretry1').exists()

    mock_encolar.side_effect = None
    mock_encolar.return_value = False
    resp2 = client.post('/webhook/whatsapp/', data=data, secure=True, HTTP_HOST='testserver')
    assert resp2.status_code == 200
    mock_proc.assert_called_once()
    assert WebhookEventoProcesado.objects.filter(canal=CANAL_TWILIO, external_id='SMretry1').exists()


@pytest.mark.django_db
def test_limpiar_logs_borra_eventos_de_mas_de_10_dias():
    from pathlib import Path

    from core.webhook_evento import purgar_eventos_procesados

    tarea = Path('core/tasks.py').read_text(encoding='utf-8')
    assert 'purgar_eventos_procesados(10)' in tarea

    viejo = WebhookEventoProcesado.objects.create(canal=CANAL_META, external_id='wamid.viejo')
    reciente = WebhookEventoProcesado.objects.create(canal=CANAL_META, external_id='wamid.nuevo')
    WebhookEventoProcesado.objects.filter(pk=viejo.pk).update(creado=timezone.now() - timedelta(days=11))
    WebhookEventoProcesado.objects.filter(pk=reciente.pk).update(creado=timezone.now() - timedelta(days=9))

    purgar_eventos_procesados(10)

    assert not WebhookEventoProcesado.objects.filter(external_id='wamid.viejo').exists()
    assert WebhookEventoProcesado.objects.filter(external_id='wamid.nuevo').exists()


def _meta_sandbox(messages):
    payload = _meta(messages)
    payload['entry'][0]['changes'][0]['value']['metadata'] = {
        'display_phone_number': '573009998888',
        'phone_number_id': '111222333',
    }
    return payload


@pytest.mark.django_db
@override_settings(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    SANDBOX_CELERY_ASYNC=True,
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    BOT_COMERCIAL_SANDBOX_NUMBER='573009998888',
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
    WHATSAPP_APP_SECRET='',
)
@patch('core.views.entrada._aplicar_sandbox_menu', return_value=None)
@patch('core.views.entrada._encolar_sandbox_si_async')
def test_segundo_mensaje_falla_al_encolar_y_el_reintento_solo_lo_procesa(mock_encolar, _menu):
    client = Client()
    payload = _meta_sandbox([
        {'from': '57300111', 'id': 'wamid.a', 'type': 'text', 'text': {'body': 'uno'}},
        {'from': '57300111', 'id': 'wamid.b', 'type': 'text', 'text': {'body': 'dos'}},
    ])
    mock_encolar.side_effect = [True, ConnectionError('redis')]
    resp = _post_json(client, payload)
    assert resp.status_code == 500
    assert WebhookEventoProcesado.objects.filter(canal=CANAL_META, external_id='wamid.a').exists()
    assert not WebhookEventoProcesado.objects.filter(external_id='wamid.b').exists()
    assert mock_encolar.call_count == 2

    mock_encolar.side_effect = None
    mock_encolar.return_value = True
    resp2 = _post_json(client, payload)
    assert resp2.status_code == 200
    assert mock_encolar.call_count == 3
    assert mock_encolar.call_args.args[0]['MessageSid'] == 'wamid.b'
    assert WebhookEventoProcesado.objects.filter(canal=CANAL_META, external_id='wamid.b').exists()


class ReclamarEventoCarreraTests(TransactionTestCase):
    def test_dos_hilos_un_solo_true(self):
        if connection.vendor != 'postgresql':
            self.skipTest('carrera requiere Postgres')
        barrera = threading.Barrier(2)
        resultados = []
        errores = []

        def worker():
            connections.close_all()
            try:
                barrera.wait(timeout=5)
                resultados.append(reclamar_evento(CANAL_META, 'wamid.race'))
            except Exception as exc:
                errores.append(exc)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=worker) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=10)
        self.assertFalse(errores)
        self.assertEqual(sorted(resultados), [False, True])
        self.assertEqual(
            WebhookEventoProcesado.objects.filter(external_id='wamid.race').count(),
            1,
        )
