"""Mueve un bloque `if intent == 'x':` de get_response_for_intent a core/conversacion/intents/x.py.

Uso:
    python scripts/mover_intent.py saludo [--dry-run]

Copia el texto tal cual. Solo cambia dos cosas: los imports relativos pasan a
`core.` y los globales de response_templates que el bloque lee se importan al
inicio del handler (en tiempo de llamada, así los patch() siguen funcionando).
Compara por AST antes de escribir. Aborta si el bloque lee un nombre que otro
bloque o el preámbulo asignan, o si puede seguir de largo.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import io
import sys
import tokenize
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / 'core' / 'response_templates.py'
DESTINO = RAIZ / 'core' / 'conversacion' / 'intents'
FUNCION = 'get_response_for_intent'
PARAMETROS = ('intent', 'nombre_usuario', 'kwargs')
ALCANCES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef,
            ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def _globales(arbol: ast.Module) -> set[str]:
    nombres: set[str] = set()

    def visitar(stmts):
        for n in stmts:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nombres.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    nombres.add((a.asname or a.name).split('.')[0])
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                objetivos = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in objetivos:
                    nombres.update(x.id for x in ast.walk(t) if isinstance(x, ast.Name))
            elif isinstance(n, (ast.If, ast.Try)):
                visitar(n.body)
                visitar(getattr(n, 'orelse', []))
                for h in getattr(n, 'handlers', []):
                    visitar(h.body)
                visitar(getattr(n, 'finalbody', []))

    visitar(arbol.body)
    return nombres


def _ligados(stmts) -> set[str]:
    """Nombres asignados en el alcance de la función (sin entrar a funciones ni comprensiones)."""
    salida: set[str] = set()

    def visitar(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            salida.add(n.name)
            return
        if isinstance(n, ALCANCES):
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
    """Nombres leídos; dentro de lambdas, funciones y comprensiones, solo los libres."""
    salida: set[str] = set()

    def libres(n, propios: set[str]):
        if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            ligados = set(propios)
            for g in n.generators:
                libres(g.iter, ligados)
                ligados |= {x.id for x in ast.walk(g.target) if isinstance(x, ast.Name)}
                for c in g.ifs:
                    libres(c, ligados)
            for hijo in ([n.key, n.value] if isinstance(n, ast.DictComp) else [n.elt]):
                libres(hijo, ligados)
            return
        if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            for d in a.defaults + [d for d in a.kw_defaults if d is not None]:
                libres(d, propios)
            params = {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
            params |= {x.arg for x in (a.vararg, a.kwarg) if x}
            cuerpo = [n.body] if isinstance(n, ast.Lambda) else n.body
            internos = params | (set() if isinstance(n, ast.Lambda) else _ligados(n.body))
            for hijo in cuerpo:
                libres(hijo, propios | internos)
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in propios:
            salida.add(n.id)
        for hijo in ast.iter_child_nodes(n):
            libres(hijo, propios)

    for s in stmts:
        libres(s, set())
    return salida


def _termina(stmts) -> bool:
    if not stmts:
        return False
    u = stmts[-1]
    if isinstance(u, (ast.Return, ast.Raise)):
        return True
    if isinstance(u, ast.If):
        return _termina(u.body) and _termina(u.orelse)
    if isinstance(u, ast.Try):
        if _termina(u.finalbody):
            return True
        normal = _termina(u.orelse) if u.orelse else _termina(u.body)
        return normal and all(_termina(h.body) for h in u.handlers)
    return False


def _es_bloque(n: ast.AST, intent: str) -> bool:
    return (
        isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and isinstance(n.test.left, ast.Name)
        and n.test.left.id == 'intent'
        and len(n.test.ops) == 1
        and isinstance(n.test.ops[0], ast.Eq)
        and isinstance(n.test.comparators[0], ast.Constant)
        and n.test.comparators[0].value == intent
    )


def _lineas_en_cadena(texto: str) -> set[int]:
    """Líneas (1-based) que son continuación de un literal de varias líneas: no se reindentan."""
    dentro: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
        if tok.type == tokenize.STRING and tok.end[0] > tok.start[0]:
            dentro.update(range(tok.start[0] + 1, tok.end[0] + 1))
    return dentro


class _Absolutos(ast.NodeTransformer):
    def visit_ImportFrom(self, n):
        if n.level == 1:
            return ast.ImportFrom(module='core' + (f'.{n.module}' if n.module else ''), names=n.names, level=0)
        return n


def _normal(stmts) -> str:
    modulo = _Absolutos().visit(ast.Module(body=list(stmts), type_ignores=[]))
    return ast.dump(modulo, include_attributes=False)


def mover(intent: str, *, dry_run: bool = False) -> str:
    with ORIGEN.open(encoding='utf-8', newline='') as f:
        texto = f.read()
    lineas = texto.splitlines(keepends=True)
    arbol = ast.parse(texto)
    func = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == FUNCION)
    indice = next((i for i, n in enumerate(func.body) if _es_bloque(n, intent)), None)
    if indice is None:
        raise SystemExit(f'No hay bloque de primer nivel para {intent!r}')
    bloque = func.body[indice]
    if bloque.orelse:
        raise SystemExit('El bloque tiene else/elif')
    if not _termina(bloque.body):
        raise SystemExit('El bloque puede seguir de largo')
    if any(isinstance(n, (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom)) for n in ast.walk(bloque)):
        raise SystemExit('global/nonlocal/yield en el bloque')
    for n in ast.walk(bloque):
        if isinstance(n, ast.ImportFrom) and n.level > 1:
            raise SystemExit('import relativo de nivel 2')

    globales = _globales(arbol)
    nativos = set(dir(builtins))
    ligados_func = _ligados(func.body) | {a.arg for a in func.args.args}
    if func.args.kwarg:
        ligados_func.add(func.args.kwarg.arg)
    ligados_bloque = _ligados(bloque.body)
    leidos = _leidos(bloque.body)
    del_modulo, problemas = set(), []
    for nombre in sorted(leidos - ligados_bloque - set(PARAMETROS)):
        if nombre in ligados_func:
            problemas.append(f'{nombre}: lo asigna otro bloque o el preámbulo')
        elif nombre in globales:
            del_modulo.add(nombre)
        elif nombre not in nativos:
            problemas.append(f'{nombre}: no se sabe de dónde viene')
    if problemas:
        raise SystemExit('Aborta:\n  ' + '\n  '.join(problemas))

    primera, ultima = bloque.lineno + 1, bloque.end_lineno
    cadena = _lineas_en_cadena(texto)
    cuerpo = []
    for num in range(primera, ultima + 1):
        linea = lineas[num - 1]
        if num not in cadena and linea.startswith('    '):
            linea = linea[4:]
        cuerpo.append(linea)
    # Imports relativos -> core.
    for n in ast.walk(bloque):
        if isinstance(n, ast.ImportFrom) and n.level == 1:
            i = n.lineno - primera
            viejo = 'from . import' if not n.module else f'from .{n.module}'
            nuevo = 'from core import' if not n.module else f'from core.{n.module}'
            if viejo not in cuerpo[i]:
                raise SystemExit(f'No encontré {viejo!r} en la línea {n.lineno}')
            cuerpo[i] = cuerpo[i].replace(viejo, nuevo, 1)

    encabezado = [
        f'"""Intent `{intent}` de get_response_for_intent. Movido tal cual (fase G7)."""\n',
        '\n',
        '\n',
        'def responder(intent, nombre_usuario, kwargs):\n',
    ]
    if del_modulo:
        encabezado.append(f"    from core.response_templates import {', '.join(sorted(del_modulo))}\n")
    nuevo_texto = (''.join(encabezado) + ''.join(cuerpo)).replace('\r\n', '\n')
    if not nuevo_texto.endswith('\n'):
        nuevo_texto += '\n'

    nuevo_arbol = ast.parse(nuevo_texto)
    nuevo_cuerpo = nuevo_arbol.body[1].body
    if del_modulo:
        nuevo_cuerpo = nuevo_cuerpo[1:]
    if _normal(nuevo_cuerpo) != _normal(bloque.body):
        raise SystemExit('El AST no coincide')

    previa = func.body[indice - 1].end_lineno if indice else func.body[0].lineno
    restante = lineas[:previa] + lineas[ultima:]
    resultado = f'{intent}: líneas {previa + 1}-{ultima} ({ultima - previa}), globales {sorted(del_modulo)}'
    if dry_run:
        return resultado
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / f'{intent}.py').write_text(nuevo_texto, encoding='utf-8', newline='\n')
    ORIGEN.write_text(''.join(restante), encoding='utf-8', newline='')
    _escribir_despacho()
    return resultado


def _escribir_despacho() -> None:
    modulos = sorted(p.stem for p in DESTINO.glob('*.py') if p.stem not in ('__init__', 'despacho'))
    texto = (
        '"""Qué módulo responde cada intent de get_response_for_intent.\n\n'
        'get_response_for_intent busca aquí después del preámbulo B2B. Cada handler\n'
        'recibe (intent, nombre_usuario, kwargs) y siempre devuelve el texto.\n'
        '"""\n'
        f"from core.conversacion.intents import {', '.join(modulos)}\n\n"
        'INTENTS = {\n'
        + ''.join(f"    '{m}': {m}.responder,\n" for m in modulos)
        + '}\n'
    )
    (DESTINO / 'despacho.py').write_text(texto, encoding='utf-8', newline='\n')
    init = DESTINO / '__init__.py'
    if not init.exists():
        init.write_text('"""Intents de get_response_for_intent, uno por módulo (fase G7)."""\n', encoding='utf-8')


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('intent')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args(argv)
    print(mover(a.intent, dry_run=a.dry_run))
    return 0


if __name__ == '__main__':
    sys.exit(main())
