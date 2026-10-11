# -*- coding: utf-8 -*-
"""El componente de subida no conoce el Module Builder."""
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core.media_upload_servicio import validar_archivo


class MediaUploadServicioTests(SimpleTestCase):
    def test_rechaza_tipo_y_tamano(self):
        malo = validar_archivo('notas.exe', 100, 'application/octet-stream')
        self.assertFalse(malo['ok'])
        self.assertIn('no está permitido', malo['error'])
        grande = validar_archivo('foto.png', 6 * 1024 * 1024, 'image/png')
        self.assertFalse(grande['ok'])
        self.assertIn('demasiado grande', grande['error'])
        bien = validar_archivo('foto.png', 1024, 'image/png')
        self.assertTrue(bien['ok'])
        self.assertEqual(bien['tipo'], 'imagen')

    @override_settings(WHATSAPP_VIDEO_MAX_BYTES=10)
    def test_el_tope_sale_de_settings(self):
        r = validar_archivo('clip.mp4', 11, 'video/mp4')
        self.assertFalse(r['ok'])

    def test_el_javascript_no_importa_el_builder(self):
        js = Path('static/js/media-uploader/uploader.js').read_text(encoding='utf-8')
        py = Path('core/media_upload_servicio.py').read_text(encoding='utf-8')
        self.assertNotIn('module_builder', js)
        self.assertNotIn('unfold', js.lower())
        self.assertNotIn('module_builder', py)
        for evento in ('upload:progress', 'upload:done', 'upload:error', 'upload:cancel'):
            self.assertIn(evento, js)
        self.assertIn('role="progressbar"', js)
        self.assertIn('Cancelar', js)
        self.assertIn('Reintentar', js)
