"""Extrae sentencias hermanas de una función a otra función del mismo archivo.

Copia el texto tal cual. Los nombres que el bloque lee y no asigna pasan a
parámetros, en el orden en que aparecen. Aborta si el bloque no es una
secuencia de sentencias hermanas, si deja código vivo después y además
retorna, o si alguna ruta no cubre el rango.

    python scripts/partir_bloque.py ARCHIVO FUNCION INICIO FIN NOMBRE [--dry-run]
"""
from __future__ import annotations

import argparse
import ast
import builtins
import sys
from pathlib import Path

ALCANCES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef,
            ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def _funcion(arbol: ast.AST, nombre: str) -> ast.FunctionDef:
    for nodo in getattr(arbol, 'body', []):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            return nodo
    raise SystemExit(f'no está la función {nombre}')


def _listas(nodo: ast.AST):
    for nombre in ('body', 'orelse', 'finalbody'):
        lista = getattr(nodo, nombre, None)
        if isinstance(lista, list) and lista and isinstance(lista[0], ast.stmt):
            yield lista
    for hijo in ast.iter_child_nodes(nodo):
        if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from _listas(hijo)


def _encontrar(funcion: ast.FunctionDef, inicio: int, fin: int) -> list[ast.stmt]:
    candidatos = []
    for lista in _listas(funcion):
        if not lista:
            continue
        toma = [s for s in lista if s.lineno >= inicio and s.end_lineno <= fin]
        if not toma:
            continue
        if toma[0].lineno == inicio and toma[-1].end_lineno == fin:
            candidatos.append(toma)
    if len(candidatos) != 1:
        raise SystemExit(f'el rango {inicio}-{fin} no es una sola lista de sentencias ({len(candidatos)})')
    return candidatos[0]


def _libres(stmts: list[ast.stmt]) -> list[str]:
    asignados: set[str] = set()
    vistos: list[str] = []

    def anotar(nombre: str) -> None:
        asignados.add(nombre)

    def ver_load(nombre: str, locales: set[str]) -> None:
        if nombre not in asignados and nombre not in locales and nombre not in dir(builtins) and nombre not in vistos:
            vistos.append(nombre)

    def visitar(nodo: ast.AST, locales: set[str]) -> None:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            internos = {a.arg for a in nodo.args.args}
            internos.update(a.arg for a in nodo.args.kwonlyargs)
            if nodo.args.vararg:
                internos.add(nodo.args.vararg.arg)
            for sub in ast.walk(nodo):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and sub.id not in internos:
                    ver_load(sub.id, locales)
            return
        if isinstance(nodo, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            comp = set(locales)
            for gen in nodo.generators:
                visitar(gen.iter, comp)
                visitar_store(gen.target, comp.add)
                for cond in gen.ifs:
                    visitar(cond, comp)
            if isinstance(nodo, ast.DictComp):
                visitar(nodo.key, comp)
                visitar(nodo.value, comp)
            else:
                visitar(nodo.elt, comp)
            return
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Load):
            ver_load(nodo.id, locales)
            return
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Store):
            anotar(nodo.id)
            return
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            for alias in nodo.names:
                anotar(alias.asname or alias.name.split('.')[0])
            return
        if isinstance(nodo, ast.ExceptHandler) and nodo.name:
            anotar(nodo.name)
        if isinstance(nodo, ast.Assign):
            visitar(nodo.value, locales)
            for blanco in nodo.targets:
                visitar_store(blanco, anotar)
            return
        for hijo in ast.iter_child_nodes(nodo):
            visitar(hijo, locales)

    for stmt in stmts:
        visitar(stmt, set())
    return vistos


def visitar_store(nodo: ast.AST, anotar) -> None:
    if isinstance(nodo, ast.Name):
        anotar(nodo.id)
    elif isinstance(nodo, (ast.Tuple, ast.List)):
        for elt in nodo.elts:
            visitar_store(elt, anotar)
    elif isinstance(nodo, ast.Starred):
        visitar_store(nodo.value, anotar)


