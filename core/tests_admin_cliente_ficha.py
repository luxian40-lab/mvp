"""Ficha Cliente: banda de identidad + preview de logo/wallpaper (patrón certificados)."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Cliente


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ClienteFichaIdentidadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('ficha_cli', 'f@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Alitic Ficha',
            contacto_principal='Dirección académica',
            email='org@test.com',
            telefono='573001110044',
            nit='900123',
            activo=True,
            tipo_proyecto='cursos',
            logo_url='https://example.com/logo-alitic.png',
            wallpaper_aula_url='https://example.com/fondo-aprende.jpg',
            fecha_fin_suscripcion='2099-12-31',
        )

    def test_ficha_muestra_banda_y_imagenes(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_cliente_change', args=[self.cliente.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('eki-id-band', body)
        self.assertIn('eki-id-preview', body)
        self.assertIn('Alitic Ficha', body)
        self.assertIn('Cursos eki', body)
        self.assertIn('https://example.com/logo-alitic.png', body)
        self.assertIn('https://example.com/fondo-aprende.jpg', body)
        self.assertIn('Así se ve', body)
        self.assertIn('Fondo Aprende', body)

    def test_alta_sin_banda(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_cliente_add'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertNotIn('eki-id-band', body)
        self.assertNotIn('eki-id-preview', body)

    def test_sin_logo_muestra_inicial(self):
        self.cliente.logo_url = ''
        self.cliente.wallpaper_aula_url = ''
        self.cliente.save(update_fields=['logo_url', 'wallpaper_aula_url'])
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_cliente_change', args=[self.cliente.pk]))
        body = r.content.decode('utf-8')
        self.assertIn('eki-id-band__thumb--ph', body)
        self.assertIn('Sin logo', body)
        self.assertIn('Sin fondo', body)
