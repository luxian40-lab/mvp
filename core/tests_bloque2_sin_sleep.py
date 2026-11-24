"""Bloque 2: guardián — sin time.sleep ejecutable en conversación, líneas y avisos."""
from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase

_ARBOLES = (
    'core/conversacion',
    'core/lineas',
    'core/avisos',
)


def _archivos_py(raiz: Path):
    for path in sorted(raiz.rglob('*.py')):
        nombre = path.name
        if nombre.startswith('tests_') or nombre.startswith('test_'):
            continue
        yield path


def _lineas_time_sleep(tree: ast.AST) -> list[int]:
    lineas: list[int] = []
    for nodo in ast.walk(tree):
        if not isinstance(nodo, ast.Call):
            continue
        func = nodo.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == 'sleep'
            and isinstance(func.value, ast.Name)
            and func.value.id == 'time'
        ):
            lineas.append(getattr(nodo, 'lineno', 0))
    return lineas


class Bloque2SinSleepGuardianTests(SimpleTestCase):
    def test_detector_reconoce_time_sleep(self):
        """Beyoncé: el guardián debe reaccionar a una llamada real."""
        tree = ast.parse('import time\ntime.sleep(0.1)\n')
        self.assertEqual(_lineas_time_sleep(tree), [2])

    def test_sin_time_sleep_en_conversacion_lineas_avisos(self):
        base = Path(__file__).resolve().parent.parent
        violaciones: list[str] = []
        for rel in _ARBOLES:
            raiz = base / rel
            if not raiz.is_dir():
                continue
            for path in _archivos_py(raiz):
                rel_path = path.relative_to(base)
                try:
                    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
                except SyntaxError as err:
                    violaciones.append(f'{rel_path}: SyntaxError {err}')
                    continue
                for lineno in _lineas_time_sleep(tree):
                    violaciones.append(f'{rel_path}:{lineno}')
        if violaciones:
            self.fail(
                'time.sleep prohibido (usar entrega_delays / Celery):\n'
                + '\n'.join(violaciones)
            )