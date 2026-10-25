"""Freno de complejidad. Los números del baseline solo pueden bajar.

Mide el código de producto (core, portal, aprende, studio, formulario), sin
tests ni migraciones. No importa Django. Reglas: docs/PLAN_MODULARIDAD_EKI.md §3.

    python scripts/ratchet_complejidad.py
    python scripts/ratchet_complejidad.py --archivo core/views/webhook_twilio.py
    python scripts/ratchet_complejidad.py --actualizar [--aceptar-movimiento]

--aceptar-movimiento deja entrar funciones grandes nuevas solo si el total de
líneas en funciones grandes no sube (una función que se movió de archivo).
Para la fase D, un handler grande nuevo en core/conversacion/estados/ puede sumar
su pegamento (ver `pegamento`), y ciclo_mayor solo crece con esos módulos.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASELINE = RAIZ / 'scripts' / 'complejidad_baseline.json'
APPS = ('core', 'portal', 'aprende', 'studio', 'formulario')
APPS_SUPERIORES = ('portal', 'aprende', 'studio', 'formulario')
UMBRAL_FUNCION = 150
FUNCIONES_VARIANTE = {'es_modo_twilio', 'es_solo_cursos'}
VARIANTE_PERMITIDA = 'core/lineas/'
MARCADORES = ('[MULTI_MSG]', '[MEDIA:', '[DELAY:', '[SEND_TEMPLATE:', '[SEP]')
MODULOS_ESTADOS = 'core.conversacion.estados.'
ARCHIVOS_ESTADOS = 'core/conversacion/estados/'

POR_ARCHIVO = (
    'excepts_amplios',
    'variante_linea',
    'parser_sep',
    'marcadores_texto',
    'parches_runtime',
    'core_importa_apps_superiores',
)
ESCALARES = ('lineas_en_funciones_grandes', 'ciclo_mayor', 'archivos_sueltos_core')


def es_producto(rel: str) -> bool:
    partes = rel.split('/')
    if partes[0] not in APPS or not rel.endswith('.py'):
        return False
    if 'migrations' in partes:
        return False
    if 'test' in partes[-1]:
        return False
    return not any(p.startswith('tests') for p in partes[:-1])


def archivos_producto(raiz: Path) -> list[str]:
    salida = []
    for app in APPS:
        base = raiz / app
        if not base.is_dir():
            continue
        for ruta in base.rglob('*.py'):
            rel = ruta.relative_to(raiz).as_posix()
            if es_producto(rel):
                salida.append(rel)
    return sorted(salida)


def nombre_modulo(rel: str) -> str:
    return rel[:-3].replace('/', '.').removesuffix('.__init__')


def funciones(arbol: ast.AST) -> dict[str, int]:
    salida: dict[str, int] = {}

    def visitar(nodo: ast.AST, prefijo: str) -> None:
        for hijo in ast.iter_child_nodes(nodo):
            if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nombre = f'{prefijo}{hijo.name}'
                if not isinstance(hijo, ast.ClassDef):
                    clave, n = nombre, 2
                    while clave in salida:
                        clave, n = f'{nombre}#{n}', n + 1
                    salida[clave] = hijo.end_lineno - hijo.lineno + 1
                visitar(hijo, nombre + '.')
            else:
                visitar(hijo, prefijo)

    visitar(arbol, '')
    return salida


def _es_amplio(tipo: ast.AST | None) -> bool:
    if tipo is None:
        return True
    if isinstance(tipo, ast.Name):
        return tipo.id in ('Exception', 'BaseException')
    if isinstance(tipo, ast.Tuple):
        return any(_es_amplio(e) for e in tipo.elts)
    return False


def _nombres_importados(arbol: ast.AST) -> set[str]:
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                nombres.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(nodo, ast.ImportFrom):
            for alias in nodo.names:
                nombres.add(alias.asname or alias.name)
    return nombres


def _base_relativa(modulo_actual: str, es_paquete: bool, nodo: ast.ImportFrom) -> str:
    if not nodo.level:
        return nodo.module or ''
    partes = modulo_actual.split('.')
    paquete = partes if es_paquete else partes[:-1]
    paquete = paquete[: len(paquete) - (nodo.level - 1)]
    return '.'.join(paquete + ([nodo.module] if nodo.module else []))


def medir_archivo(rel: str, arbol: ast.AST) -> dict:
    importados = _nombres_importados(arbol)
    datos = {k: 0 for k in POR_ARCHIVO}
    destinos_superiores = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ExceptHandler) and _es_amplio(nodo.type):
            datos['excepts_amplios'] += 1
        elif isinstance(nodo, ast.Call):
            func = nodo.func
            nombre = func.id if isinstance(func, ast.Name) else getattr(func, 'attr', '')
            if nombre in FUNCIONES_VARIANTE and not rel.startswith(VARIANTE_PERMITIDA):
                datos['variante_linea'] += 1
            if (
                nombre == 'split'
                and isinstance(func, ast.Attribute)
                and nodo.args
                and isinstance(nodo.args[0], ast.Constant)
                and nodo.args[0].value == '[SEP]'
            ):
                datos['parser_sep'] += 1
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            if any(m in nodo.value for m in MARCADORES):
                datos['marcadores_texto'] += 1
        elif isinstance(nodo, ast.Assign):
            for objetivo in nodo.targets:
                if (
                    isinstance(objetivo, ast.Attribute)
                    and isinstance(objetivo.value, ast.Name)
                    and objetivo.value.id in importados
                ):
                    datos['parches_runtime'] += 1
        elif rel.startswith('core/') and isinstance(nodo, (ast.Import, ast.ImportFrom)):
            if isinstance(nodo, ast.ImportFrom):
                destinos = [nodo.module or ''] if not nodo.level else []
            else:
                destinos = [a.name for a in nodo.names]
            for destino in destinos:
                if destino.split('.')[0] in APPS_SUPERIORES:
                    destinos_superiores.add(destino)
    datos['core_importa_apps_superiores'] = len(destinos_superiores)
    return datos


def _aristas(rel: str, arbol: ast.AST, modulos: set[str]) -> set[str]:
    actual = nombre_modulo(rel)
    es_paquete = rel.endswith('__init__.py')
    salida = set()
    for nodo in ast.walk(arbol):
        candidatos: list[str] = []
        if isinstance(nodo, ast.Import):
            candidatos = [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            base = _base_relativa(actual, es_paquete, nodo)
            for alias in nodo.names:
                completo = f'{base}.{alias.name}' if base else alias.name
                candidatos.append(completo if completo in modulos else base)
        for destino in candidatos:
            while destino and destino not in modulos:
                destino = destino.rpartition('.')[0]
            if destino and destino != actual:
                salida.add(destino)
    return salida


def ciclo_mayor(grafo: dict[str, set[str]]) -> int:
    return max(1, len(miembros_ciclo_mayor(grafo)))


def miembros_ciclo_mayor(grafo: dict[str, set[str]]) -> list[str]:
    indice: dict[str, int] = {}
    bajo: dict[str, int] = {}
    pila: list[str] = []
    en_pila: set[str] = set()
    mayor: list[str] = []
    contador = 0
    for raiz in grafo:
        if raiz in indice:
            continue
        trabajo = [(raiz, iter(sorted(grafo.get(raiz, ()))))]
        indice[raiz] = bajo[raiz] = contador
        contador += 1
        pila.append(raiz)
        en_pila.add(raiz)
        while trabajo:
            nodo, hijos = trabajo[-1]
            avanzo = False
            for hijo in hijos:
                if hijo not in indice:
                    indice[hijo] = bajo[hijo] = contador
                    contador += 1
                    pila.append(hijo)
                    en_pila.add(hijo)
                    trabajo.append((hijo, iter(sorted(grafo.get(hijo, ())))))
                    avanzo = True
                    break
                if hijo in en_pila:
                    bajo[nodo] = min(bajo[nodo], indice[hijo])
            if avanzo:
                continue
            trabajo.pop()
            if trabajo:
                padre = trabajo[-1][0]
                bajo[padre] = min(bajo[padre], bajo[nodo])
            if bajo[nodo] == indice[nodo]:
                componente = []
                while True:
                    w = pila.pop()
                    en_pila.discard(w)
                    componente.append(w)
                    if w == nodo:
                        break
                if len(componente) > len(mayor):
                    mayor = componente
    return sorted(mayor) if len(mayor) > 1 else []


def _lee_del_parametro(valor: ast.AST, parametro: str) -> bool:
    if isinstance(valor, ast.Subscript):
        valor = valor.value
    return (
        isinstance(valor, ast.Attribute)
        and isinstance(valor.value, ast.Name)
        and valor.value.id == parametro
    )


def pegamento(func: ast.FunctionDef) -> int:
    """Líneas que suma mover una rama a un handler: def, return y `x = contexto.y` iniciales."""
    if not func.args.args:
        return 0
    parametro = func.args.args[0].arg
    encabezado = 0
    for sentencia in func.body:
        if not (
            isinstance(sentencia, ast.Assign)
            and len(sentencia.targets) == 1
            and isinstance(sentencia.targets[0], ast.Name)
            and _lee_del_parametro(sentencia.value, parametro)
        ):
            break
        encabezado += 1
    if not encabezado:
        return 0
    ultima = func.body[-1]
    cierre = (
        isinstance(ultima, ast.Return)
        and isinstance(ultima.value, ast.Call)
        and isinstance(ultima.value.func, ast.Name)
        and ultima.value.func.id == 'Respuesta'
    )
    return 1 + encabezado + int(cierre)


def _parsear(raiz: Path, rel: str) -> ast.AST | None:
    try:
        return ast.parse((raiz / rel).read_text(encoding='utf-8-sig', errors='replace'))
    except SyntaxError:
        return None


def medir(raiz: Path = RAIZ) -> dict:
    rels = archivos_producto(raiz)
    modulos = {nombre_modulo(r) for r in rels}
    resultado: dict = {
        'umbral_funcion': UMBRAL_FUNCION,
        'funciones_grandes': {},
        **{k: {} for k in POR_ARCHIVO},
        'no_parseables': [],
        'pegamento_estados': {},
    }
    grafo: dict[str, set[str]] = {}
    for rel in rels:
        arbol = _parsear(raiz, rel)
        if arbol is None:
            resultado['no_parseables'].append(rel)
            continue
        for nombre, lineas in funciones(arbol).items():
            if lineas > UMBRAL_FUNCION:
                resultado['funciones_grandes'][f'{rel}::{nombre}'] = lineas
        if rel.startswith(ARCHIVOS_ESTADOS):
            for nodo in arbol.body:
                if isinstance(nodo, ast.FunctionDef) and pegamento(nodo):
                    resultado['pegamento_estados'][f'{rel}::{nodo.name}'] = pegamento(nodo)
        for clave, valor in medir_archivo(rel, arbol).items():
            if valor:
                resultado[clave][rel] = valor
        grafo[nombre_modulo(rel)] = _aristas(rel, arbol, modulos)
    resultado['lineas_en_funciones_grandes'] = sum(resultado['funciones_grandes'].values())
    resultado['ciclo_mayor_miembros'] = miembros_ciclo_mayor(grafo)
    resultado['ciclo_mayor'] = max(1, len(resultado['ciclo_mayor_miembros']))
    resultado['archivos_sueltos_core'] = sum(1 for r in rels if r.count('/') == 1 and r.startswith('core/'))
    return resultado


def totales(datos: dict) -> dict[str, int]:
    salida = {k: sum(datos.get(k, {}).values()) for k in POR_ARCHIVO}
    salida.update({k: int(datos.get(k, 0)) for k in ESCALARES})
    salida['funciones_grandes'] = len(datos.get('funciones_grandes', {}))
    return salida


def _fuera_de_estados(miembros: list[str]) -> list[str]:
    return [m for m in miembros if not m.startswith(MODULOS_ESTADOS)]


def _ciclo_crece_solo_por_estados(base: dict, actual: dict) -> bool:
    """Una rama de estado movida del cuerpo hereda los imports del cuerpo y entra al ciclo."""
    miembros_base = base.get('ciclo_mayor_miembros')
    if miembros_base is None:
        fuera_base = int(base.get('ciclo_mayor', 0))
        nuevos_fuera: list[str] = []
    else:
        fuera_base = len(_fuera_de_estados(miembros_base))
        nuevos_fuera = _fuera_de_estados(sorted(set(actual.get('ciclo_mayor_miembros', [])) - set(miembros_base)))
    return not nuevos_fuera and len(_fuera_de_estados(actual.get('ciclo_mayor_miembros', []))) <= fuera_base


def comparar(base: dict, actual: dict, *, aceptar_movimiento: bool = False) -> list[str]:
    problemas = []
    base_f = base.get('funciones_grandes', {})
    for clave, lineas in sorted(actual.get('funciones_grandes', {}).items()):
        if clave in base_f:
            if lineas > base_f[clave]:
                problemas.append(f'función creció: {clave} {base_f[clave]} -> {lineas} líneas')
        elif not aceptar_movimiento:
            problemas.append(f'función nueva de más de {UMBRAL_FUNCION} líneas: {clave} ({lineas})')
    t_base, t_actual = totales(base), totales(actual)
    if aceptar_movimiento:
        pegamento = actual.get('pegamento_estados', {})
        t_base['lineas_en_funciones_grandes'] += sum(
            pegamento.get(c, 0) for c in actual.get('funciones_grandes', {}) if c not in base_f
        )
    for clave in (*POR_ARCHIVO, *ESCALARES):
        if t_actual[clave] > t_base[clave]:
            if clave == 'ciclo_mayor' and aceptar_movimiento and _ciclo_crece_solo_por_estados(base, actual):
                continue
            problemas.append(f'{clave} subió: {t_base[clave]} -> {t_actual[clave]}')
    nuevos_rotos = sorted(set(actual.get('no_parseables', [])) - set(base.get('no_parseables', [])))
    if nuevos_rotos:
        problemas.append(f"archivos que no parsean: {', '.join(nuevos_rotos)}")
    return problemas


def comparar_archivo(base: dict, raiz: Path, rel: str) -> list[str]:
    """Para el hook: solo lo que cambió en un archivo. No calcula el ciclo."""
    if not es_producto(rel):
        return []
    arbol = _parsear(raiz, rel)
    if arbol is None:
        return [] if rel in base.get('no_parseables', []) else [f'{rel} no parsea']
    problemas = []
    base_f = base.get('funciones_grandes', {})
    for nombre, lineas in sorted(funciones(arbol).items()):
        clave = f'{rel}::{nombre}'
        if clave in base_f and lineas > base_f[clave]:
            problemas.append(f'función creció: {clave} {base_f[clave]} -> {lineas} líneas')
        elif clave not in base_f and lineas > UMBRAL_FUNCION:
            problemas.append(f'función nueva de más de {UMBRAL_FUNCION} líneas: {clave} ({lineas})')
    for clave, valor in medir_archivo(rel, arbol).items():
        antes = base.get(clave, {}).get(rel, 0)
        if valor > antes:
            problemas.append(f'{clave} en {rel}: {antes} -> {valor}')
    return problemas


def leer_baseline(ruta: Path = BASELINE) -> dict:
    return json.loads(ruta.read_text(encoding='utf-8'))


def escribir_baseline(datos: dict, ruta: Path = BASELINE) -> None:
    salida = dict(datos)
    salida['totales'] = totales(datos)
    ruta.write_text(json.dumps(salida, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')


def _tabla(base: dict, actual: dict) -> str:
    t_base, t_actual = totales(base), totales(actual)
    filas = [f"{'métrica':32} {'baseline':>9} {'actual':>9}"]
    for clave in ('funciones_grandes', *ESCALARES, *POR_ARCHIVO):
        marca = '  <- subió' if t_actual[clave] > t_base[clave] else ''
        filas.append(f'{clave:32} {t_base[clave]:>9} {t_actual[clave]:>9}{marca}')
    return '\n'.join(filas)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--archivo')
    parser.add_argument('--actualizar', action='store_true')
    parser.add_argument('--aceptar-movimiento', action='store_true')
    args = parser.parse_args(argv)

    if args.archivo:
        if not BASELINE.exists():
            return 0
        rel = Path(args.archivo).resolve().relative_to(RAIZ).as_posix()
        problemas = comparar_archivo(leer_baseline(), RAIZ, rel)
        for p in problemas:
            print(p)
        return 1 if problemas else 0

    actual = medir(RAIZ)
    if args.actualizar and not BASELINE.exists():
        escribir_baseline(actual)
        print('baseline creado')
        print(_tabla(actual, actual))
        return 0
    base = leer_baseline()
    problemas = comparar(base, actual, aceptar_movimiento=args.aceptar_movimiento)
    print(_tabla(base, actual))
    if problemas:
        print('\nEl código empeoró respecto al baseline:')
        for p in problemas:
            print(f'- {p}')
        if args.actualizar:
            print('\nNo se actualiza: el baseline solo baja.')
        return 1
    if args.actualizar:
        escribir_baseline(actual)
        print('\nbaseline actualizado')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
