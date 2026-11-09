"""Claim del outbox de envío. Con el flag apagado no crea filas."""
from datetime import timedelta
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models.outbox_envio import (
    ENVIADO,
    ENVIANDO,
    ERROR,
    INCIERTO,
    PENDIENTE,
    OutboxEnvio,
    cerrar_con_wamid,
    marcar,
    outbox_activo,
    reclamar,
    registrar,
    vencer_enviando,
)
from core.models.canal import EventOutbox


class OutboxEnvioTests(TestCase):
    def test_flag_apagado_por_defecto(self):
        self.assertFalse(outbox_activo())

    def test_flag_apagado_no_crea_fila(self):
        fila = registrar(correlacion='c1', canal='meta', telefono='573000000001')
        self.assertIsNone(fila)
        self.assertEqual(OutboxEnvio.objects.count(), 0)
        self.assertIsNone(reclamar('c1'))

    @override_settings(EKI_OUTBOX_ENVIO=True)
    def test_reentrega_no_duplica_correlacion(self):
        a = registrar(correlacion='c1', canal='meta', telefono='573000000001')
        b = registrar(correlacion='c1', canal='meta', telefono='573000000001')
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(OutboxEnvio.objects.count(), 1)
        self.assertEqual(a.estado, PENDIENTE)

    @override_settings(EKI_OUTBOX_ENVIO=True)
    def test_el_segundo_claim_no_gana(self):
        registrar(correlacion='c1', canal='meta', telefono='573000000001')
        primero = reclamar('c1')
        segundo = reclamar('c1')
        self.assertIsNotNone(primero)
        self.assertIsNone(segundo)
        fila = OutboxEnvio.objects.get(correlacion='c1')
        self.assertEqual(fila.estado, ENVIANDO)
        self.assertEqual(fila.intentos, 1)
        self.assertEqual(fila.claim_token, primero)

    @override_settings(EKI_OUTBOX_ENVIO=True)
    def test_token_ajeno_no_marca(self):
        registrar(correlacion='c1', canal='meta', telefono='573000000001')
        token = reclamar('c1')
        self.assertFalse(marcar('c1', ENVIADO, token=uuid4(), wamid='wamid.x'))
        self.assertTrue(marcar('c1', ENVIADO, token=token, wamid='wamid.ok'))
        fila = OutboxEnvio.objects.get(correlacion='c1')
        self.assertEqual(fila.estado, ENVIADO)
        self.assertEqual(fila.wamid, 'wamid.ok')

    @override_settings(EKI_OUTBOX_ENVIO=True)
    def test_timeout_queda_incierto_y_no_se_reclama(self):
        registrar(correlacion='c1', canal='meta', telefono='573000000001')
        reclamar('c1')
        OutboxEnvio.objects.filter(correlacion='c1').update(
            intento_en=timezone.now() - timedelta(minutes=11),
        )
        self.assertEqual(vencer_enviando(), 1)
        fila = OutboxEnvio.objects.get(correlacion='c1')
        self.assertEqual(fila.estado, INCIERTO)
        self.assertIsNone(reclamar('c1'))

    @override_settings(EKI_OUTBOX_ENVIO=True)
    def test_status_con_wamid_cierra_incierto(self):
        registrar(correlacion='c1', canal='meta', telefono='573000000001')
        reclamar('c1')
        marcar('c1', INCIERTO, token=OutboxEnvio.objects.get(correlacion='c1').claim_token)
        self.assertTrue(cerrar_con_wamid('c1', 'wamid.1'))
        fila = OutboxEnvio.objects.get(correlacion='c1')
        self.assertEqual(fila.estado, ENVIADO)
        self.assertEqual(fila.wamid, 'wamid.1')

    @override_settings(EKI_OUTBOX_ENVIO=True)
    def test_error_no_se_confunde_con_el_lago(self):
        registrar(correlacion='c1', canal='meta', telefono='573000000001')
        token = reclamar('c1')
        self.assertTrue(marcar('c1', ERROR, token=token, codigo_error='130429'))
        self.assertEqual(EventOutbox.objects.count(), 0)
        self.assertEqual(OutboxEnvio.objects.get(correlacion='c1').codigo_error, '130429')
