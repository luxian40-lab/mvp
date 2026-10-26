"""Mueve un tramo contiguo de modelos de core/models/__init__.py a core/models/<dominio>.py.

Uso:
    python scripts/mover_modelos.py clientes TemaCampana MetaMetricaNati [--dry-run]

Copia el texto tal cual (con los comentarios que encabezan el tramo). Solo
genera los imports que el tramo lee, tomados de la cabecera de __init__ o de
submódulos ya movidos. En __init__ deja un reexport en la misma posición, así
el orden de carga de los modelos no cambia. Compara por AST antes de escribir.
Aborta si el tramo lee algo que sigue definido en __init__ o que llega por un
import a mitad de archivo.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import symtable
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / 'core' / 'models'
ORIGEN = PAQUETE / '__init__.py'
PREFIJO = 'core.models.'
COMPRENSIONES = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
FUNCIONES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
NATIVOS = set(dir(builtins)) | {'__name__', '__file__', '__doc__', '__module__', '__qualname__'}


def _ligados(stmts) -> set[str]:
    """Nombres asignados en el alcance de una función (sin entrar a alcances anidados)."""
    salida: set[str] = set()

    def visitar(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            salida.add(n.name)
            return
        if isinstance(n, (ast.Lambda, *COMPRENSIONES)):
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            salida.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                salida.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            salida.add(n.name)
        elif isinstance(n, ast.NamedExpr):
            salida.add(n.target.id)
        for h in ast.iter_child_nodes(n):
            visitar(h)

    for s in stmts:
        visitar(s)
    return salida


def _leidos(stmts) -> set[str]:
    """Nombres que el tramo puede buscar en los globales del módulo.

    En cuerpos de clase cuenta todo lo leído (una clase cae a globales aunque
    luego asigne el nombre, p. ej. `X = X`).
    """
    salida: set[str] = set()

    def libres(n, propios: frozenset):
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            raise SystemExit('global/nonlocal en el tramo')
        if isinstance(n, COMPRENSIONES):
            ligados = set(propios)
            for g in n.generators:
                libres(g.iter, frozenset(ligados))
                ligados |= {x.id for x in ast.walk(g.target) if isinstance(x, ast.Name)}
                for c in g.ifs:
                    libres(c, frozenset(ligados))
            for hijo in ([n.key, n.value] if isinstance(n, ast.DictComp) else [n.elt]):
                libres(hijo, frozenset(ligados))
            return
        if isinstance(n, FUNCIONES):
            a = n.args
            externos = list(a.defaults) + [d for d in a.kw_defaults if d is not None]
            if not isinstance(n, ast.Lambda):
                externos += list(n.decorator_list) + ([n.returns] if n.returns else [])
            todos = a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]
            externos += [x.annotation for x in todos if x.annotation]
            for d in externos:
                libres(d, propios)
            params = {x.arg for x in todos}
            cuerpo = [n.body] if isinstance(n, ast.Lambda) else n.body
            internos = params | (set() if isinstance(n, ast.Lambda) else _ligados(n.body))
            for hijo in cuerpo:
                libres(hijo, propios | internos)
            return
        if isinstance(n, ast.ClassDef):
            for d in [*n.decorator_list, *n.bases, *(k.value for k in n.keywords)]:
                libres(d, propios)
            for s in n.body:
                libres(s, propios)
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in propios:
            salida.add(n.id)
        for hijo in ast.iter_child_nodes(n):
            libres(hijo, propios)

    for s in stmts:
        libres(s, frozenset())
    return salida


def _definidos(n: ast.stmt) -> list[str]:
    if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return [n.name]
    if isinstance(n, (ast.Import, ast.ImportFrom)):
        return [(a.asname or a.name).split('.')[0] for a in n.names]
    if isinstance(n, (ast.Assign, ast.AnnAssign)):
        objetivos = n.targets if isinstance(n, ast.Assign) else [n.target]
        return [x.id for t in objetivos for x in ast.walk(t) if isinstance(x, ast.Name)]
    return []


def _globales_sin_resolver(texto: str, nombre: str) -> set[str]:
    """Globales que leen clases y funciones y que el módulo no define."""
    arbol = ast.parse(texto)
    del_modulo = {x for n in arbol.body for x in _definidos(n)}
    faltan: set[str] = set()

    def recorrer(tabla):
        for s in tabla.get_symbols():
            if s.is_referenced() and s.is_global() and s.get_name() not in del_modulo | NATIVOS:
                faltan.add(s.get_name())
        for hijo in tabla.get_children():
            recorrer(hijo)

    for hijo in symtable.symtable(texto, nombre, 'exec').get_children():
        recorrer(hijo)
    return faltan


def _linea_import(n: ast.stmt, nombres: set[str]) -> str:
    alias = [a for a in n.names if (a.asname or a.name).split('.')[0] in nombres]
    partes = [a.name + (f' as {a.asname}' if a.asname else '') for a in alias]
    if isinstance(n, ast.Import):
        return ''.join(f'import {p}\n' for p in partes)
    linea = f"from {n.module} import {', '.join(partes)}\n"
    if len(linea) <= 100:
        return linea
    return f'from {n.module} import (\n' + ''.join(f'    {p},\n' for p in partes) + ')\n'


def _reexport(dominio: str, nombres: list[str], fin: str) -> str:
    return (
        f'from {PREFIJO}{dominio} import (  # noqa: F401{fin}'
        + ''.join(f'    {x},{fin}' for x in nombres)
        + f'){fin}'
    )


def _normal(stmts) -> str:
    return ast.dump(ast.Module(body=list(stmts), type_ignores=[]), include_attributes=False)


def mover(dominio: str, desde: str, hasta: str, *, dry_run: bool = False) -> str:
    destino = PAQUETE / f'{dominio}.py'
    if destino.exists():
        raise SystemExit(f'{destino.name} ya existe')
    with ORIGEN.open(encoding='utf-8', newline='') as f:
        texto = f.read()
    fin = '\r\n' if '\r\n' in texto else '\n'
    lineas = texto.splitlines(keepends=True)
    arbol = ast.parse(texto)
    cuerpo = arbol.body
    nombres_top = [getattr(n, 'name', None) for n in cuerpo]
    if desde not in nombres_top or hasta not in nombres_top:
        raise SystemExit(f'No encuentro {desde!r} o {hasta!r} en el primer nivel')
    i, j = nombres_top.index(desde), nombres_top.index(hasta)
    if j < i:
        raise SystemExit('El tramo está al revés')
    tramo = cuerpo[i:j + 1]
    for n in tramo:
        if not isinstance(n, (ast.ClassDef, ast.FunctionDef)):
            raise SystemExit(f'Línea {n.lineno}: el tramo solo puede tener clases y funciones')
        if any(isinstance(x, ast.ImportFrom) and x.level for x in ast.walk(n)):
            raise SystemExit(f'Línea {n.lineno}: import relativo en el tramo')

    primera = min([tramo[0].lineno] + [d.lineno for d in tramo[0].decorator_list])
    k = primera - 1
    while k >= 1 and not lineas[k - 1].strip():
        k -= 1
    if k >= 1 and lineas[k - 1].startswith('#') and k > cuerpo[i - 1].end_lineno:
        while k > cuerpo[i - 1].end_lineno + 1 and lineas[k - 2].startswith('#'):
            k -= 1
        primera = k
    ultima = tramo[-1].end_lineno

    movidos = [n.name for n in tramo]
    cabecera_fin = next(n.lineno for n in cuerpo if isinstance(n, (ast.ClassDef, ast.FunctionDef)))
    origen_de: dict[str, ast.stmt] = {}
    for n in cuerpo[:i] + cuerpo[j + 1:]:
        for x in _definidos(n):
            origen_de.setdefault(x, n)

    imports: dict[int, set[str]] = {}
    problemas = []
    for nombre in sorted(_leidos(tramo) - set(movidos) - NATIVOS):
        n = origen_de.get(nombre)
        if n is None:
            continue
        if isinstance(n, ast.ImportFrom) and (n.module or '').startswith(PREFIJO) and n.lineno < primera:
            imports.setdefault(n.lineno, set()).add(nombre)
        elif isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno < cabecera_fin:
            imports.setdefault(n.lineno, set()).add(nombre)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            problemas.append(f'{nombre}: llega por un import de la línea {n.lineno}, a mitad de archivo')
        else:
            problemas.append(f'{nombre}: sigue definido en __init__ (línea {n.lineno})')
    if problemas:
        raise SystemExit('Aborta:\n  ' + '\n  '.join(problemas))

    por_linea = {n.lineno: n for n in cuerpo if isinstance(n, (ast.Import, ast.ImportFrom))}
    bloque_imports = ''.join(_linea_import(por_linea[ln], imports[ln]) for ln in sorted(imports))
    encabezado = (
        f'"""Modelos de {dominio.replace("_", " ")} (fase H1).\n\n'
        'Movidos tal cual desde core/models/__init__.py, que los reexporta:\n'
        'importar desde core.models sigue igual.\n'
        '"""\n'
    )
    codigo = ''.join(lineas[primera - 1:ultima]).replace('\r\n', '\n')
    nuevo = encabezado + bloque_imports + '\n\n' + codigo
    if not nuevo.endswith('\n'):
        nuevo += '\n'

    nuevo_arbol = ast.parse(nuevo)
    if _normal(nuevo_arbol.body[-len(tramo):]) != _normal(tramo):
        raise SystemExit('El AST del submódulo no coincide con el tramo')
    latentes = _globales_sin_resolver(texto, str(ORIGEN))
    faltan = _globales_sin_resolver(nuevo, str(destino)) - latentes
    if faltan:
        raise SystemExit(f'El submódulo no resuelve: {sorted(faltan)}')

    reexport = _reexport(dominio, movidos, fin)
    restante = ''.join(lineas[:primera - 1]) + reexport + ''.join(lineas[ultima:])
    esperado = cuerpo[:i] + ast.parse(reexport).body + cuerpo[j + 1:]
    if _normal(ast.parse(restante).body) != _normal(esperado):
        raise SystemExit('El AST de __init__ no coincide')

    resultado = (
        f'{dominio}: líneas {primera}-{ultima} ({ultima - primera + 1}), '
        f'{len(movidos)} nombres, imports {sorted(x for s in imports.values() for x in s)}'
    )
    if latentes:
        resultado += f'\n  globales sin definir ya en el original: {sorted(latentes)}'
    if dry_run:
        return resultado
    destino.write_text(nuevo, encoding='utf-8', newline='\n')
    ORIGEN.write_text(restante, encoding='utf-8', newline='')
    return resultado


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('dominio')
    p.add_argument('desde')
    p.add_argument('hasta')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args(argv)
    print(mover(a.dominio, a.desde, a.hasta, dry_run=a.dry_run))
    return 0


if __name__ == '__main__':
    sys.exit(main())
