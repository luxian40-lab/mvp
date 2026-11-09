"""Orden de llegada de la bandeja y su enganche al webhook."""
from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from core.conversacion.bandeja_entrada import (
    FALLIDO,
    PENDIENTE,
    PROCESADO,
    PROCESANDO,
    EntradaBandeja,
    anotar_fallo,
    anotar_llegada,
    anotar_tras_firma,
    bandeja_activa,
    cerrar_procesado,
    cerrar_turno,
    reclamar_cabeza,
    tomar_turno,
)
from core.webhook_evento import CANAL_META


class BandejaEntradaTests(TestCase):
    def test_flag_apagado_por_defecto(self):
        self.assertFalse(bandeja_activa())

    @override_settings(EKI_BANDEJA_ENTRADA=True)
    def test_flag_se_lee_de_settings(self):
        self.assertTrue(bandeja_activa())

    def test_firma_invalida_no_crea_fila(self):
        fila = anotar_tras_firma(
            firma_valida=False,
            canal='meta',
            external_id='wamid.a',
            telefono='573000000001',
        )
        self.assertIsNone(fila)
        self.assertEqual(EntradaBandeja.objects.count(), 0)

    def test_a_luego_b_se_reclaman_en_ese_orden(self):
        telefono = '573000000001'
        a, nueva_a = anotar_llegada('meta', 'wamid.a', telefono, {'n': 1})
        b, nueva_b = anotar_llegada('meta', 'wamid.b', telefono, {'n': 2})
        self.assertTrue(nueva_a)
        self.assertTrue(nueva_b)
        self.assertEqual((a.secuencia, b.secuencia), (1, 2))

        cabeza = reclamar_cabeza(telefono)
        self.assertEqual(cabeza.external_id, 'wamid.a')
        self.assertEqual(cabeza.estado, PROCESANDO)
        b.refresh_from_db()
        self.assertEqual(b.estado, PENDIENTE)

        otra = reclamar_cabeza(telefono)
        self.assertEqual(otra.external_id, 'wamid.a')
        b.refresh_from_db()
        self.assertEqual(b.estado, PENDIENTE)

        cerrar_procesado(cabeza)
        siguiente = reclamar_cabeza(telefono)
        self.assertEqual(siguiente.external_id, 'wamid.b')
        self.assertEqual(siguiente.estado, PROCESANDO)

    def test_reentrega_no_crea_otra_fila(self):
        fila, _nueva = anotar_llegada('meta', 'wamid.a', '573000000001', {'n': 1})
        otra, nueva = anotar_llegada('meta', 'wamid.a', '573000000001', {'n': 9})
        self.assertFalse(nueva)
        self.assertEqual(otra.pk, fila.pk)
        self.assertEqual(EntradaBandeja.objects.count(), 1)
        self.assertEqual(otra.payload, {'n': 1})

    def test_cinco_fallos_de_la_cabeza_dejan_pasar_al_siguiente(self):
        telefono = '573000000088'
        anotar_llegada('meta', 'wamid.a', telefono)
        anotar_llegada('meta', 'wamid.b', telefono)
        for _ in range(4):
            cabeza = reclamar_cabeza(telefono)
            self.assertEqual(cabeza.external_id, 'wamid.a')
            self.assertEqual(anotar_fallo(cabeza, 'no'), PENDIENTE)
        cabeza = reclamar_cabeza(telefono)
        self.assertEqual(anotar_fallo(cabeza, 'no'), FALLIDO)
        siguiente = reclamar_cabeza(telefono)
        self.assertEqual(siguiente.external_id, 'wamid.b')

    def test_el_fallo_de_una_posterior_no_cambia_su_estado(self):
        telefono = '573000000088'
        anotar_llegada('meta', 'wamid.a', telefono)
        b, _nueva = anotar_llegada('meta', 'wamid.b', telefono)
        reclamar_cabeza(telefono)
        self.assertEqual(anotar_fallo(b, 'no'), PENDIENTE)
        b.refresh_from_db()
        self.assertEqual(b.estado, PENDIENTE)
        self.assertEqual(b.intentos, 0)

    def test_otro_telefono_no_espera(self):
        anotar_llegada('meta', 'wamid.a', '573000000001')
        anotar_llegada('meta', 'wamid.b', '573000000002')
        self.assertEqual(reclamar_cabeza('573000000002').external_id, 'wamid.b')
        self.assertEqual(reclamar_cabeza('573000000001').external_id, 'wamid.a')

    @override_settings(EKI_BANDEJA_ENTRADA=True)
    def test_b_no_toma_turno_mientras_a_sigue_abierta(self):
        telefono = '573000000088'
        anotar_llegada(CANAL_META, 'wamid.a', telefono)
        anotar_llegada(CANAL_META, 'wamid.b', telefono)
        self.assertFalse(tomar_turno(CANAL_META, 'wamid.b', telefono))
        b = EntradaBandeja.objects.get(external_id='wamid.b')
        self.assertEqual(b.estado, PENDIENTE)
        self.assertTrue(tomar_turno(CANAL_META, 'wamid.a', telefono))
        a = EntradaBandeja.objects.get(external_id='wamid.a')
        self.assertEqual(a.estado, PROCESANDO)
        cerrar_turno(CANAL_META, 'wamid.a')
        self.assertTrue(tomar_turno(CANAL_META, 'wamid.b', telefono))
        b.refresh_from_db()
        self.assertEqual(b.estado, PROCESANDO)