def _estado(stmts: list[ast.stmt], resto: list[ast.stmt]) -> list[str]:
    """Asignaciones directas del bloque que el código de después lee antes de reasignar.

    No cuenta un nombre que solo se asigna dentro de un if: si el camino que
    sigue no pasó por ahí, devolverlo rompería. Esos nombres, si hacen falta,
    se reasignan en el código que queda.
    """
    asignados: list[str] = []

    def anotar(nodo: ast.AST) -> None:
        if isinstance(nodo, ast.Name) and nodo.id not in asignados:
            asignados.append(nodo.id)
        elif isinstance(nodo, (ast.Tuple, ast.List)):
            for elt in nodo.elts:
                anotar(elt)

    for stmt in stmts:
        if isinstance(stmt, ast.Assign):
            for blanco in stmt.targets:
                anotar(blanco)
        elif isinstance(stmt, ast.AnnAssign) and stmt.target:
            anotar(stmt.target)
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for alias in stmt.names:
                nombre = alias.asname or alias.name.split('.')[0]
                if nombre not in asignados:
                    asignados.append(nombre)
        elif isinstance(stmt, ast.For):
            anotar(stmt.target)
    leidos: set[str] = set()
    for stmt in resto:
        for nodo in ast.walk(stmt):
            if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Load):
                leidos.add(nodo.id)
    return [nombre for nombre in asignados if nombre in leidos]


def _hay_return(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        for nodo in ast.walk(stmt):
            if isinstance(nodo, ast.Return):
                return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('archivo')
    parser.add_argument('funcion')
    parser.add_argument('inicio', type=int)
    parser.add_argument('fin', type=int)
    parser.add_argument('nombre')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--con-estado', action='store_true')
    parser.add_argument('--devolver', default='', help='El bloque asigna este nombre en todos los caminos y lo devuelve.')
    args = parser.parse_args(argv)

    ruta = Path(args.archivo)
    texto = ruta.read_text(encoding='utf-8')
    lineas = texto.splitlines(keepends=True)
    arbol = ast.parse(texto)
    funcion = _funcion(arbol, args.funcion)
    stmts = _encontrar(funcion, args.inicio, args.fin)
    libres = _libres(stmts)
    if args.nombre in {n.name for n in arbol.body if isinstance(n, ast.FunctionDef)}:
        raise SystemExit(f'ya existe {args.nombre}')
    lista = None
    for candidata in _listas(funcion):
        if stmts[0] in candidata:
            lista = candidata
            break
    indice = lista.index(stmts[-1])
    if _hay_return(stmts) and not args.con_estado and indice != len(lista) - 1:
        raise SystemExit('el bloque retorna y deja sentencias después')
    estado = _estado(stmts, lista[indice + 1:]) if args.con_estado else []

    indent = lineas[stmts[0].lineno - 1][: len(lineas[stmts[0].lineno - 1]) - len(lineas[stmts[0].lineno - 1].lstrip())]
    cuerpo = ''.join(lineas[stmts[0].lineno - 1: stmts[-1].end_lineno])
    cuerpo_dedent = ''.join(
        (ln[len(indent):] if ln.startswith(indent) else ln)
        for ln in cuerpo.splitlines(keepends=True)
    )
    if args.devolver and args.devolver not in libres:
        libres.insert(0, args.devolver)
    firma = ', '.join(libres)
    helper = f'\n\ndef {args.nombre}({firma}):\n'
    if cuerpo_dedent.strip():
        helper += ''.join('    ' + ln if ln.strip() else ln for ln in cuerpo_dedent.splitlines(keepends=True))
    if not helper.endswith('\n'):
        helper += '\n'
    if args.con_estado and args.devolver:
        raise SystemExit('elige --con-estado o --devolver')
    if args.devolver:
        if _hay_return(stmts):
            raise SystemExit('--devolver no admite return dentro del bloque')
        helper += f'    return {args.devolver}\n'
        llamada = f'{indent}{args.devolver} = {args.nombre}({firma})\n'
    elif args.con_estado:
        devuelve = ', '.join(estado)
        helper += f'    return ({devuelve}{"," if len(estado) == 1 else ""})\n'
        nombres = ', '.join(estado)
        coma = ',' if len(estado) == 1 else ''
        llamada = (
            f'{indent}_salida = {args.nombre}({firma})\n'
            f'{indent}if not isinstance(_salida, tuple):\n'
            f'{indent}    return _salida\n'
            f'{indent}{nombres}{coma} = _salida\n'
        )
    else:
        llamada = f'{indent}return {args.nombre}({firma})\n'
    nuevo = ''.join(lineas[: stmts[0].lineno - 1]) + llamada + ''.join(lineas[stmts[-1].end_lineno:])
    nuevo = nuevo.rstrip() + '\n' + helper
    if args.dry_run:
        print(f'{args.nombre}({firma}) -> ({", ".join(estado)})  {stmts[0].lineno}-{stmts[-1].end_lineno}')
        return 0
    ast.parse(nuevo)
    ruta.write_text(nuevo, encoding='utf-8')
    print(f'{args.nombre}({firma})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
