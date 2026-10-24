"""Utilidades compartidas por los hooks del proyecto. Solo librería estándar."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def leer_entrada() -> dict:
    try:
        return json.loads(sys.stdin.buffer.read().decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return {}


def responder(datos: dict) -> None:
    sys.stdout.write(json.dumps(datos))
    sys.stdout.flush()


VERBOS_EDICION = ('write', 'replace', 'edit', 'delete')


def ruta_editada(entrada: dict) -> str | None:
    """Ruta relativa a la raíz, con '/', del archivo que edita la herramienta. None si no edita."""
    herramienta = str(entrada.get('tool_name') or '').lower()
    if herramienta and not any(v in herramienta for v in VERBOS_EDICION):
        return None
    tool_input = entrada.get('tool_input') or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            tool_input = {}
    for clave in ('path', 'file_path', 'target_file', 'target_notebook'):
        valor = tool_input.get(clave) if isinstance(tool_input, dict) else None
        if valor:
            break
    else:
        valor = entrada.get('file_path')
    if not valor:
        return None
    ruta = Path(valor)
    if not ruta.is_absolute():
        ruta = RAIZ / ruta
    try:
        return ruta.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return None
