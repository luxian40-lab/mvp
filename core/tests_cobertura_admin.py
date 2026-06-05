from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente


class AdminCoberturaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_cob', 'a@c.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org Admin Mapa',
            contacto_principal='A',
            email='adminmapa@test.com',
            telefono='573004444441',
            activo=True,
        )
        self.http = Client()

    def test_cobertura_admin_requiere_staff(self):
        r = self.http.get('/admin/cobertura/')
        self.assertEqual(r.status_code, 302)

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_cobertura_admin_con_cliente(self):
        self.http.login(username='admin_cob', password='pass')
        r = self.http.get(f'/admin/cobertura/?cliente={self.cliente.id}')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'mapa-cobertura')

    def test_cobertura_admin_api(self):
        self.http.login(username='admin_cob', password='pass')
        r = self.http.get(f'/admin/cobertura/datos.json?cliente={self.cliente.id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('total_estudiantes', r.json())
