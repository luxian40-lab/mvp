"""Una nota de voz se transcribe una vez dentro del turno y siempre fuera de él."""
from unittest.mock import Mock

from django.test import SimpleTestCase

from core.conversacion.transcripcion_turno import del_turno, un_turno


class TranscripcionTurnoTests(SimpleTestCase):
    def test_dentro_del_turno_el_mismo_audio_se_transcribe_una_vez(self):
        transcribir = Mock(return_value='hola')
        with un_turno():
            self.assertEqual(del_turno('media1', transcribir), 'hola')
            self.assertEqual(del_turno('media1', transcribir), 'hola')
        self.assertEqual(transcribir.call_count, 1)

    def test_audios_distintos_se_transcriben_cada_uno(self):
        transcribir = Mock(side_effect=['uno', 'dos'])
        with un_turno():
            self.assertEqual(del_turno('media1', transcribir), 'uno')
            self.assertEqual(del_turno('media2', transcribir), 'dos')
        self.assertEqual(transcribir.call_count, 2)

    def test_fuera_del_turno_no_guarda(self):
        transcribir = Mock(return_value='hola')
        del_turno('media1', transcribir)
        del_turno('media1', transcribir)
        self.assertEqual(transcribir.call_count, 2)

    def test_un_turno_nuevo_no_ve_lo_del_anterior(self):
        transcribir = Mock(return_value='hola')
        with un_turno():
            del_turno('media1', transcribir)
        with un_turno():
            del_turno('media1', transcribir)
        self.assertEqual(transcribir.call_count, 2)

    def test_transcripcion_fallida_se_guarda_y_no_se_reintenta(self):
        transcribir = Mock(return_value=None)
        with un_turno():
            self.assertIsNone(del_turno('media1', transcribir))
            self.assertIsNone(del_turno('media1', transcribir))
        self.assertEqual(transcribir.call_count, 1)

    def test_si_transcribir_lanza_no_queda_guardado(self):
        transcribir = Mock(side_effect=[RuntimeError('red'), 'hola'])
        with un_turno():
            with self.assertRaises(RuntimeError):
                del_turno('media1', transcribir)
            self.assertEqual(del_turno('media1', transcribir), 'hola')
        self.assertEqual(transcribir.call_count, 2)

    def test_sin_id_no_guarda(self):
        transcribir = Mock(return_value='hola')
        with un_turno():
            del_turno('', transcribir)
            del_turno('', transcribir)
        self.assertEqual(transcribir.call_count, 2)
