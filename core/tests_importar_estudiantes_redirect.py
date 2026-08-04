"""Compat: /admin/importar-estudiantes/ → importador LatAm del ModelAdmin."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class TestImportarEstudiantesRedirect(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='ops_import', email='ops@import.test', password='x',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_legacy_url_redirige_a_admin_importar(self):
        r = self.client.get(reverse('importar_estudiantes'), follow=False)
        self.assertIn(r.status_code, (301, 302))
        self.assertIn('/admin/core/estudiante/importar/', r['Location'])

    def test_admin_importar_responde_200(self):
        r = self.client.get(reverse('admin:core_estudiante_importar'), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Importar')
