# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.course_engine.storyboard import generar_storyboard
from core.course_engine.tts import generar_narracion
from core.course_engine.types import LessonAnalysis, LessonDraft, SceneType


@override_settings(
    ELEVENLABS_API_KEY='test-el',
    ELEVENLABS_VOICE_ID='voice123',
    COURSE_ENGINE_TTS_PROVIDER='elevenlabs',
    COURSE_ENGINE_TTS_FALLBACK_OPENAI=False,
)
class ElevenLabsTtsTests(SimpleTestCase):
    def test_genera_y_sube_via_elevenlabs(self):
        fake_url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/course_engine/tts/abc.mp3'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'\xff\xfb' + b'0' * 50
        mock_resp.raise_for_status = MagicMock()

        with patch('httpx.post', return_value=mock_resp) as post:
            with patch('core.course_engine.tts._subir_bytes_s3', return_value=fake_url):
                result = generar_narracion('Hola campo')

        self.assertIsNotNone(result)
        self.assertEqual(result.provider, 'elevenlabs')
        self.assertEqual(result.voice, 'voice123')
        post.assert_called_once()
        self.assertIn('voice123', post.call_args[0][0])

    def test_sin_api_key_retorna_none(self):
        with self.settings(ELEVENLABS_API_KEY=''):
            self.assertIsNone(generar_narracion('hola'))


@override_settings(OPENAI_API_KEY='test-key')
class StoryboardTests(SimpleTestCase):
    def test_genera_escenas_desde_openai(self):
        lesson = LessonDraft(titulo='Riego', contenido='...', puntos_clave=['a'])
        analysis = LessonAnalysis(
            audiencia='Agricultores',
            duracion_estimada_min=3,
            conceptos=['riego'],
            riesgos_pedagogicos=[],
            recomendacion_formato='mixto',
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"titulo_leccion":"Riego","objetivo":"Aprender","escenas":'
                            '[{"orden":1,"tipo":"narracion","titulo":"Intro","guion":"Hola",'
                            '"duracion_seg":5,"notas_visuales":""}]}'
                        )
                    )
                )
            ]
        )

        sb = generar_storyboard(lesson, analysis, openai_client=mock_client)

        self.assertIsNotNone(sb)
        self.assertEqual(len(sb.escenas), 1)
        self.assertEqual(sb.escenas[0].tipo, SceneType.NARRACION)
