"""Tests subida async de video admin (Celery encode)."""
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from core.admin._common import guardar_upload_admin_media_resultado
from core.media_encode_async import (
    aplicar_resultado_upload_async,
    estado_encode_paso,
    media_encode_paso_key,
)
from core.modulo_publicacion import estado_media_paso
from core.models import Curso, Modulo, PasoModulo, SeccionModulo


def _mp4_toy() -> bytes:
    return (
        b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41'
        b'\x00\x00\x00\x08free'
    )


@override_settings(CELERY_TASK_ALWAYS_EAGER=False)
class GuardarUploadAsyncTests(SimpleTestCase):
    @patch('core.admin._common.guardar_bytes_admin_media_resultado')
    @patch('core.media_encode_async.subir_video_incoming')
    @patch('core.media_encode_async.use_async_media_encode', return_value=True)
    def test_video_deferido_a_incoming(self, _ua, mock_incoming, mock_sync):
        mock_incoming.return_value = ('modulos/pasos/incoming/x.mp4', 'https://s3/x.mp4')
        raw = _mp4_toy() + b'\x00' * 100
        uploaded = SimpleUploadedFile('clip.mp4', raw, content_type='video/mp4')
        r = guardar_upload_admin_media_resultado(uploaded, carpeta='modulos/pasos', prefix='m1')
        self.assertTrue(r.get('async_encode'))
        self.assertIsNone(r.get('media_wa_apto'))
        self.assertEqual(r['url'], 'https://s3/x.mp4')
        mock_sync.assert_not_called()
        mock_incoming.assert_called_once()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class GuardarUploadSyncEagerTests(SimpleTestCase):
    @patch('core.admin._common.guardar_bytes_admin_media_resultado')
    def test_eager_usa_sync(self, mock_sync):
        mock_sync.return_value = {
            'url': 'https://s3/final.mp4',
            'media_wa_apto': True,
            'bytes': 10,
            'razon': '',
        }
        raw = _mp4_toy() + b'\x00' * 100
        uploaded = SimpleUploadedFile('clip.mp4', raw, content_type='video/mp4')
        r = guardar_upload_admin_media_resultado(uploaded, carpeta='t', prefix='p')
        self.assertNotIn('async_encode', r)
        self.assertTrue(r.get('media_wa_apto'))
        mock_sync.assert_called_once()


class EstadoMediaProcesandoTests(TestCase):
    def setUp(self):
        curso = Curso.objects.create(nombre='Async QA', descripcion='d', dias_espera_entre_modulos=0)
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='d', contenido='x', duracion_dias=7
        )
        sec = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='S1', activa=True)
        self.paso = PasoModulo.objects.create(
            modulo=mod,
            seccion=sec,
            orden=1,
            titulo='V',
            contenido='',
            media_url='https://s3/incoming/x.mp4',
            media_wa_apto=None,
            activo=True,
        )

    def tearDown(self):
        cache.delete(media_encode_paso_key(self.paso.pk))

    def test_semaforo_procesando(self):
        cache.set(
            media_encode_paso_key(self.paso.pk),
            {'status': 'running', 'paso_id': self.paso.pk},
            60,
        )
        code, label = estado_media_paso(self.paso)
        self.assertEqual(code, 'warn')
        self.assertIn('Procesando', label)

    def test_reconcilia_cache_stale_cuando_url_ya_no_incoming(self):
        cache.set(
            media_encode_paso_key(self.paso.pk),
            {'status': 'pending', 'paso_id': self.paso.pk},
            60,
        )
        self.paso.media_url = 'https://s3/modulos/pasos/2026/final.mp4'
        self.paso.media_wa_apto = True
        self.paso.save(update_fields=['media_url', 'media_wa_apto'])
        enc = estado_encode_paso(self.paso.pk, paso=self.paso)
        self.assertIsNone(enc)
        self.assertIsNone(cache.get(media_encode_paso_key(self.paso.pk)))

    def test_incoming_y_no_apto_es_error_sin_cache(self):
        self.paso.media_wa_apto = False
        self.paso.save(update_fields=['media_wa_apto'])
        enc = estado_encode_paso(self.paso.pk, paso=self.paso)
        self.assertEqual(enc.get('status'), 'error')

    def test_incoming_sin_apto_sin_cache_es_pending(self):
        enc = estado_encode_paso(self.paso.pk, paso=self.paso)
        self.assertEqual(enc.get('status'), 'pending')

    @patch('core.media_encode_async.encolar_encode_paso_modulo')
    def test_encolar_setea_cache(self, mock_encolar):
        resultado = {
            'async_encode': True,
            'job_id': 'job-1',
            'temp_s3_path': 'incoming/x.mp4',
            'filename': 'x.mp4',
            'carpeta': 'modulos/pasos',
            'prefix': 'm1',
        }
        ok = aplicar_resultado_upload_async(
            resultado, self.paso.pk, carpeta='modulos/pasos', prefix='m1'
        )
        self.assertTrue(ok)
        mock_encolar.assert_called_once_with(
            paso_id=self.paso.pk,
            job_id='job-1',
            temp_s3_path='incoming/x.mp4',
            filename='x.mp4',
            carpeta='modulos/pasos',
            prefix='m1',
        )
