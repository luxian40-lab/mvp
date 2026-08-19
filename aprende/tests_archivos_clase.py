"""Límites de archivo de clase y wallpaper aula."""

from __future__ import annotations

from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from aprende.archivos_aula import MAX_VIDEO_CLASE_MB, validar_archivo_clase_profesor
from portal.utils import WALLPAPER_MAX_BYTES


class ValidarVideoClaseTests(SimpleTestCase):
    def test_video_ok_bajo_limite(self):
        f = SimpleUploadedFile('clase.mp4', b'x' * 1024, content_type='video/mp4')
        validar_archivo_clase_profesor(f, tipo_hint='video')  # no raise

    def test_video_rechaza_sobre_100mb(self):
        f = SimpleNamespace(
            name='pesado.mp4',
            size=(MAX_VIDEO_CLASE_MB + 1) * 1024 * 1024,
        )
        with self.assertRaises(ValidationError) as ctx:
            validar_archivo_clase_profesor(f, tipo_hint='video')
        self.assertIn('100', str(ctx.exception))


class WallpaperBytesTests(SimpleTestCase):
    def test_limite_2mb(self):
        self.assertEqual(WALLPAPER_MAX_BYTES, 2 * 1024 * 1024)
