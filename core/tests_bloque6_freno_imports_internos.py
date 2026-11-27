"""H4 bloque 6.3 — guardián de imports internos prohibidos en core (AST).

Aristas que no deben aparecer (Import / ImportFrom en código de producto):

1. ``core/curso/**`` no importa:
   - ``core.lineas.principal`` (ni submódulos)
   - ``core.sandbox_menu`` (menú / ficha asesoría)
   - ``core.lineas.principal.asesores`` (cubierto por el prefijo principal)

2. ``core/conversacion/**`` (salvo archivos de test) no importa:
   - ``core.admin`` ni submódulos
   - ``core.admin_vistas`` ni submódulos

No sustituye ``scripts/ratchet_complejidad.py`` ni ``core_importa_apps_superiores`` (debe seguir en 0).
Ver ``docs/H4_FRENO_IMPORTS_INTERNOS.md`` y PLAN_MODULARIDAD § H4 punto 4.
"""
from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase

_EXENTOS_LEGADOS: frozenset[tuple[str, int]] = frozenset(
    {
        # Alta demo en curso: quitar cuando menú salga del motor (H4).
        ('core/curso/cursos_generales.py', 639),
    }
)

_ZONA_CURSO = 'core/curso'
_ZONA_CONVERSACION = 'core/conversacion'

_PROHIBIDO_CURSO = (
    'core.lineas.principal',
    'core.sandbox_menu',
)

_PROHIBIDO_CONVERSACION = (
    'core.admin',
    'core.admin_vistas',
)


def _archivos_py(raiz: Path):
    for path in sorted(raiz.rglob('*.py')):
        nombre = path.name
        if nombre.startswith('tests_') or nombre.startswith('test_'):
            continue
        yield path


def _empieza_con(modulo: str | None, prefijo: str) -> bool:
    if not modulo:
        return False
    return modulo == prefijo or modulo.startswith(prefijo + '.')


def _destinos_import(nodo: ast.AST) -> list[tuple[int, str]]:
    salida: list[tuple[int, str]] = []
    if isinstance(nodo, ast.Import):
        for alias in nodo.names:
            salida.append((nodo.lineno, alias.name))
    elif isinstance(nodo, ast.ImportFrom) and nodo.module:
        salida.append((nodo.lineno, nodo.module))
    return salida


def _violacion_curso(modulo: str) -> str | None:
    for prefijo in _PROHIBIDO_CURSO:
        if _empieza_con(modulo, prefijo):
            return prefijo
    return None


def _violacion_conversacion(modulo: str) -> str | None:
    for prefijo in _PROHIBIDO_CONVERSACION:
        if _empieza_con(modulo, prefijo):
            return prefijo
    return None


class Bloque6FrenoImportsInternosTests(SimpleTestCase):
    def test_detector_reconoce_import_prohibido_curso(self):
        tree = ast.parse('from core.lineas.principal.foo import bar\n')
        destinos = []
        for n in ast.walk(tree):
            destinos.extend(_destinos_import(n))
        self.assertEqual(_violacion_curso(destinos[0][1]), 'core.lineas.principal')

    def test_sin_aristas_prohibidas_internas(self):
        base = Path(__file__).resolve().parent.parent
        violaciones: list[str] = []
        for rel_raiz, chequeo in (
            (_ZONA_CURSO, _violacion_curso),
            (_ZONA_CONVERSACION, _violacion_conversacion),
        ):
            raiz = base / rel_raiz
            if not raiz.is_dir():
                continue
            for path in _archivos_py(raiz):
                rel_path = path.relative_to(base).as_posix()
                try:
                    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
                except SyntaxError as err:
                    violaciones.append(f'{rel_path}: SyntaxError {err}')
                    continue
                for nodo in ast.walk(tree):
                    for lineno, modulo in _destinos_import(nodo):
                        if (rel_path, lineno) in _EXENTOS_LEGADOS:
                            continue
                        regla = chequeo(modulo)
                        if regla:
                            violaciones.append(
                                f'{rel_path}:{lineno} importa {modulo!r} (prohibido: {regla})'
                            )
        if violaciones:
            self.fail(
                'Imports internos prohibidos (H4 bloque 6.3):\n' + '\n'.join(sorted(violaciones))
            )