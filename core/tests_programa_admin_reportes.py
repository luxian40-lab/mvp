"""Reportes admin trae la franja Programa del portal; NPS no se mueve a Inicio/eki."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Cliente, Estudiante


@override_settings(SECURE_SSL_REDIRECT=False)
class ProgramaEnReportesAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user('prog-staff', password='x', is_staff=True)
        self.client = Client()
        self.client.force_login(self.staff)
        self.org = Cliente.objects.create(
            nombre='Org Programa',
            contacto_principal='C',
            email='prog@example.com',
            telefono='573009991101',
        )
        Estudiante.objects.create(
            cedula='PROG0001',
            nombre='Ana',
            telefono='573001401101',
            cliente=self.org,
            activo=True,
        )

    def test_dashboard_learning_y_pulso_no_nameerror(self):
        # Regresión prod: llamada a _cursos_selector_analitica sin definir → 500.
        for qs in (
            '?tab=learning&section=reportes',
            f'?tab=learning&section=reportes&cliente={self.org.id}',
            '?tab=executive',
        ):
            resp = self.client.get(reverse('dashboard_unificado') + qs)
            self.assertEqual(resp.status_code, 200, qs)

    def test_sin_org_pide_elegir(self):
        resp = self.client.get(reverse('dashboard_unificado') + '?tab=learning&section=reportes')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Elija una', html)
        self.assertNotIn('id="programa-kpi"', html)
        self.assertIsNone(resp.context.get('programa_uso'))

    def test_con_org_muestra_kpi_portal_sin_nps_en_reportes(self):
        url = reverse('dashboard_unificado') + f'?tab=learning&section=reportes&cliente={self.org.id}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context['programa_uso'])
        self.assertEqual(resp.context['programa_uso']['registrados'], 1)
        html = resp.content.decode()
        self.assertIn('id="programa-kpi"', html)
        self.assertIn('Registrados', html)
        # NPS del programa no se pinta aquí; sigue en Pulso.
        self.assertNotIn('prog-kpi__label">NPS', html)
        self.assertIn('NPS en Pulso', html)

    def test_inicio_eki_no_tiene_nps(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        source = (root / 'templates' / 'admin' / 'partials' / 'eki_panel_exec.html').read_text(
            encoding='utf-8'
        )
        self.assertNotIn('NPS', source)
        self.assertNotIn('kpi-nps', source)
