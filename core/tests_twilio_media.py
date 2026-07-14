"""Tests for Twilio media helpers and 63021 fallback."""
from django.test import SimpleTestCase, TestCase

from core.models import WhatsappLog
from core.twilio_media import (
    cuerpo_con_enlace_archivo,
    es_error_media_twilio,
    extraer_media_url_de_mensaje,
    mensaje_log_con_media,
    normalizar_media_url_s3,
    url_no_es_media_directo,
    ya_envio_fallback_enlace,
)


class TwilioMediaHelpersTests(SimpleTestCase):
    def test_es_error_media_codes(self):
        self.assertTrue(es_error_media_twilio(63021))
        self.assertTrue(es_error_media_twilio('HTTP 400: 63019 Media download failed'))
        self.assertTrue(es_error_media_twilio('63005 Channel rejected'))
        self.assertFalse(es_error_media_twilio(21211))
        self.assertFalse(es_error_media_twilio('ok'))

    def test_normalizar_s3_regional(self):
        u = 'https://eki-produccion.s3.amazonaws.com/media/a.mp4'
        out = normalizar_media_url_s3(u)
        self.assertIn('s3.us-east-2.amazonaws.com', out)

    def test_youtube_no_directo(self):
        self.assertTrue(url_no_es_media_directo('https://www.youtube.com/watch?v=abc'))
        self.assertFalse(url_no_es_media_directo('https://eki-produccion.s3.us-east-2.amazonaws.com/x.mp4'))

    def test_mensaje_log_persiste_media(self):
        msg = mensaje_log_con_media('Aquí tiene el material', 'https://cdn.example/a.mp4')
        self.assertIn('[MEDIA:https://cdn.example/a.mp4]', msg)
        self.assertEqual(extraer_media_url_de_mensaje(msg), 'https://cdn.example/a.mp4')

    def test_cuerpo_enlace(self):
        body = cuerpo_con_enlace_archivo('Ver material', 'https://cdn.example/a.mp4')
        self.assertIn('📎 Archivo:', body)
        self.assertIn('https://cdn.example/a.mp4', body)

    def test_mp4_faststart_remux_mueve_moov(self):
        from core.twilio_media import mp4_necesita_faststart, remux_mp4_faststart

        # ftyp(8+8) + mdat(8+4) + moov(8+4) — moov al final
        ftyp = (20).to_bytes(4, 'big') + b'ftyp' + b'isom' + b'\x00' * 8
        mdat = (12).to_bytes(4, 'big') + b'mdat' + b'XXXX'
        moov = (12).to_bytes(4, 'big') + b'moov' + b'YYYY'
        raw = ftyp + mdat + moov
        self.assertTrue(mp4_necesita_faststart(raw))
        fixed = remux_mp4_faststart(raw)
        self.assertFalse(mp4_necesita_faststart(fixed))
        # moov debe ir antes de mdat
        self.assertLess(fixed.find(b'moov'), fixed.find(b'mdat'))


class TwilioMediaCallbackFallbackTests(TestCase):
    def test_ya_envio_fallback(self):
        log = WhatsappLog(mensaje='x', error_detalle='63021 | FALLBACK_ENLACE')
        self.assertTrue(ya_envio_fallback_enlace(log))

    def test_callback_63021_reenvia_enlace(self):
        from unittest.mock import patch

        from core.views import _registrar_estado_twilio_callback

        url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/demo.mp4'
        log = WhatsappLog.objects.create(
            telefono='573026480629',
            mensaje=mensaje_log_con_media('Aquí tiene el material del módulo. Revíselo con calma.', url),
            mensaje_id='MMf414dea0218286e02a3c412db3e35866',
            tipo='SENT',
            estado='SENT',
        )
        with patch('core.utils.enviar_whatsapp_twilio') as send_mock:
            send_mock.return_value = {'success': True}
            _registrar_estado_twilio_callback({
                'MessageSid': log.mensaje_id,
                'MessageStatus': 'undelivered',
                'ErrorCode': '63021',
                'ErrorMessage': 'Channel invalid content error',
            })
            send_mock.assert_called_once()
            args, kwargs = send_mock.call_args
            self.assertEqual(args[0], '573026480629')
            self.assertIn(url, args[1])
            self.assertIn('📎 Archivo:', args[1])

        log.refresh_from_db()
        self.assertEqual(log.estado, 'UNDELIVERED')
        self.assertIn('63021', log.error_detalle or '')
        self.assertIn('FALLBACK_ENLACE', log.error_detalle or '')
