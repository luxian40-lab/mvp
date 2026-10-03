"""Whisper borra el audio local al terminar, con error o sin él."""
import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


class TranscripcionBorraAudioTests(SimpleTestCase):
    def _procesador(self, media_root, openai):
        from core.audio_processor import AudioProcessor

        with override_settings(MEDIA_ROOT=media_root, OPENAI_API_KEY='sk-test'):
            with patch('core.audio_processor.OpenAI', return_value=openai) as ctor:
                proc = AudioProcessor()
        ctor.assert_called_once_with(api_key='sk-test', timeout=30)
        return proc

    def test_exito_borra_el_archivo(self):
        import tempfile

        with tempfile.TemporaryDirectory() as media_root:
            carpeta = os.path.join(media_root, 'audios_whatsapp')
            os.makedirs(carpeta)
            archivo = os.path.join(carpeta, 'nota.ogg')
            with open(archivo, 'wb') as fh:
                fh.write(b'ogg')
            cliente = MagicMock()
            cliente.audio.transcriptions.create.return_value = MagicMock(text='  hola  ')
            proc = self._procesador(media_root, cliente)
            self.assertEqual(proc.transcribir_audio(archivo), 'hola')
            self.assertFalse(os.path.exists(archivo))

    def test_error_tambien_borra_el_archivo(self):
        import tempfile

        with tempfile.TemporaryDirectory() as media_root:
            carpeta = os.path.join(media_root, 'audios_whatsapp')
            os.makedirs(carpeta)
            archivo = os.path.join(carpeta, 'nota.ogg')
            with open(archivo, 'wb') as fh:
                fh.write(b'ogg')
            cliente = MagicMock()
            cliente.audio.transcriptions.create.side_effect = RuntimeError('whisper')
            proc = self._procesador(media_root, cliente)
            self.assertIsNone(proc.transcribir_audio(archivo))
            self.assertFalse(os.path.exists(archivo))
