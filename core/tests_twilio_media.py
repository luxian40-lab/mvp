"""Tests for Twilio media helpers (sin links S3 en WhatsApp)."""
from django.test import SimpleTestCase, TestCase

from core.models import WhatsappLog
from core.twilio_media import (
    cuerpo_con_enlace_archivo,
    es_error_media_twilio,
    es_url_s3_o_firmada,
    extraer_media_url_de_mensaje,
    media_requiere_enlace_previo,
    mensaje_log_con_media,
    normalizar_media_url_s3,
    url_no_es_media_directo,
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

    def test_normalizar_no_rompe_firma_convertir_a_publica(self):
        """URL firmada → pública regional (sin query X-Amz). Evita 63019."""
        firmada = (
            'https://eki-produccion.s3.amazonaws.com/c1/VIDEOS_FINANZAS/Modulo_0.mp4'
            '?response-content-type=video%2Fmp4&X-Amz-Algorithm=AWS4-HMAC-SHA256'
            '&X-Amz-Signature=abc123'
        )
        out = normalizar_media_url_s3(firmada)
        self.assertEqual(
            out,
            'https://eki-produccion.s3.us-east-2.amazonaws.com/c1/VIDEOS_FINANZAS/Modulo_0.mp4',
        )
        self.assertNotIn('X-Amz-', out)

    def test_normalizar_encode_espacios(self):
        u = 'https://eki-produccion.s3.amazonaws.com/c1/VIDEOS_FINANZAS/2.2. Presupuesto.jpg.jpeg'
        out = normalizar_media_url_s3(u)
        self.assertIn('%20', out)
        self.assertIn('s3.us-east-2.amazonaws.com', out)

    def test_youtube_no_directo(self):
        self.assertTrue(url_no_es_media_directo('https://www.youtube.com/watch?v=abc'))
        self.assertFalse(url_no_es_media_directo('https://eki-produccion.s3.us-east-2.amazonaws.com/x.mp4'))

    def test_mensaje_log_persiste_media(self):
        msg = mensaje_log_con_media('Aquí tiene el material', 'https://cdn.example/a.mp4')
        self.assertIn('[MEDIA:https://cdn.example/a.mp4]', msg)
        self.assertEqual(extraer_media_url_de_mensaje(msg), 'https://cdn.example/a.mp4')

    def test_cuerpo_enlace_permite_externo_bloquea_s3(self):
        body = cuerpo_con_enlace_archivo('Ver material', 'https://youtu.be/abc')
        self.assertIn('📎 Archivo:', body)
        self.assertIn('https://youtu.be/abc', body)

        s3 = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/a.mp4'
        self.assertTrue(es_url_s3_o_firmada(s3))
        body_s3 = cuerpo_con_enlace_archivo('Ver material', s3)
        self.assertEqual(body_s3, 'Ver material')
        self.assertNotIn('amazonaws.com', body_s3)

        firmada = 'https://eki-produccion.s3.us-east-2.amazonaws.com/x.mp4?X-Amz-Signature=abc'
        self.assertEqual(cuerpo_con_enlace_archivo('hola', firmada), 'hola')

    def test_media_requiere_enlace_previo_desactivado(self):
        self.assertFalse(media_requiere_enlace_previo('https://x/a.mp4'))
        self.assertFalse(media_requiere_enlace_previo('https://x/a.png'))

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
    def test_callback_63021_reintenta_media_sin_link_s3_en_texto(self):
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
            send_mock.return_value = {'success': True, 'mensaje_id': 'MMnew'}
            with patch('core.twilio_media.preparar_url_media_whatsapp', side_effect=lambda u: u):
                _registrar_estado_twilio_callback({
                    'MessageSid': log.mensaje_id,
                    'MessageStatus': 'undelivered',
                    'ErrorCode': '63021',
                    'ErrorMessage': 'Channel invalid content error',
                })
            send_mock.assert_called_once()
            body = send_mock.call_args.kwargs.get('texto') or send_mock.call_args[0][1]
            self.assertNotIn('amazonaws.com', body)

        log.refresh_from_db()
        self.assertEqual(log.estado, 'UNDELIVERED')
        self.assertIn('63021', log.error_detalle or '')
        self.assertIn('RETRY:1', log.error_detalle or '')
