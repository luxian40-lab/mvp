# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.course_engine.tts import TtsResult
from core.course_engine.voice_preview import generar_muestra_voz
from core.models import Cliente, Curso


@override_settings(
    ELEVENLABS_API_KEY='test-key',
    ELEVENLABS_VOICE_ID='env_default_voice',
)
class VoicePreviewTests(TestCase):
    def test_generar_muestra_sin_voice_id(self):
        out = generar_muestra_voz('')
        self.assertFalse(out.ok)
        self.assertIn('Voice ID vacio', out.error)

    @patch('core.course_engine.voice_preview.generar_narracion')
    def test_generar_muestra_ok(self, mock_tts):
        mock_tts.return_value = TtsResult(
            url='https://eki-produccion.s3.us-east-2.amazonaws.com/x.mp3',
            s3_key='media/x.mp3',
            bytes_size=12000,
            provider='elevenlabs',
            voice='abc123',
            text_hash='h',
        )
        out = generar_muestra_voz('abc123', voice_label='Maria')
        self.assertTrue(out.ok)
        self.assertEqual(out.voice_id, 'abc123')
        mock_tts.assert_called_once()

    @patch('core.course_engine.voice_preview.generar_muestra_voz')
    def test_admin_preview_curso_requiere_login(self, mock_gen):
        mock_gen.return_value = type('R', (), {'ok': True, 'voice_id': 'v', 'voice_label': 'L', 'tts': None, 'error': ''})()
        curso = Curso.objects.create(nombre='Test', descripcion='d')
        url = reverse('admin:core_curso_preview_voz', args=[curso.pk])
        resp = Client().get(url, follow=True)
        self.assertIn(resp.status_code, (200, 302))
        if resp.status_code == 200:
            self.assertContains(resp, 'login', status_code=200)

    @patch('core.course_engine.voice_preview.generar_muestra_voz')
    def test_admin_preview_curso_staff(self, mock_gen):
        mock_gen.return_value = type(
            'R',
            (),
            {
                'ok': True,
                'voice_id': 'voice_test',
                'voice_label': 'eki',
                'tts': TtsResult(
                    url='https://example.com/a.mp3',
                    s3_key='k',
                    bytes_size=100,
                    provider='elevenlabs',
                    voice='voice_test',
                    text_hash='h',
                ),
                'error': '',
            },
        )()
        User = get_user_model()
        user = User.objects.create_superuser('qa', 'qa@test.com', 'pass')
        cliente = Cliente.objects.create(nombre='Org QA')
        curso = Curso.objects.create(
            nombre='Broca',
            descripcion='d',
            cliente=cliente,
            course_engine_voice_id='voice_test',
            course_engine_voice_label='Voz QA',
        )
        client = Client()
        client.force_login(user)
        url = reverse('admin:core_curso_preview_voz', args=[curso.pk])
        resp = client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'voice_test')
        self.assertContains(resp, 'audio/mpeg')

    def test_admin_curso_change_form_ok(self):
        User = get_user_model()
        user = User.objects.create_superuser('qa_change', 'qa_change@test.com', 'pass')
        cliente = Cliente.objects.create(nombre='Org change')
        curso = Curso.objects.create(
            nombre='Curso change QA',
            descripcion='d',
            cliente=cliente,
            course_engine_voice_id='Wb1wmVQjMx9g2QSIOTPI',
        )
        client = Client()
        client.force_login(user)
        url = reverse('admin:core_curso_change', args=[curso.pk])
        resp = client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'course_engine_voice_id')
        self.assertContains(resp, 'Course Engine')
