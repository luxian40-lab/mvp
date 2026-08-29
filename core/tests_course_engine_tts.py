# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.course_engine.tts_service import (
    DEFAULT_VOICE,
    MAX_CHARS,
    generar_audio_tts,
)


@override_settings(OPENAI_API_KEY='test-key')
class TtsServiceTests(SimpleTestCase):
    def test_texto_vacio_retorna_none(self):
        self.assertIsNone(generar_audio_tts('   ', openai_client=MagicMock()))

    def test_texto_largo_se_trunca(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b'fake-mp3-bytes'
        mock_client.audio.speech.create.return_value = mock_response

        with patch('core.course_engine.tts_service._subir_bytes_s3', return_value='https://example.com/a.mp3'):
            result = generar_audio_tts('x' * (MAX_CHARS + 500), openai_client=mock_client)

        self.assertIsNotNone(result)
        call_kw = mock_client.audio.speech.create.call_args.kwargs
        self.assertEqual(len(call_kw['input']), MAX_CHARS)

    def test_genera_y_sube_mp3(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b'\xff\xfb' + b'0' * 100
        mock_client.audio.speech.create.return_value = mock_response

        fake_url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/course_engine/tts/abc.mp3'
        with patch('core.course_engine.tts_service._subir_bytes_s3', return_value=fake_url) as upload:
            result = generar_audio_tts('Hola eki', voice='nova', openai_client=mock_client)

        self.assertIsNotNone(result)
        self.assertEqual(result.url, fake_url)
        self.assertEqual(result.voice, 'nova')
        upload.assert_called_once()
        args = upload.call_args[0]
        self.assertTrue(args[0].startswith('media/course_engine/tts/'))
        self.assertEqual(args[2], 'audio/mpeg')

    def test_voz_invalida_usa_default(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b'mp3'
        mock_client.audio.speech.create.return_value = mock_response

        with patch('core.course_engine.tts_service._subir_bytes_s3', return_value='https://example.com/a.mp3'):
            result = generar_audio_tts('test', voice='no-existe', openai_client=mock_client)

        self.assertEqual(result.voice, DEFAULT_VOICE)
        self.assertEqual(mock_client.audio.speech.create.call_args.kwargs['voice'], DEFAULT_VOICE)

    def test_openai_error_retorna_none(self):
        mock_client = MagicMock()
        mock_client.audio.speech.create.side_effect = RuntimeError('api down')
        self.assertIsNone(generar_audio_tts('hola', openai_client=mock_client))
