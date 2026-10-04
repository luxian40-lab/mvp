"""Compara el junit de suite-completa con el baseline de fallos conocidos."""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mvp_project.ci_baseline import parse_baseline_lines  # noqa: E402


def nodeid_de(caso: ET.Element) -> str:
    archivo = (caso.get('file') or '').replace('\\', '/')
    classname = caso.get('classname') or ''
    nombre = caso.get('name') or ''
    modulo = archivo[:-3].replace('/', '.') if archivo.endswith('.py') else ''
    resto = ''
    if modulo and classname.startswith(modulo):
        resto = classname[len(modulo):].lstrip('.')
    elif classname.split('.')[-1][:1].isupper():
        resto = classname.split('.')[-1]
    if resto:
        return f'{archivo}::{resto}::{nombre}'.replace('\\', '/')
    return f'{archivo}::{nombre}'.replace('\\', '/')


def _primera(caso: ET.Element) -> str:
    nodo = caso.find('failure')
    if nodo is None:
        nodo = caso.find('error')
    if nodo is None:
        return ''
    texto = (nodo.get('message') or nodo.text or '').strip()
    return (texto.splitlines() or [''])[0][:300]


def clasificar(xml_texto: str, baseline_texto: str) -> dict:
    baseline = parse_baseline_lines(baseline_texto)
    raiz = ET.fromstring(xml_texto)
    fallos: list[tuple[str, str]] = []
    xfail: set[str] = set()
    xpass: set[str] = set()
    pasados: set[str] = set()
    saltados: list[tuple[str, str]] = []

    for caso in raiz.iter('testcase'):
        nid = nodeid_de(caso)
        saltado = caso.find('skipped')
        if saltado is not None:
            tipo = saltado.get('type') or ''
            mensaje = saltado.get('message') or ''
            if tipo == 'pytest.xfail':
                xfail.add(nid)
            elif 'passes unexpectedly' in mensaje:
                xpass.add(nid)
            else:
                saltados.append((nid, (mensaje.splitlines() or [''])[0][:200]))
            continue
        if caso.find('failure') is not None or caso.find('error') is not None:
            fallos.append((nid, _primera(caso)))
            continue
        pasados.add(nid)

    conocidos = [(nid, linea) for nid, linea in fallos if nid in baseline]
    conocidos += [(nid, 'xfail') for nid in sorted(xfail) if nid in baseline]
    nuevos = [(nid, linea) for nid, linea in fallos if nid not in baseline]
    ahora = sorted((baseline & pasados) | (baseline & xpass))
    return {
        'conocidos': conocidos,
        'nuevos': nuevos,
        'ahora_pasan': ahora,
        'saltados': saltados,
    }


def _render(resultado: dict) -> str:
    lineas = [
        '## suite vs baseline',
        '',
        f"- conocidos (en el baseline): {len(resultado['conocidos'])}",
        f"- nuevos (no estaban): {len(resultado['nuevos'])}",
        f"- del baseline que ahora pasan: {len(resultado['ahora_pasan'])}",
        f"- skipped: {len(resultado['saltados'])}",
        '',
        '### Fallos nuevos',
    ]
    if not resultado['nuevos']:
        lineas.append('(ninguno)')
    for nid, linea in resultado['nuevos']:
        lineas.append(f'- `{nid}`')
        if linea:
            lineas.append(f'  {linea}')
    lineas.append('')
    lineas.append('### Baseline que ahora pasa')
    if not resultado['ahora_pasan']:
        lineas.append('(ninguno)')
    for nid in resultado['ahora_pasan']:
        lineas.append(f'- `{nid}`')
    lineas.append('')
    lineas.append('### Skipped')
    if not resultado['saltados']:
        lineas.append('(ninguno)')
    for nid, razon in resultado['saltados']:
        lineas.append(f'- `{nid}` — {razon}')
    return '\n'.join(lineas) + '\n'


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    junit = Path(args[0] if args else 'pytest-junit-suite.xml')
    baseline = Path(args[1] if len(args) > 1 else ROOT / 'scripts' / 'baseline_failures_before.txt')
    if not junit.is_file():
        print(f'comparar_baseline: no está {junit}')
        return 0
    resultado = clasificar(
        junit.read_text(encoding='utf-8', errors='replace'),
        baseline.read_text(encoding='utf-8', errors='replace') if baseline.is_file() else '',
    )
    texto = _render(resultado)
    print(texto)
    print(f"::notice title=baseline nuevos::{len(resultado['nuevos'])} nuevos, "
          f"{len(resultado['conocidos'])} conocidos, "
          f"{len(resultado['ahora_pasan'])} ahora pasan, "
          f"{len(resultado['saltados'])} skipped")
    for nid, linea in resultado['nuevos']:
        print(f'::notice title=fallo nuevo::{nid} | {linea}')
    for nid, razon in resultado['saltados']:
        print(f'::notice title=skipped::{nid} | {razon}')
    for nid in resultado['ahora_pasan']:
        print(f'::notice title=baseline ahora pasa::{nid}')
    destino = os.environ.get('GITHUB_STEP_SUMMARY')
    if destino:
        Path(destino).write_text(texto, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
