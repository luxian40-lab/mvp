"""Alerta ops al agotar reintentos de media WhatsApp."""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.media_entrega import notificar_fallo_media_ops
from core.models import WhatsappLog


class NotificarFalloMediaOpsTests(TestCase):
    def setUp(self):
        self.log = WhatsappLog.objects.create(
            telefono='573001112233',
            mensaje='x [MEDIA:https://cdn.example.com/mod1.mp4]',
            tipo='SENT',
            estado='UNDELIVERED',
            mensaje_id='MMtest63021',
            error_detalle='63021',
        )

    @override_settings(
        EKI_SLACK_OPS_WEBHOOK='https://hooks.slack.test/x',
        EKI_MEDIA_FAIL_EMAIL=True,
        EMAIL_SOPORTE='ops@eki.test',
        DEFAULT_FROM_EMAIL='eki@eki.test',
    )
    @patch('core.ops_slack.notify_slack_ops', return_value=True)
    @patch('django.core.mail.send_mail')
    def test_notifica_una_vez(self, mock_mail, mock_slack):
        notificar_fallo_media_ops(self.log, error_code='63021', intentos=2)
        mock_slack.assert_called_once()
        mock_mail.assert_called_once()
        self.log.refresh_from_db()
        self.assertIn('NOTIFIED_OPS', self.log.error_detalle)

        notificar_fallo_media_ops(self.log, error_code='63021', intentos=2)
        self.assertEqual(mock_slack.call_count, 1)
        self.assertEqual(mock_mail.call_count, 1)
