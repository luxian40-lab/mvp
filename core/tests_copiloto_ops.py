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
    def test_view_staff(self):
        User = get_user_model()
        u = User.objects.create_user('ops', password='x', is_staff=True, is_superuser=True)
        self.client.force_login(u)
        r = self.client.get(reverse('copiloto_ops'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Copiloto ops')
