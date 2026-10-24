"""beforeShellExecution: frena `eb deploy` con módulos sin trackear o desde la rama de escalabilidad.

Un .py sin trackear no sube en `eb deploy` y el web arranca con ImportError.
`slice/escalabilidad-base` no se despliega: se hace cherry-pick sobre el árbol de producción.
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
    return proc.stdout.strip() if proc.returncode == 0 else ''


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
    sin_trackear = [p for p in git(cwd, 'ls-files', '--others', '--exclude-standard').splitlines() if p.endswith('.py')]
    sucios = git(cwd, 'status', '--porcelain', '--untracked-files=no')

    if rama in RAMAS_PROHIBIDAS:
        responder({
            'permission': 'deny',
            'user_message': f'Deploy bloqueado: {rama} no se despliega. Cherry-pick sobre el árbol de producción en un worktree limpio.',
            'agent_message': 'Lee docs/CONTINUAR_EKI.md y la skill eki-ship: deploy desde worktree limpio con cherry-pick.',
        })
        return
    if sin_trackear:
        lista = ', '.join(sin_trackear[:10]) + (' …' if len(sin_trackear) > 10 else '')
        responder({
            'permission': 'deny',
            'user_message': f'Deploy bloqueado: hay módulos .py sin trackear ({lista}). No subirían y el web arrancaría con ImportError.',
            'agent_message': 'Agrega a git (o borra) los .py sin trackear antes de eb deploy.',
        })
        return
    aviso = ' Hay cambios sin commitear.' if sucios else ''
    responder({
        'permission': 'ask',
        'user_message': f'eb deploy desde la rama {rama or "?"}.{aviso} ¿Pasó QA y es un pedido explícito de deploy?',
        'agent_message': 'Deploy solo con pedido explícito del usuario y gates de eki-ship en verde.',
    })


if __name__ == '__main__':
    main()
