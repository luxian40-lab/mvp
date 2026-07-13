"""Tests panel retención admin (ahora tab del Dashboard Eki)."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante

_STATIC_TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


class RetencionAdminViewTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Admin Ret',
            contacto_principal='A',
            email='reta@test.com',
            telefono='573003333001',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso AR', cliente=self.cliente, activo=True)
        est = Estudiante.objects.create(
            cedula='ar1', nombre='E1', telefono='573003333002', cliente=self.cliente,
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=self.curso)
        self.admin = User.objects.create_superuser('adminret', 'a@t.com', 'pass1234')
        self.http = Client()
        self.http.force_login(self.admin)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_retencion_url_redirige_a_dashboard_tab(self):
        r = self.http.get(f'/admin/retencion/?cliente={self.cliente.pk}&curso={self.curso.pk}')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/dashboard/', r['Location'])
        self.assertIn('tab=retencion', r['Location'])
        self.assertIn(f'cliente={self.cliente.pk}', r['Location'])

    @override_settings(STORAGES=_STATIC_TEST_STORAGES, SECURE_SSL_REDIRECT=False)
    def test_dashboard_tab_retencion_carga(self):
        r = self.http.get(
            f'/admin/dashboard/?tab=retencion&cliente={self.cliente.pk}&curso={self.curso.pk}'
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Retención')
        self.assertContains(r, 'Embudo de aprendizaje')
        self.assertContains(r, 'Inscritos')
        self.assertContains(r, 'tab-retencion')
        self.assertContains(r, 'data-loaded="1"')
        self.assertContains(r, 'data-width=')
        self.assertContains(r, 'animateRetencionBars')
        # Payload ejecutivo vacío en tab retención (carga liviana)
        self.assertContains(r, 'type="application/json">{}</script>')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_retencion_admin_requiere_staff(self):
        User.objects.create_user('norm', password='x')
        c = Client()
        c.force_login(User.objects.get(username='norm'))
        r = c.get('/admin/retencion/')
        self.assertEqual(r.status_code, 302)
