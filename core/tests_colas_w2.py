"""W2: profundidad y edad de colas Celery."""
import json
import time
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from core.analitica.colas_w2 import (
    _epoch_de_sobre,
    edad_segundos_desde_epoch,
    snapshot_colas_w2,
)


class ColasW2ParseTests(SimpleTestCase):
    def test_epoch_desde_headers_timestamp(self):
        ahora = time.time()
        bruto = json.dumps({'headers': {'timestamp': ahora - 90}, 'body': '{}'})
        self.assertAlmostEqual(_epoch_de_sobre(bruto), ahora - 90, delta=1)

    def test_edad_segundos(self):
        self.assertEqual(edad_segundos_desde_epoch(100.0, ahora=190.0), 90)
        self.assertIsNone(edad_segundos_desde_epoch(None, ahora=1.0))


class ColasW2SnapshotTests(SimpleTestCase):
    def test_vacias(self):
        cliente = MagicMock()
        cliente.llen.return_value = 0
        snap = snapshot_colas_w2(cliente=cliente)
        self.assertTrue(snap['ok'])
        self.assertEqual(snap['mas_viejo_seg'], 0)
        for nombre in ('conversacion', 'masivo', 'media_encode'):
            self.assertEqual(snap['colas'][nombre]['profundidad'], 0)
            self.assertEqual(snap['colas'][nombre]['edad_seg'], 0)

    def test_mas_viejo_con_timestamp(self):
        ahora = time.time()
        sobre = json.dumps({'headers': {'timestamp': ahora - 120}})
        cliente = MagicMock()

        def llen(nombre):
            return 2 if nombre == 'conversacion' else 0

        def lindex(nombre, idx):
            return sobre if nombre == 'conversacion' and idx == -1 else None

        cliente.llen.side_effect = llen
        cliente.lindex.side_effect = lindex
        snap = snapshot_colas_w2(cliente=cliente)
        self.assertTrue(snap['ok'])
        self.assertEqual(snap['colas']['conversacion']['profundidad'], 2)
        self.assertAlmostEqual(snap['colas']['conversacion']['edad_seg'], 120, delta=2)
        self.assertEqual(snap['colas']['conversacion']['fuente'], 'sobre')
        self.assertAlmostEqual(snap['mas_viejo_seg'], 120, delta=2)

    def test_sin_timestamp_reporta_fuente(self):
        cliente = MagicMock()
        cliente.llen.return_value = 1
        cliente.lindex.return_value = json.dumps({'headers': {}, 'body': 'x'})
        snap = snapshot_colas_w2(cliente=cliente)
        self.assertTrue(snap['ok'])
        self.assertIsNone(snap['colas']['conversacion']['edad_seg'])
        self.assertEqual(snap['colas']['conversacion']['fuente'], 'sin_timestamp')
