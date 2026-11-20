"""Regresión: reto.py debe parsear e importarse (gate WA).

Un IndentationError aquí tumba todo Continuemos vía import de BARRERAS.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase


class RetoSintaxisTests(SimpleTestCase):
    def test_reto_py_parsea(self):
        path = Path(__file__).resolve().parent / 'conversacion' / 'estados' / 'reto.py'
        src = path.read_text(encoding='utf-8')
        ast.parse(src)

    def test_import_reto_y_despacho(self):
        from core.conversacion.estados import reto  # noqa: F401
        from core.conversacion.estados.despacho import BARRERAS  # noqa: F401

        self.assertTrue(callable(getattr(reto, 'manejar', None)) or hasattr(reto, 'manejar'))
