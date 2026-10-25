"""Entradas, salidas y cortes de una rama de estado del cuerpo del webhook.

Uso:
    python scripts/variables_libres_rama.py ESPERANDO_CEDULA
    python scripts/variables_libres_rama.py esperando_seleccion_curso --linea 3028
    python scripts/variables_libres_rama.py --archivo core/views/webhook_twilio.py --funcion X estado

Entradas: locales del cuerpo asignados antes de la rama que la rama lee sin
reasignarlos antes de forma incondicional (conservador: sobra antes que falte).
Salidas: locales que la rama asigna y que el cuerpo lee después de terminar
toda la cadena if/elif de la rama.
Cortes: returns dentro de la rama y si la rama puede seguir de largo.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / 'core' / 'views' / 'webhook_twilio.py'
FUNCION = '_procesar_twilio_webhook_cuerpo'
COMPRENSIONES = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
FUNCIONES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _pos(n):
    return (n.lineno, n.col_offset)


def _fin(n):
    return (n.end_lineno, n.end_col_offset)


def eventos(nodos) -> list[tuple[tuple[int, int], str, str]]:
    """(posición, 'L'|'S', nombre) en orden aproximado de ejecución."""
    ev: list[tuple[tuple[int, int], str, str]] = []

    def destino(t, p):
        for hijo in ast.walk(t):
            if isinstance(hijo, ast.Name):
                ev.append((p if isinstance(hijo.ctx, ast.Store) else _pos(hijo), 'S' if isinstance(hijo.ctx, ast.Store) else 'L', hijo.id))

    def visitar(n):
        if isinstance(n, COMPRENSIONES):
            ligados = {t.id for g in n.generators for t in ast.walk(g.target) if isinstance(t, ast.Name)}
            for hijo in ast.walk(n):
                if isinstance(hijo, ast.Name) and isinstance(hijo.ctx, ast.Load) and hijo.id not in ligados:
                    ev.append((_pos(hijo), 'L', hijo.id))
            return
        if isinstance(n, FUNCIONES):
            params = {a.arg for a in n.args.args + n.args.kwonlyargs + n.args.posonlyargs}
            for hijo in ast.walk(n):
                if isinstance(hijo, ast.Name) and isinstance(hijo.ctx, ast.Load) and hijo.id not in params:
                    ev.append((_pos(n), 'L', hijo.id))
            if not isinstance(n, ast.Lambda):
                ev.append((_pos(n), 'S', n.name))
            return
        if isinstance(n, ast.Assign):
            visitar(n.value)
            for t in n.targets:
                destino(t, _fin(n.value))
            return
        if isinstance(n, ast.AnnAssign):
            if n.value is not None:
                visitar(n.value)
            destino(n.target, _fin(n))
            return
        if isinstance(n, ast.AugAssign):
            visitar(n.value)
            if isinstance(n.target, ast.Name):
                ev.append((_pos(n.target), 'L', n.target.id))
            destino(n.target, _fin(n))
            return
        if isinstance(n, (ast.For, ast.AsyncFor)):
            visitar(n.iter)
            destino(n.target, _fin(n.iter))
            for s in n.body + n.orelse:
                visitar(s)
            return
        if isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                visitar(item.context_expr)
                if item.optional_vars is not None:
                    destino(item.optional_vars, _fin(item.context_expr))
            for s in n.body:
                visitar(s)
            return
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for alias in n.names:
                ev.append((_pos(n), 'S', (alias.asname or alias.name).split('.')[0]))
            return
        if isinstance(n, ast.ExceptHandler):
            if n.type is not None:
                visitar(n.type)
            if n.name:
                ev.append((_pos(n), 'S', n.name))
            for s in n.body:
                visitar(s)
            return
        if isinstance(n, ast.NamedExpr):
            visitar(n.value)
            destino(n.target, _fin(n))
            return
        if isinstance(n, ast.Name):
            ev.append((_pos(n), 'S' if isinstance(n.ctx, ast.Store) else 'L', n.id))
            return
        for hijo in ast.iter_child_nodes(n):
            visitar(hijo)

    for nodo in nodos:
        visitar(nodo)
    return sorted(ev)


def _cuerpo(arbol: ast.Module, funcion: str) -> ast.FunctionDef:
    for nodo in arbol.body:
        if isinstance(nodo, ast.FunctionDef) and nodo.name == funcion:
            return nodo
    raise SystemExit(f'No encontré {funcion}')


def _compara_estado(test: ast.AST, estado: str) -> bool:
    for nodo in ast.walk(test):
        if isinstance(nodo, ast.Compare) and any(isinstance(op, (ast.Eq, ast.In)) for op in nodo.ops):
            for lado in [nodo.left, *nodo.comparators]:
                for hoja in ast.walk(lado):
                    if isinstance(hoja, ast.Constant) and hoja.value == estado:
                        return True
    return False


def _padres(func) -> dict:
    padres = {}
    for n in ast.walk(func):
        for hijo in ast.iter_child_nodes(n):
            padres[hijo] = n
    return padres


def _cadena(rama_if: ast.If, padres: dict) -> ast.If:
    """If más externo de la cadena if/elif que contiene la rama."""
    actual = rama_if
    while True:
        padre = padres.get(actual)
        if isinstance(padre, ast.If) and padre.orelse == [actual]:
            actual = padre
            continue
        return actual


def _retornos(stmts) -> list[ast.Return]:
    encontrados = []

    def visitar(n):
        if isinstance(n, FUNCIONES):
            return
        if isinstance(n, ast.Return):
            encontrados.append(n)
        for hijo in ast.iter_child_nodes(n):
            visitar(hijo)

    for s in stmts:
        visitar(s)
    return encontrados


def _termina(stmts) -> bool:
    if not stmts:
        return False
    ultimo = stmts[-1]
    if isinstance(ultimo, (ast.Return, ast.Raise)):
        return True
    if isinstance(ultimo, ast.If):
        return _termina(ultimo.body) and _termina(ultimo.orelse)
    if isinstance(ultimo, ast.Try):
        if _termina(ultimo.finalbody):
            return True
        normal = _termina(ultimo.orelse) if ultimo.orelse else _termina(ultimo.body)
        return normal and all(_termina(h.body) for h in ultimo.handlers)
    return False


def analizar(estado: str, linea: int | None = None, archivo: Path = ARCHIVO, funcion: str = FUNCION) -> dict:
    func = _cuerpo(ast.parse(archivo.read_text(encoding='utf-8')), funcion)
    candidatas = sorted(
        (n for n in ast.walk(func) if isinstance(n, ast.If) and _compara_estado(n.test, estado)),
        key=lambda n: n.lineno,
    )
    if not candidatas:
        raise SystemExit(f'No hay rama para {estado}')
    rama_if = next((r for r in candidatas if r.lineno == linea), None) if linea else candidatas[0]
    if rama_if is None:
        raise SystemExit(f'No hay rama de {estado} en la línea {linea}. Candidatas: {[r.lineno for r in candidatas]}')
    stmts = rama_if.body
    inicio = _pos(stmts[0])
    fin_rama = max(_fin(s) for s in stmts)
    fin_cadena = _fin(_cadena(rama_if, _padres(func)))
    nativos = set(dir(builtins))

    todos = eventos(func.body)
    params = {a.arg for a in func.args.args + func.args.kwonlyargs}
    antes = params | {nombre for p, tipo, nombre in todos if tipo == 'S' and p < inicio}
    propios = eventos(stmts)
    fijos = {
        nombre for p, tipo, nombre in eventos([s for s in stmts if not isinstance(s, (ast.If, ast.Try, ast.For, ast.While, ast.With))])
        if tipo == 'S'
    }
    entradas = set()
    vistos_fijos: set[str] = set()
    for p, tipo, nombre in propios:
        if tipo == 'S' and nombre in fijos:
            vistos_fijos.add(nombre)
        if tipo == 'L' and nombre in antes and nombre not in nativos and nombre not in vistos_fijos:
            entradas.add(nombre)

    asignados = {nombre for _, tipo, nombre in propios if tipo == 'S'}
    sigue = not _termina(stmts)
    salidas = set()
    if sigue:
        salidas = {nombre for p, tipo, nombre in todos if tipo == 'L' and p > fin_cadena and nombre in asignados}
        entradas |= {nombre for nombre in salidas if nombre not in fijos and nombre in antes}
    retornos = _retornos(stmts)
    return {
        'estado': estado,
        'if_linea': rama_if.lineno,
        'candidatas': [r.lineno for r in candidatas],
        'lineas': (inicio[0], fin_rama[0]),
        'fin_cadena': fin_cadena[0],
        'entradas': sorted(entradas),
        'salidas': sorted(salidas),
        'retornos': [(r.lineno, ast.unparse(r.value) if r.value is not None else None) for r in retornos],
        'sigue_de_largo': sigue,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('estado')
    parser.add_argument('--linea', type=int)
    parser.add_argument('--archivo', default=str(ARCHIVO))
    parser.add_argument('--funcion', default=FUNCION)
    args = parser.parse_args(argv)
    r = analizar(args.estado, args.linea, Path(args.archivo), args.funcion)
    print(f"estado: {r['estado']}  if en línea {r['if_linea']} (candidatas {r['candidatas']})")
    print(f"rama: líneas {r['lineas'][0]}-{r['lineas'][1]}  cadena hasta {r['fin_cadena']}")
    print(f"entradas: {', '.join(r['entradas']) or '-'}")
    print(f"salidas (leídas tras la cadena): {', '.join(r['salidas']) or '-'}")
    print(f"returns: {len(r['retornos'])} {sorted({v for _, v in r['retornos']}, key=str)}")
    print(f"sigue de largo: {r['sigue_de_largo']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
