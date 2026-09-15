"""Tests Fase C: panel alertas territoriales + runbook + transiciones."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.alerta_territorial_ops import (
    RUNBOOK_PASOS,
    build_territorio_alertas_snapshot,
    etiqueta_territory_id,
    transicionar_alerta,
)
from core.event_engine import correlacionar_clusters, registrar_senal_territorial
from core.models import AlertaTerritorial


class AlertaTerritorialOpsTests(TestCase):
    def test_etiqueta_medellin(self):
        self.assertIn('Medellin', etiqueta_territory_id('05001'))

    def test_snapshot_municipio_ventana_conteo(self):
        for i in range(3):
            registrar_senal_territorial(
                tipo='agro.plaga.roya',
                territory_id='05001',
                confianza=0.9,
                fuente='test',
                metadata={'i': i},
            )
        correlacionar_clusters(tipo_prefijo='agro.plaga')
        snap = build_territorio_alertas_snapshot(ventana_horas=72, tipo_prefijo='agro.plaga')
        self.assertGreaterEqual(snap['kpis']['senales_ventana'], 3)
        self.assertTrue(any(f['n'] >= 3 and f['territory_id'] == '05001' for f in snap['filas']))
        self.assertGreaterEqual(snap['kpis']['alertas_abiertas'], 1)
        self.assertEqual(len(snap['runbook']), len(RUNBOOK_PASOS))

    def test_transicion_validar_y_cerrar(self):
        for i in range(3):
            registrar_senal_territorial(
                tipo='agro.plaga.broca',
                territory_id='11001',
                confianza=0.85,
                fuente='test',
            )
        correlacionar_clusters(tipo_prefijo='agro.plaga')
        alerta = AlertaTerritorial.objects.filter(
            territory_id='11001',
            estado=AlertaTerritorial.ESTADO_DETECTADA,
        ).first()
        self.assertIsNotNone(alerta)
        User = get_user_model()
        user = User.objects.create_user('ops_ta', password='x')
        transicionar_alerta(
            alerta,
            nuevo_estado=AlertaTerritorial.ESTADO_VALIDADA,
            usuario=user,
            nota='ok tipificado',
        )
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, AlertaTerritorial.ESTADO_VALIDADA)
        self.assertTrue(alerta.metadata.get('historial'))
        transicionar_alerta(
            alerta,
            nuevo_estado=AlertaTerritorial.ESTADO_CERRADA,
            usuario=user,
            nota='falso positivo',
        )
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, AlertaTerritorial.ESTADO_CERRADA)

    def test_transicion_invalida(self):
        a = AlertaTerritorial.objects.create(
            familia='agro.plaga',
            subtipo='cluster.roya',
            territory_id='05001',
            conteo=3,
            score=0.4,
            estado=AlertaTerritorial.ESTADO_DETECTADA,
        )
        with self.assertRaises(ValueError):
            transicionar_alerta(a, nuevo_estado=AlertaTerritorial.ESTADO_COMUNICADA)


@override_settings(SECURE_SSL_REDIRECT=False)
class TerritorioAlertasViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser('staff_ta', 'ta@test.com', 'pass')
        self.client = Client()
        self.client.force_login(self.user)

    def test_panel_requiere_staff_y_renderiza(self):
        anon = Client()
        url = reverse('admin_territorio_alertas')
        resp = anon.get(url)
        self.assertIn(resp.status_code, (302, 403))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Alertas territoriales')
        self.assertContains(resp, 'Runbook')

    def test_post_validar_alerta(self):
        for i in range(3):
            registrar_senal_territorial(
                tipo='empleo.barrera.transporte',
                territory_id='05001',
                confianza=0.8,
                fuente='test',
            )
        correlacionar_clusters(tipo_prefijo='empleo.barrera')
        alerta = AlertaTerritorial.objects.filter(
            estado=AlertaTerritorial.ESTADO_DETECTADA,
            familia='empleo.barrera',
        ).first()
        self.assertIsNotNone(alerta)
        url = reverse('admin_territorio_alertas')
        resp = self.client.post(
            url,
            {'accion': 'validar', 'alerta_id': alerta.pk, 'nota': 'revisado'},
        )
        self.assertEqual(resp.status_code, 302)
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, AlertaTerritorial.ESTADO_VALIDADA)
