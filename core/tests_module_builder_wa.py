# -*- coding: utf-8 -*-
"""Tests Module Builder WA: estructura + gate media (sin Twilio send)."""
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from core.models import Curso, Modulo, PasoModulo, SeccionModulo
from core.module_structure import (
    detectar_secciones_intercaladas,
    mensaje_error_intercalado,
    modulo_tiene_secciones_intercaladas,
)
from core.twilio_media import (
    WHATSAPP_VIDEO_MAX_BYTES,
    evaluar_mp4_listo_whatsapp,
)


def _mp4_toy():
    ftyp = (20).to_bytes(4, 'big') + b'ftyp' + b'isom' + b'\x00' * 8
    mdat = (12).to_bytes(4, 'big') + b'mdat' + b'XXXX'
    moov = (12).to_bytes(4, 'big') + b'moov' + b'YYYY'
    return ftyp + mdat + moov


class ModuleStructureTests(SimpleTestCase):
    def test_detecta_intercalado_agrosavia_like(self):
        pasos = [
            SimpleNamespace(seccion_id=79, orden=1, pk=1),
            SimpleNamespace(seccion_id=80, orden=2, pk=2),
            SimpleNamespace(seccion_id=80, orden=3, pk=3),
            SimpleNamespace(seccion_id=79, orden=4, pk=4),
            SimpleNamespace(seccion_id=80, orden=5, pk=5),
        ]
        hall = detectar_secciones_intercaladas(pasos)
        self.assertEqual(len(hall), 2)
        self.assertEqual(hall[0]['seccion_id'], 79)
        self.assertEqual(hall[1]['seccion_id'], 80)
        self.assertIn('intercalada', mensaje_error_intercalado(hall).lower())

    def test_contiguo_ok(self):
        pasos = [
            SimpleNamespace(seccion_id=1, orden=1, pk=1),
            SimpleNamespace(seccion_id=1, orden=2, pk=2),
            SimpleNamespace(seccion_id=2, orden=3, pk=3),
            SimpleNamespace(seccion_id=2, orden=4, pk=4),
        ]
        self.assertEqual(detectar_secciones_intercaladas(pasos), [])


class ModuleStructureDbTests(TestCase):
    def test_modulo_intercalado_db(self):
        curso = Curso.objects.create(nombre='MB WA Test')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        sa = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='A')
        sb = SeccionModulo.objects.create(modulo=mod, orden=2, titulo='B')
        PasoModulo.objects.create(
            modulo=mod, seccion=sa, orden=1, tipo=PasoModulo.TIPO_CONTENIDO, contenido='a1',
        )
        PasoModulo.objects.create(
            modulo=mod, seccion=sb, orden=2, tipo=PasoModulo.TIPO_CONTENIDO, contenido='b1',
        )
        PasoModulo.objects.create(
            modulo=mod, seccion=sa, orden=3, tipo=PasoModulo.TIPO_CONTENIDO, contenido='a2',
        )
        hall = modulo_tiene_secciones_intercaladas(mod)
        self.assertTrue(hall)


class EvaluarMp4WhatsappTests(SimpleTestCase):
    def test_cabecera_invalida(self):
        r = evaluar_mp4_listo_whatsapp(b'nope')
        self.assertFalse(r['apto'])
        self.assertEqual(r['razon'], 'cabecera_mp4_invalida')

    def test_supera_limite(self):
        raw = _mp4_toy() + (b'\x00' * (WHATSAPP_VIDEO_MAX_BYTES + 10))
        # Forzar tamaño: toy pequeño + padding grande sin romper ftyp al inicio
        raw = _mp4_toy()[:-4] + (b'Z' * (WHATSAPP_VIDEO_MAX_BYTES))
        r = evaluar_mp4_listo_whatsapp(raw)
        self.assertFalse(r['apto'])
        self.assertIn('supera_', r['razon'])

    @patch('core.twilio_media.mp4_bitstream_ilegible', return_value=False)
    def test_toy_apto_si_no_ilegible(self, _mock):
        r = evaluar_mp4_listo_whatsapp(_mp4_toy())
        self.assertTrue(r['apto'])
        self.assertLessEqual(r['bytes'], WHATSAPP_VIDEO_MAX_BYTES)


class GuardarUploadWaGateTests(SimpleTestCase):
    @patch('core.admin._common._validar_video_decodificable')
    @patch('core.twilio_media.optimizar_mp4_bytes_whatsapp')
    def test_rechaza_si_sigue_grande(self, mock_opt, _mock_val):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from core.admin._common import guardar_upload_admin_media_resultado

        huge = _mp4_toy() + (b'\x00' * (WHATSAPP_VIDEO_MAX_BYTES + 100))
        mock_opt.return_value = huge
        uploaded = SimpleUploadedFile('clip.mp4', huge, content_type='video/mp4')
        with self.assertRaises(ValidationError) as ctx:
            guardar_upload_admin_media_resultado(uploaded, carpeta='t', prefix='p')
        self.assertIn('WhatsApp', str(ctx.exception))
