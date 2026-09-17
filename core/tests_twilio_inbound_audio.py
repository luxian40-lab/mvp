"""Audio inbound Twilio: descarga sin auth en S3 y no tratar nota de voz como *listo*."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.intent_detector import mensaje_indica_listo
from core.twilio_inbound_media import (
    descargar_bytes_twilio,
    es_audio_inbound_twilio,
)


class EsAudioInboundTests(SimpleTestCase):
    def test_ogg_con_codecs_opus(self):
        self.assertTrue(
            es_audio_inbound_twilio(1, 'audio/ogg; codecs=opus', 'https://api.twilio.com/x')
        )

    def test_mime_vacio_con_media_twilio_es_audio(self):
        self.assertTrue(
            es_audio_inbound_twilio(1, '', 'https://api.twilio.com/2010-04-01/Accounts/AC/Messages/MM/Media/ME')
        )

    def test_imagen_no_es_audio(self):
        self.assertFalse(
            es_audio_inbound_twilio(1, 'image/jpeg', 'https://api.twilio.com/x')
        )

    def test_sin_media_no_es_audio(self):
        self.assertFalse(es_audio_inbound_twilio(0, 'audio/ogg', ''))


class DescargaTwilioRedirectTests(SimpleTestCase):
    @override_settings(TWILIO_ACCOUNT_SID='ACtest', TWILIO_AUTH_TOKEN='tok')
    def test_redirect_s3_no_lleva_basic_auth(self):
        twilio_url = 'https://api.twilio.com/2010-04-01/Accounts/AC/Messages/MM/Media/ME'
        s3_url = 'https://s3.amazonaws.com/bucket/nota.ogg'
        calls = []

        def fake_get(url, **kwargs):
            calls.append({'url': url, 'auth': kwargs.get('auth'), 'allow_redirects': kwargs.get('allow_redirects')})
            resp = MagicMock()
            if 'api.twilio.com' in url:
                resp.status_code = 307
                resp.headers = {'Location': s3_url, 'Content-Type': ''}
                resp.content = b''
                resp.raise_for_status.side_effect = AssertionError('no raise en 307')
                return resp
            resp.status_code = 200
            resp.headers = {'Content-Type': 'audio/ogg'}
            resp.content = b'OggS-bytes'
            resp.raise_for_status = MagicMock()
            return resp

        with patch('core.twilio_inbound_media.requests.get', side_effect=fake_get):
            data, ctype = descargar_bytes_twilio(twilio_url)

        self.assertEqual(data, b'OggS-bytes')
        self.assertEqual(ctype, 'audio/ogg')
        self.assertEqual(calls[0]['auth'], ('ACtest', 'tok'))
        self.assertIs(calls[0]['allow_redirects'], False)
        self.assertIsNone(calls[1]['auth'])
        self.assertEqual(calls[1]['url'], s3_url)


class TypoListiTests(SimpleTestCase):
    def test_listi_avanza(self):
        self.assertTrue(mensaje_indica_listo('Listi'))
        self.assertTrue(mensaje_indica_listo('listi'))

    def test_prosa_con_listi_no_avanza(self):
        self.assertFalse(
            mensaje_indica_listo('ya listi para seguir con todo el material del módulo')
        )


class AudioCompaneroNoEsListoTests(TestCase):
    def setUp(self):
        from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante

        self.cli = Cliente.objects.create(
            nombre='Agrosavia QA', activo=True, nombre_agente_asistente='Carlos',
        )
        self.curso = Curso.objects.create(
            nombre='Identificación QA',
            cliente=self.cli,
            activo=True,
            usar_agentes_ia=True,
            nombre_agente_asistente='Carlos',
        )
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Bienvenida', descripcion='d', contenido='c',
            publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='QA-AUD-001',
            nombre='Julian QA',
            telefono='573026480011',
            cliente=self.cli,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_asistente',
            contexto_temporal={
                'tipo': 'asistente_dario',
                'preguntas_hechas': 0,
                'modulo_id': self.mod.id,
                'modulos_reto_ids': [self.mod.id],
            },
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.mod,
        )
        ctx = dict(self.est.contexto_temporal)
        ctx['progreso_id'] = self.prog.id
        self.est.contexto_temporal = ctx
        self.est.save(update_fields=['contexto_temporal'])

    def _webhook(self, extra):
        from core.views import _procesar_twilio_webhook

        payload = {
            'From': f'whatsapp:+{self.est.telefono}',
            'To': 'whatsapp:+14155238886',
            'MessageSid': 'SM_audio_carlos',
            'Body': '',
            'NumMedia': '1',
            'MediaUrl0': 'https://api.twilio.com/2010-04-01/Accounts/AC/Messages/MM/Media/ME',
            **extra,
        }
        mock_tw = MagicMock()
        mock_tw.messages.create.return_value = MagicMock(sid='SM_out')
        with patch('builtins.print'), patch('twilio.rest.Client', MagicMock(return_value=mock_tw)):
            _procesar_twilio_webhook(payload)
        return mock_tw

    def test_mime_vacio_transcribe_y_carlos_responde(self):
        from core.models import WhatsappLog

        with patch(
            'core.views._transcribir_audio_twilio',
            return_value='cuando debo preocuparme por la mortalidad de mis abejas',
        ) as trans, patch(
            'core.tutor_ia_modulo.generar_respuesta_asistente',
            return_value='La mortalidad se monitorea cada semana.',
        ):
            self._webhook({'MediaContentType0': ''})
        trans.assert_called_once()
        cuerpos = ' '.join(
            WhatsappLog.objects.filter(telefono__endswith='80011', tipo='SENT').values_list(
                'mensaje', flat=True
            )
        )
        self.assertNotIn('No pude escuchar', cuerpos)
        self.assertIn('mortalidad', cuerpos.lower())
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')
        self.assertEqual((self.est.contexto_temporal or {}).get('preguntas_hechas'), 1)
