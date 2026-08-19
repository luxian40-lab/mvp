"""Login admin: marca eki y layout custom."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1', 'admin.eki.technology'],
    SECURE_SSL_REDIRECT=False,
)
class AdminLoginBrandingTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='admin.eki.technology')

    def test_login_muestra_marca_eki(self):
        r = self.client.get('/admin/login/', follow=True)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('eki-login-shell', body)
        self.assertIn('eki-login-brand', body)
        self.assertIn('Panel de operaciones', body)
        self.assertIn('Iniciar sesión', body)
        self.assertNotIn('Welcome back to', body)
        self.assertNotIn('Return to site', body)

    def test_login_post_csrf_ok(self):
        r = self.client.get('/admin/login/', follow=True)
        csrf = r.context['csrf_token'] if r.context else ''
        r2 = self.client.post(
            '/admin/login/',
            {
                'username': 'nobody',
                'password': 'wrong',
                'csrfmiddlewaretoken': str(csrf),
            },
            HTTP_HOST='admin.eki.technology',
        )
        self.assertEqual(r2.status_code, 200)
        self.assertNotIn(b'CSRF verification failed', r2.content)