def _meta(messages):
    return {
        'object': 'whatsapp_business_account',
        'entry': [{'changes': [{'field': 'messages', 'value': {'messages': messages}}]}],
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


_WEBHOOK = dict(
    SANDBOX_PROVEEDOR='twilio',
    SANDBOX_MENU_ENABLED=False,
    TWILIO_VALIDATE_SIGNATURE=False,
    SECURE_SSL_REDIRECT=False,
    WHATSAPP_APP_SECRET='sekreto-test',
    WHATSAPP_REQUIRE_SIGNATURE=True,
)


@override_settings(**_WEBHOOK)
class BandejaWebhookTests(TestCase):
    @override_settings(EKI_BANDEJA_ENTRADA=False)
    @patch('core.views.entrada._procesar_meta_webhook')
    def test_flag_apagado_no_crea_fila(self, mock_proc):
        client = Client()
        payload = _meta([{'from': '57300111', 'id': 'wamid.off', 'type': 'text', 'text': {'body': 'hola'}}])
        self.assertEqual(_post_json(client, payload, HTTP_X_HUB_SIGNATURE_256='sha256=00').status_code, 403)
        payload_ok = _meta([{'from': '57300111', 'id': 'wamid.off', 'type': 'text', 'text': {'body': 'hola'}}])
        with override_settings(WHATSAPP_REQUIRE_SIGNATURE=False, WHATSAPP_APP_SECRET=''):
            self.assertEqual(_post_json(client, payload_ok).status_code, 200)
        self.assertEqual(EntradaBandeja.objects.count(), 0)
        mock_proc.assert_called_once()

    @patch('core.views.entrada._procesar_meta_webhook')
    def test_firma_invalida_no_crea_fila_aunque_el_flag_este_prendido(self, mock_proc):
        with override_settings(EKI_BANDEJA_ENTRADA=True):
            client = Client()
            payload = _meta([{'from': '57300111', 'id': 'wamid.mala', 'type': 'text', 'text': {'body': 'hola'}}])
            resp = _post_json(client, payload, HTTP_X_HUB_SIGNATURE_256='sha256=00')
        self.assertEqual(resp.status_code, 403)
        mock_proc.assert_not_called()
        self.assertEqual(EntradaBandeja.objects.count(), 0)

    @override_settings(EKI_BANDEJA_ENTRADA=True, WHATSAPP_REQUIRE_SIGNATURE=False, WHATSAPP_APP_SECRET='')
    @patch('core.views.entrada._procesar_meta_webhook')
    def test_el_post_anota_y_cierra_en_orden(self, mock_proc):
        client = Client()
        payload = _meta([
            {'from': '57300111', 'id': 'wamid.a', 'type': 'text', 'text': {'body': 'uno'}},
            {'from': '57300111', 'id': 'wamid.b', 'type': 'text', 'text': {'body': 'dos'}},
        ])
        self.assertEqual(_post_json(client, payload).status_code, 200)
        self.assertEqual(mock_proc.call_count, 2)
        estados = list(
            EntradaBandeja.objects.order_by('secuencia').values_list('external_id', 'estado')
        )
        self.assertEqual(estados, [('wamid.a', PROCESADO), ('wamid.b', PROCESADO)])


@contextmanager
def _candado(*_args, **_kwargs):
    yield


@override_settings(EKI_BANDEJA_ENTRADA=True)
class BandejaTareaTests(TestCase):
    @patch('core.tasks._frenar_flood', return_value=False)
    @patch('core.tasks._cortar_reentregas', return_value=False)
    @patch('core.locks.telefono_lock', _candado)
    @patch('core.views._aplicar_sandbox_menu')
    def test_la_tarea_de_b_reintenta_sin_aplicar(self, menu, _reentrega, _flood):
        from celery.exceptions import Retry

        from core.tasks import procesar_sandbox_meta_async

        telefono = '573000000088'
        anotar_llegada(CANAL_META, 'wamid.a', telefono)
        anotar_llegada(CANAL_META, 'wamid.b', telefono)
        inbound_b = {'From': 'whatsapp:+573000000088', 'MessageSid': 'wamid.b', 'Body': 'dos'}
        with self.assertRaises(Retry):
            procesar_sandbox_meta_async.apply(args=[inbound_b])
        menu.assert_not_called()
        b = EntradaBandeja.objects.get(external_id='wamid.b')
        self.assertEqual(b.estado, PENDIENTE)

        inbound_a = {'From': 'whatsapp:+573000000088', 'MessageSid': 'wamid.a', 'Body': 'uno'}
        procesar_sandbox_meta_async.apply(args=[inbound_a])
        menu.assert_called_once()
        a = EntradaBandeja.objects.get(external_id='wamid.a')
        self.assertEqual(a.estado, PROCESADO)
        self.assertTrue(tomar_turno(CANAL_META, 'wamid.b', telefono))
