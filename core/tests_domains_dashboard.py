"""Tests Parte 0 (dominios) y Parte 1 (dashboard canónico)."""

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from core.domains.analytics.metricas import calcular_semaforo
from core.domains.dashboard import (
    API_TIPO_ALIASES,
    LEGACY_DASHBOARD_REDIRECTS,
    resolve_dashboard_tab,
    resolve_learning_section,
)
from core.domains.learning.checkpoints import debe_activar_checkpoint_reto_ia
from core.domains.registry import DOMAIN_REGISTRY, get_domain


class DomainRegistryTests(SimpleTestCase):
    def test_registry_incluye_dominios_clave(self):
        self.assertIn('learning', DOMAIN_REGISTRY)
        self.assertIn('analytics', DOMAIN_REGISTRY)
        self.assertIn('agents_commercial', DOMAIN_REGISTRY)

    def test_get_domain_desconocido(self):
        self.assertIsNone(get_domain('inventado'))

    def test_facade_checkpoints_alineada_con_manual(self):
        self.assertFalse(debe_activar_checkpoint_reto_ia(1, 5, True))
        self.assertTrue(debe_activar_checkpoint_reto_ia(3, 5, True))

    def test_facade_metricas_semaforo(self):
        self.assertEqual(calcular_semaforo(85, 80), 'verde')


class DashboardTabResolverTests(SimpleTestCase):
    def test_aliases_legacy_a_canonicos(self):
        self.assertEqual(resolve_dashboard_tab('resumen'), 'executive')
        self.assertEqual(resolve_dashboard_tab('reportes'), 'learning')
        self.assertEqual(resolve_dashboard_tab('auditoria'), 'ai_ops')
        self.assertEqual(resolve_dashboard_tab('metricas_nati'), 'commercial')

    def test_learning_section_desde_tab_legacy(self):
        self.assertEqual(resolve_learning_section('reportes', None), 'reportes')
        self.assertEqual(resolve_learning_section('metricas_empresa', None), 'metricas_empresa')

    def test_api_tipo_aliases(self):
        self.assertEqual(API_TIPO_ALIASES['learning'], 'metricas_empresa')
        self.assertEqual(API_TIPO_ALIASES['commercial'], 'metricas_nati')


class LegacyDashboardRedirectTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username='staff-dash',
            password='test-pass-123',
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_redirect_metrics_a_ai_ops(self):
        resp = self.client.get(reverse('dashboard_metrics'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('tab=ai_ops', resp['Location'])

    def test_redirect_reportes_a_learning(self):
        resp = self.client.get(reverse('dashboard_reportes_avanzados'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('tab=learning', resp['Location'])
        self.assertIn('section=reportes', resp['Location'])

    def test_redirect_gerencial_a_executive(self):
        resp = self.client.get(reverse('dashboard_gerencial'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('tab=executive', resp['Location'])

    def test_legacy_map_completo(self):
        self.assertIn('dashboard_antiguo', LEGACY_DASHBOARD_REDIRECTS)
        self.assertIn('dashboard_analytics', LEGACY_DASHBOARD_REDIRECTS)
