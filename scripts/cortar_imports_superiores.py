"""Fase H3: core deja de importar portal, aprende, studio y formulario.

Esas apps registran los nombres en core.puentes al cargarse.
"""
from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

APPS = ('portal', 'aprende', 'studio', 'formulario')
RAIZ = Path(__file__).resolve().parent.parent


def sitios() -> dict[str, set[str]]:
    por_modulo: dict[str, set[str]] = defaultdict(set)
    for path in (RAIZ / 'core').rglob('*.py'):
        if 'test' in path.name or 'migrations' in path.parts:
            continue
        texto = path.read_text(encoding='utf-8')
        try:
            arbol = ast.parse(texto)
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ImportFrom) or not nodo.module:
                continue
            if nodo.module.split('.')[0] not in APPS:
                continue
            for alias in nodo.names:
                por_modulo[nodo.module].add(alias.name)
    return por_modulo


def reescribir() -> int:
    patron = re.compile(
        r'^(\s*)from (?:portal|aprende|studio|formulario)\.\S+ import (.+)$'
    )
    n = 0
    for path in (RAIZ / 'core').rglob('*.py'):
        if 'test' in path.name or 'migrations' in path.parts:
            continue
        lineas = path.read_text(encoding='utf-8').splitlines(keepends=True)
        cambio = False
        nuevas = []
        for linea in lineas:
            m = patron.match(linea)
            if not m:
                nuevas.append(linea)
                continue
            indent, nombres = m.group(1), m.group(2)
            nuevas.append(f'{indent}from core.puentes import {nombres}')
            if not linea.endswith('\n') and linea.endswith('\r'):
                pass
            if not nuevas[-1].endswith('\n'):
                nuevas[-1] += '\n' if linea.endswith('\n') else ''
            cambio = True
            n += 1
        if cambio:
            path.write_text(''.join(nuevas), encoding='utf-8')
    return n


def escribir_registros(por_modulo: dict[str, set[str]]) -> None:
    por_app: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for modulo, nombres in sorted(por_modulo.items()):
        app = modulo.split('.')[0]
        for nombre in sorted(nombres):
            por_app[app].append((modulo, nombre))
    for app, pares in por_app.items():
        lineas = [
            '"""Registra en core lo que antes core importaba de esta app. Fase H3."""',
            'from core.puentes import registrar',
            '',
        ]
        for modulo, nombre in pares:
            lineas.append(f'from {modulo} import {nombre} as _{nombre}')
            lineas.append(f"registrar('{nombre}', _{nombre})")
        ruta = RAIZ / app / 'registro_core.py'
        ruta.write_text('\n'.join(lineas) + '\n', encoding='utf-8')
        apps = RAIZ / app / 'apps.py'
        texto = apps.read_text(encoding='utf-8')
        marca = f'import {app}.registro_core  # noqa: F401  fase H3'
        if marca not in texto:
            apps.write_text(texto.rstrip() + f'\n\n{marca}\n', encoding='utf-8')
        print(app, len(pares))


if __name__ == '__main__':
    datos = sitios()
    print('imports', reescribir())
    escribir_registros(datos)
