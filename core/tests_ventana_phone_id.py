"""Ventana 24 h filtrada por phone_id de salida (multi-línea)."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Estudiante, WhatsappLog
from core.reenganche_meta import ventana_abierta

TEL = '573001234700'
L3 = '1477762615411333'
L1 = '495439026995771'


@override_settings(WA_VENTANA_HORAS=23)
class VentanaPorPhoneIdTests(TestCase):
    def setUp(self):
        self.estudiante = Estudiante.objects.create(
            cedula='CC700', nombre='Linea', telefono=TEL,
        )

    def _incoming(self, phone_id: str, hace=None):
        log = WhatsappLog.objects.create(
            telefono=TEL,
            tipo='INCOMING',
            canal='meta',
            mensaje='hola',
            phone_id=phone_id,
            estudiante=self.estudiante,
        )
        if hace is not None:
            WhatsappLog.objects.filter(pk=log.pk).update(fecha=timezone.now() - hace)
        return log

    def test_sin_phone_id_sigue_global(self):
        self._incoming(L1)
        self.assertTrue(ventana_abierta(self.estudiante))

    def test_entrante_misma_linea_abre(self):
        self._incoming(L3)
        self.assertTrue(ventana_abierta(self.estudiante, phone_id=L3))

    def test_entrante_otra_linea_no_abre(self):
        self._incoming(L1)
        self.assertFalse(ventana_abierta(self.estudiante, phone_id=L3))

    def test_legacy_sin_phone_id_abre_cualquier_linea(self):
        self._incoming('')
        self.assertTrue(ventana_abierta(self.estudiante, phone_id=L3))

    def test_otra_linea_no_pisa_legacy_si_hay_exacto_viejo(self):
        self._incoming(L3, hace=timedelta(hours=30))
        self._incoming(L1)
        self.assertFalse(ventana_abierta(self.estudiante, phone_id=L3))
