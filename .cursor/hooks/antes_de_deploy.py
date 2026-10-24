"""beforeShellExecution: frena `eb deploy` desde una carpeta sucia o desde la rama de escalabilidad.

Con `.ebignore` la CLI comprime la carpeta en disco: lo que no tiene commit sube igual y `main`
deja de ser lo que corre en producción. En un worktree limpio, lo que no tiene commit no existe
y el web arranca con ImportError. Por eso la carpeta tiene que estar limpia.
`slice/escalabilidad-base` quedó atrás de producción: desplegarla sería un rollback.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from _comun import RAIZ, leer_entrada, responder

RAMAS_PROHIBIDAS = {'slice/escalabilidad-base'}
EB_DEPLOY = re.compile(r'\beb(\.exe)?\s+deploy\b')


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ['git', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', timeout=15, check=False,
    )
    return proc.stdout.strip('\r\n') if proc.returncode == 0 else ''


def main() -> None:
    entrada = leer_entrada()
    comando = entrada.get('command') or ''
    if not EB_DEPLOY.search(comando):
        responder({})
        return
    cwd = Path(entrada.get('cwd') or RAIZ)
    if not cwd.is_dir():
        cwd = RAIZ
    rama = git(cwd, 'rev-parse', '--abbrev-ref', 'HEAD')
    sucios = [linea[3:] for linea in git(cwd, 'status', '--porcelain').splitlines() if linea.strip()]

    if rama in RAMAS_PROHIBIDAS:
        responder({
            'permission': 'deny',
            'user_message': f'Deploy bloqueado: {rama} quedó atrás de producción. Se despliega desde un worktree limpio de main.',
            'agent_message': 'Lee docs/CONTINUAR_EKI.md y la skill eki-ship: adelantar main en fast-forward y desplegar desde un worktree limpio de main.',
        })
        return
    if sucios:
        lista = ', '.join(sucios[:10]) + (' …' if len(sucios) > 10 else '')
        responder({
            'permission': 'deny',
            'user_message': f'Deploy bloqueado: la carpeta tiene cambios sin commit o archivos sin trackear ({lista}).',
            'agent_message': 'Commitea en la rama, adelanta main y despliega desde un worktree limpio de main (docs/CONTINUAR_EKI.md).',
        })
        return
    responder({
        'permission': 'ask',
        'user_message': f'eb deploy desde {rama or "?"}. ¿Pasó QA y es un pedido explícito de deploy?',
        'agent_message': 'Deploy solo con pedido explícito del usuario y gates de eki-ship en verde.',
    })


if __name__ == '__main__':
    main()
