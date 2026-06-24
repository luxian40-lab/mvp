"""Tests del panel admin Aula web eki."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Estudiante
from portal.models import PortalUsuario


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AulaWebAdminTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.staff = User.objects.create_superuser('admin_aw', 'a@t.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org AW',
            contacto_principal='X',
            email='aw@test.com',
            telefono='573001111001',
            activo=True,
        )
        Estudiante.objects.create(
            cedula='aw1',
            nombre='Est AW',
            telefono='573001111002',
            cliente=self.cliente,
            activo=True,
        )
        prof_user = User.objects.create_user('prof_aw', 'p@t.com', 'pass')
        PortalUsuario.objects.create(user=prof_user, organizacion=self.cliente, rol='profesor')

    def test_panel_carga(self):
        self.http.force_login(self.staff)
        r = self.http.get('/admin/aula-web/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Aula web eki')
        self.assertContains(r, 'portal clientes')

    def test_redirect_viejo_portal_estudio(self):
        self.http.force_login(self.staff)
        r = self.http.get('/admin/portal-estudio/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/aula-web/', r['Location'])
