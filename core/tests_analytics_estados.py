"""Contratos de estados WA / EnvioLog usados en analítica."""

from django.test import TestCase

from core.domains.analytics.metricas import (
    q_enviolog_fail,
    q_enviolog_ok,
    q_whatsapp_fallo,
    q_whatsapp_ok,
)
from core.models import Campana, Cliente, EnvioLog, Estudiante, WhatsappLog


class AnalyticsEstadosTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre="Org estados", activo=True)
        self.est = Estudiante.objects.create(
            nombre="Estados",
            cedula="88008800",
            telefono="573008800880",
            cliente=self.cli,
            activo=True,
        )
        self.camp = Campana.objects.create(nombre="C estados", cliente=self.cli)

    def test_enviolog_enviado_es_exito_no_el_literal_exitoso(self):
        EnvioLog.objects.create(campana=self.camp, estudiante=self.est, estado="ENVIADO")
        EnvioLog.objects.create(campana=self.camp, estudiante=self.est, estado="FALLIDO")
        EnvioLog.objects.create(campana=self.camp, estudiante=self.est, estado="ERROR")
        self.assertEqual(EnvioLog.objects.filter(q_enviolog_ok()).count(), 1)
        self.assertEqual(EnvioLog.objects.filter(estado="exitoso").count(), 0)
        self.assertEqual(EnvioLog.objects.filter(q_enviolog_fail()).count(), 2)
        self.assertEqual(EnvioLog.objects.filter(estado="fallido").count(), 0)

    def test_whatsapp_fallo_incluye_twilio_y_error_interno(self):
        WhatsappLog.objects.create(
            telefono="573008800880", tipo="SENT", estado="failed"
        )
        WhatsappLog.objects.create(
            telefono="573008800880", tipo="SENT", estado="undelivered"
        )
        WhatsappLog.objects.create(
            telefono="573008800880", tipo="SENT", estado="ERROR"
        )
        WhatsappLog.objects.create(
            telefono="573008800880", tipo="SENT", estado="delivered"
        )
        self.assertEqual(WhatsappLog.objects.filter(q_whatsapp_fallo()).count(), 3)
        self.assertEqual(WhatsappLog.objects.filter(estado="ERROR").count(), 1)
        self.assertEqual(WhatsappLog.objects.filter(q_whatsapp_ok()).count(), 1)
