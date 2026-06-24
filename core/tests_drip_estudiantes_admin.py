from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente


class DripEstudiantesAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_drip', 'd@c.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org Drip',
            contacto_principal='A',
            email='drip@test.com',
            telefono='573005555551',
            activo=True,
        )
        self.http = Client()

    def test_requiere_staff(self):
        r = self.http.get('/admin/drip-estudiantes/')
        self.assertEqual(r.status_code, 302)

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_pagina_con_cliente(self):
        self.http.login(username='admin_drip', password='pass')
        r = self.http.get(f'/admin/drip-estudiantes/?cliente={self.cliente.id}')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Acceso a módulos por estudiante')
