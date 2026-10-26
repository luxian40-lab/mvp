"""Mueve un tramo de _procesar_twilio_webhook_cuerpo a core/conversacion/estados/<modulo>.py.

Uso:
    python scripts/mover_tramo.py --desde 271 --hasta 372 --modulo intercepciones \\
        --llamada "if {mod}.manejar({ctx}) is not None:\\n    return" \\
        [--entradas a,b] [--salidas x --devuelve x] [--sin-corte] [--doc "..."] [--dry-run]

Copia el texto tal cual. Solo cambia tres cosas: los imports relativos pasan a
`core.`, cada `return` suelto pasa a `return CORTAR` (o queda suelto con
--sin-corte) y, si el tramo puede seguir de largo, termina en `return None`
(o `return EXPR` con --devuelve). Los globales de webhook_twilio que el tramo
lee se importan desde su módulo de origen. Compara por AST antes de escribir.

Las entradas salen del análisis de flujo (`flujo_definidos.py`): locales que
el tramo lee sin asignarlos antes. Aborta si alguna puede no estar asignada en
el punto de la llamada, si el cuerpo puede leer después un local que el tramo
asigna (salvo --salidas, que --devuelve entrega), o si el tramo lee un global
que los tests parchean en core.views.webhook_twilio.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flujo_definidos import lecturas  # noqa: E402
from mover_intent import _leidos, _ligados, _lineas_en_cadena, _termina  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / 'core' / 'views' / 'webhook_twilio.py'
DESTINO = RAIZ / 'core' / 'conversacion' / 'estados'
FUNCION = '_procesar_twilio_webhook_cuerpo'
CAMPOS = ('estudiante', 'msg_body', 'msg_from', 'telefono_limpio')
CAMPOS_OPCIONALES = (
    'estado_chat', 'msg_sid', 'evidencia_imagen_url', 'evidencia_imagen_type', 'texto_respuesta',
)
PARCHEADOS = {
    '_intentar_responder_envio_certificado',
    '_transcribir_audio_twilio',
    '_registrar_estado_twilio_callback',
    '_procesar_twilio_webhook_cuerpo',
    '_procesar_twilio_webhook',
}


def _absoluto(n: ast.ImportFrom) -> str:
    base = {1: 'core.views', 2: 'core'}[n.level]
    return base + (f'.{n.module}' if n.module else '')


class _Normal(ast.NodeTransformer):
    def visit_ImportFrom(self, n):
        if n.level:
            return ast.ImportFrom(module=_absoluto(n), names=n.names, level=0)
        return n

    def visit_Return(self, n):
        if isinstance(n.value, ast.Name) and n.value.id == 'CORTAR':
            return ast.Return(value=None)
        return n


def _normal(stmts) -> str:
    return ast.dump(_Normal().visit(ast.Module(body=list(stmts), type_ignores=[])), include_attributes=False)


def _imports_de_modulo(arbol: ast.Module) -> dict[str, str]:
    """Nombre global -> línea de import absoluta que lo define."""
    salida: dict[str, str] = {}
    for n in arbol.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                salida[(a.asname or a.name).split('.')[0]] = f'import {a.name}' + (f' as {a.asname}' if a.asname else '')
        elif isinstance(n, ast.ImportFrom):
            modulo = _absoluto(n) if n.level else n.module
            for a in n.names:
                salida[a.asname or a.name] = f'from {modulo} import {a.name}' + (f' as {a.asname}' if a.asname else '')
    salida['logger'] = "logger = logging.getLogger('core.views.webhook_twilio')"
    return salida


def _definidos_en_modulo(arbol: ast.Module) -> set[str]:
    nombres = set()
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            nombres.add(n.name)
        elif isinstance(n, ast.Assign):
            nombres.update(t.id for t in n.targets if isinstance(t, ast.Name))
    return nombres


def _hermanos(func: ast.FunctionDef, desde: int, hasta: int) -> list[ast.stmt]:
    """Sentencias consecutivas de una misma lista que cubren [desde, hasta]."""
    for nodo in ast.walk(func):
        for campo in ('body', 'orelse', 'finalbody'):
            lista = getattr(nodo, campo, None)
            if not isinstance(lista, list) or not lista or not isinstance(lista[0], ast.stmt):
                continue
            dentro = [s for s in lista if s.lineno >= desde and s.end_lineno <= hasta]
            if dentro and dentro[0].lineno <= desde + 10 and dentro[-1].end_lineno == hasta:
                i, j = lista.index(dentro[0]), lista.index(dentro[-1])
                if lista[i:j + 1] == dentro:
                    return dentro
    raise SystemExit(f'Las líneas {desde}-{hasta} no son sentencias completas de una misma lista')


def mover(a) -> str:
    with ORIGEN.open(encoding='utf-8', newline='') as f:
        texto = f.read()
    lineas = texto.splitlines(keepends=True)
    arbol = ast.parse(texto)
    func = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == FUNCION)
    stmts = _hermanos(func, a.desde, a.hasta)
    for linea in lineas[a.desde - 1:stmts[0].lineno - 1]:
        if linea.strip() and not linea.strip().startswith('#'):
            raise SystemExit(f'Antes de la primera sentencia hay código: {linea!r}')
    if any(isinstance(n, (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom)) for s in stmts for n in ast.walk(s)):
        raise SystemExit('global/nonlocal/yield en el tramo')
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, ast.Return) and n.value is not None:
                raise SystemExit(f'return con valor en la línea {n.lineno}')
            if isinstance(n, (ast.Break, ast.Continue)):
                padre_bucle = any(
                    isinstance(b, (ast.For, ast.While)) and b.lineno <= n.lineno <= b.end_lineno
                    for t in stmts for b in ast.walk(t)
                )
                if not padre_bucle:
                    raise SystemExit(f'break/continue fuera de un bucle del tramo en la línea {n.lineno}')

    params = {x.arg for x in func.args.args}
    ligados_func = _ligados(func.body) | params
    flujo = lecturas(func, stmts, ligados_func)
    entradas = flujo['entradas']
    if a.entradas and sorted(a.entradas.split(',')) != entradas:
        raise SystemExit(f'Entradas calculadas {entradas} distintas de --entradas {a.entradas}')
    nativos = set(dir(builtins))
    importables = _imports_de_modulo(arbol)
    definidos = _definidos_en_modulo(arbol)

    problemas, globales = [], set()
    for nombre in sorted(_leidos(stmts) - ligados_func - nativos):
        if nombre in PARCHEADOS:
            problemas.append(f'{nombre}: los tests lo parchean en core.views.webhook_twilio')
        elif nombre in importables:
            globales.add(nombre)
        elif nombre in definidos:
            problemas.append(f'{nombre}: definido en webhook_twilio; moverlo exige buscarlo en tiempo de llamada')
        else:
            problemas.append(f'{nombre}: no se sabe de dónde viene')
    if flujo['inseguras']:
        problemas.append(f"entradas que pueden no estar asignadas al empezar el tramo: {flujo['inseguras']}")
    declaradas = {x for x in a.salidas.split(',') if x}
    salidas = sorted(set(flujo['salidas']) - declaradas)
    sigue = not _termina(stmts)
    if salidas:
        problemas.append(f'el cuerpo puede leer después lo que el tramo asigna: {salidas}')
    if problemas:
        raise SystemExit('Aborta:\n  ' + '\n  '.join(problemas))

    sangria = len(lineas[stmts[0].lineno - 1]) - len(lineas[stmts[0].lineno - 1].lstrip(' '))
    quitar = sangria - 4
    cadena = _lineas_en_cadena(texto)
    cuerpo = []
    for num in range(a.desde, a.hasta + 1):
        linea = lineas[num - 1]
        if num not in cadena and linea.startswith(' ' * quitar):
            linea = linea[quitar:]
        elif num not in cadena and linea.strip():
            raise SystemExit(f'Sangría menor a la del tramo en la línea {num}')
        cuerpo.append(linea)
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, ast.ImportFrom) and n.level:
                i = n.lineno - a.desde
                viejo = ('from ' + '.' * n.level + (n.module or '')).rstrip() + ' import'
                nuevo = f'from {_absoluto(n)} import'
                if viejo not in cuerpo[i]:
                    raise SystemExit(f'No encontré {viejo!r} en la línea {n.lineno}')
                cuerpo[i] = cuerpo[i].replace(viejo, nuevo, 1)
            if isinstance(n, ast.Return) and not a.sin_corte:
                i = n.lineno - a.desde
                pre, _, post = cuerpo[i].partition('return')
                if pre.strip() or (post.strip() and not post.strip().startswith('#')):
                    raise SystemExit(f'return no está solo en su línea ({n.lineno})')
                cuerpo[i] = f'{pre}return CORTAR{post}'

    hay_returns = any(isinstance(n, ast.Return) for s in stmts for n in ast.walk(s))
    del_contexto = ['Contexto']
    if hay_returns and not a.sin_corte:
        del_contexto.insert(0, 'CORTAR')
    if not a.sin_corte and ('Respuesta' in (a.devuelve or '') or 'Respuesta' in (a.tipo or '') or (sigue and not a.devuelve)):
        del_contexto.append('Respuesta')
    cabecera_imports = {f"from core.conversacion.contexto import {', '.join(del_contexto)}"}
    otros = []
    for nombre in sorted(globales):
        linea = importables[nombre]
        if nombre == 'logger':
            otros.append(linea)
            cabecera_imports.add('import logging')
        elif nombre == 'Contexto':
            continue
        else:
            cabecera_imports.add(linea)
    stdlib = sorted(x for x in cabecera_imports if x.startswith('import '))
    terceros = sorted(x for x in cabecera_imports if x.startswith('from ') and not x.startswith('from core'))
    propios = sorted(x for x in cabecera_imports if x.startswith('from core'))
    bloques = [b for b in (stdlib, terceros, propios) if b]
    encabezado = f'"""{a.doc}"""\n'
    for b in bloques:
        encabezado += '\n' + ''.join(f'{x}\n' for x in b)
    if otros:
        encabezado += '\n' + ''.join(f'{x}\n' for x in otros)
    tipo = 'None' if a.sin_corte else ('Respuesta | None' if sigue and not a.devuelve else 'Respuesta')
    if a.devuelve:
        tipo = a.tipo or 'object'
    desempaque = []
    for e in entradas:
        if e in CAMPOS + CAMPOS_OPCIONALES:
            desempaque.append(f'    {e} = contexto.{e}\n')
        else:
            desempaque.append(f"    {e} = contexto.locales['{e}']\n")
    final = []
    if a.devuelve:
        final = [f'    return {a.devuelve}\n']
    elif sigue and not a.sin_corte:
        final = ['    return None\n']
    nuevo_texto = (
        encabezado + '\n\n'
        + f'def {a.funcion}(contexto: Contexto) -> {tipo}:\n'
        + ''.join(desempaque) + ''.join(cuerpo) + ''.join(final)
    ).replace('\r\n', '\n')

    nuevo_arbol = ast.parse(nuevo_texto)
    nueva = next(n for n in nuevo_arbol.body if isinstance(n, ast.FunctionDef))
    movido = nueva.body[len(desempaque):len(nueva.body) - len(final)]
    if _normal(movido) != _normal(stmts):
        raise SystemExit('El AST no coincide')

    argumentos = []
    for campo in CAMPOS:
        argumentos.append(campo if campo in entradas else 'None')
    for campo in CAMPOS_OPCIONALES:
        if campo in entradas:
            argumentos.append(f'{campo}={campo}')
    locales = [e for e in entradas if e not in CAMPOS + CAMPOS_OPCIONALES]
    if locales:
        argumentos.append('locales={' + ', '.join(f"'{e}': {e}" for e in locales) + '}')
    ctx = 'Contexto(' + ', '.join(argumentos) + ')'
    pegamento = [f'from core.conversacion.estados import {a.modulo}', '']
    for linea_llamada in a.llamada.replace('\\n', '\n').split('\n'):
        corta = linea_llamada.format(mod=a.modulo, ctx=ctx)
        if '{ctx}' not in linea_llamada or len(corta) + sangria <= 110:
            pegamento.append(corta)
            continue
        margen = linea_llamada[:len(linea_llamada) - len(linea_llamada.lstrip())]
        antes_ctx, despues_ctx = linea_llamada.format(mod=a.modulo, ctx='\0').split('\0')
        pegamento.append(f'{antes_ctx}Contexto(')
        pegamento += [f'{margen}    {arg},' for arg in argumentos]
        pegamento.append(f'{margen}){despues_ctx}')
    fin_linea = '\r\n' if lineas[a.desde - 1].endswith('\r\n') else '\n'
    pegamento_txt = ''.join((' ' * sangria + p).rstrip() + fin_linea for p in pegamento)
    restante = lineas[:a.desde - 1] + [pegamento_txt] + lineas[a.hasta:]
    nuevo_origen = ''.join(restante)
    ast.parse(nuevo_origen)
    destino = DESTINO / f'{a.modulo}.py'
    resumen = (
        f'{a.modulo}.{a.funcion}: líneas {a.desde}-{a.hasta} ({a.hasta - a.desde + 1}), '
        f'entradas {entradas}, globales {sorted(globales)}, sigue de largo {sigue}, '
        f'returns {sum(isinstance(n, ast.Return) for s in stmts for n in ast.walk(s))}'
    )
    if a.dry_run:
        return resumen + '\n--- pegamento ---\n' + pegamento_txt
    if destino.exists():
        raise SystemExit(f'{destino} ya existe')
    destino.write_text(nuevo_texto, encoding='utf-8', newline='\n')
    ORIGEN.write_text(nuevo_origen, encoding='utf-8', newline='')
    return resumen


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--desde', type=int, required=True)
    p.add_argument('--hasta', type=int, required=True)
    p.add_argument('--modulo', required=True)
    p.add_argument('--funcion', default='manejar')
    p.add_argument('--entradas', default='', help='opcional: confirma las entradas calculadas')
    p.add_argument('--salidas', default='', help='locales que el tramo asigna y el cuerpo puede leer después; --devuelve y la llamada los entregan')
    p.add_argument('--llamada', required=True, help='pegamento; {mod} y {ctx} se reemplazan; \\n separa líneas')
    p.add_argument('--devuelve')
    p.add_argument('--tipo')
    p.add_argument('--sin-corte', action='store_true')
    p.add_argument('--doc', default='Tramo de _procesar_twilio_webhook_cuerpo movido tal cual (fase D).')
    p.add_argument('--dry-run', action='store_true')
    print(mover(p.parse_args(argv)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
