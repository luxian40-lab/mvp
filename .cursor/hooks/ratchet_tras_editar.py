"""postToolUse: tras editar un .py de producto, corre el freno de complejidad sobre ese archivo.

No bloquea: le devuelve al agente las regresiones para que las corrija en el mismo bloque.
"""
from __future__ import annotations

import subprocess
import sys

from _comun import RAIZ, leer_entrada, responder, ruta_editada

SCRIPT = RAIZ / 'scripts' / 'ratchet_complejidad.py'


def main() -> None:
    rel = ruta_editada(leer_entrada())
    if not rel or not rel.endswith('.py') or not SCRIPT.exists() or not (RAIZ / rel).exists():
        responder({})
        return
    try:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), '--archivo', rel],
            cwd=RAIZ, capture_output=True, text=True, encoding='utf-8', timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        responder({})
        return
    if proc.returncode == 0:
        responder({})
        return
    detalle = (proc.stdout or proc.stderr).strip()
    responder({
        'additional_context': (
            f'El freno de complejidad marca regresiones en {rel}:\n{detalle}\n'
            'El baseline solo baja (scripts/complejidad_baseline.json). Corrige antes de cerrar el bloque: '
            'parte la función, usa core/lineas en vez de es_modo_twilio, captura excepciones concretas. '
            'No edites el baseline a mano.'
        ),
    })


if __name__ == '__main__':
    main()
