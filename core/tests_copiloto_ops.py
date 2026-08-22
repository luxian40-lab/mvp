from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.copiloto_ops import _mask_tel, responder_copiloto, snapshot_ops
from core.models import WhatsappLog
from mvp_project.staticfiles_storage import EkiManifestStaticFilesStorage


class ManifestNoTumbaTests(TestCase):
    def test_strict_off(self):
        self.assertFalse(EkiManifestStaticFilesStorage.manifest_strict)


class CopilotoOpsTests(TestCase):
    def test_mask(self):
        self.assertEqual(_mask_tel('573026480629'), '…0629')

    @override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='')
    def test_snapshot_cuenta_63021(self):
        WhatsappLog.objects.create(
            telefono='573001112233',
            tipo='SENT',
            estado='undelivered',
            error_detalle='63021 Unable to process',
        )
        snap = snapshot_ops(horas=24)
        self.assertGreaterEqual(snap['n_63021'], 1)
        self.assertEqual(snap['ejemplos_fallos'][0]['tel'], '…2233')

    @override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='', OPENAI_API_KEY='')
    def test_reglas_sin_openai(self):
        out = responder_copiloto('¿Qué falló?')
        self.assertEqual(out['fuente'], 'reglas')
        self.assertIn('envíos', out['respuesta'].lower())

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_view_staff_redirige_a_inicio(self):
        User = get_user_model()
        u = User.objects.create_user('ops', password='x', is_staff=True, is_superuser=True)
        self.client.force_login(u)
        r = self.client.get(reverse('copiloto_ops'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/?copiloto=1', r.url)

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        TWILIO_ACCOUNT_SID='',
        TWILIO_AUTH_TOKEN='',
        OPENAI_API_KEY='',
    )
    def test_ask_json(self):
        User = get_user_model()
        u = User.objects.create_user('ops2', password='x', is_staff=True, is_superuser=True)
        self.client.force_login(u)
        r = self.client.post(
            reverse('copiloto_ask'),
            data='{"pregunta":"¿Qué falló?"}',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload['ok'])
        self.assertIn('envíos', payload['respuesta'].lower())

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_header_tiene_chat(self):
        User = get_user_model()
        User.objects.create_user('ops3', password='x', is_staff=True, is_superuser=True)
        self.client.force_login(User.objects.get(username='ops3'))
        r = self.client.get('/admin/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'eki-copiloto-drawer')
        self.assertContains(r, 'eki_copiloto_chat.js')
