"""Un solo beat: el hook de prebuild elige Procfile.ai en la caja de IA y run_beat.sh decide por rol."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
HOOK = RAIZ / '.platform' / 'hooks' / 'prebuild' / '01_eki_procfile_role.sh'


def _bash():
    for candidato in (r'C:\Program Files\Git\bin\bash.exe', shutil.which('bash')):
        if not candidato or not os.path.exists(candidato):
            continue
        try:
            ok = subprocess.run([candidato, '-c', 'echo ok'], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if ok.stdout.strip() == 'ok':
            return candidato
    return None


def _posix(ruta) -> str:
    return str(ruta).replace('\\', '/')


def _ejecutable(carpeta: Path, nombre: str, cuerpo: str) -> Path:
    ruta = carpeta / nombre
    ruta.write_bytes(f'#!/bin/bash\n{cuerpo}\n'.encode())
    ruta.chmod(0o755)
    return ruta


class _ConBash(SimpleTestCase):
    def setUp(self):
        self.bash = _bash()
        if not self.bash:
            self.skipTest('sin bash')
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _correr(self, script: Path, env: dict, cwd: Path | None = None, fake: Path | None = None) -> str:
        base = {k: v for k, v in os.environ.items() if k not in ('EKI_ROLE', 'RUN_BEAT', 'EKI_EB_ROLE')}
        base.update(env)
        prefijo = f'export PATH="$(cd "{_posix(fake)}" && pwd):$PATH"; ' if fake else ''
        proc = subprocess.run(
            [self.bash, '-c', f'{prefijo}exec bash "{_posix(script)}"'],
            capture_output=True, text=True, timeout=30, env=base, cwd=str(cwd or self.tmp),
        )
        return proc.stdout + proc.stderr


class HookProcfileTests(_ConBash):
    def _hook(self, rol_get_config: str | None, **env) -> str:
        (self.tmp / 'Procfile').write_text('beat: completo\n', encoding='utf-8')
        (self.tmp / 'Procfile.ai').write_text('# caja IA\nworker_rag: ia\n', encoding='utf-8')
        get_config = self.tmp / 'get-config'
        if rol_get_config is None:
            _ejecutable(self.tmp, 'get-config', 'exit 1')
        else:
            _ejecutable(
                self.tmp, 'get-config',
                f'[ "$1 $2 $3" = "environment -k EKI_EB_ROLE" ] && printf "%s" "{rol_get_config}"',
            )
        self._correr(HOOK, {'EKI_GET_CONFIG': _posix(get_config), **env})
        return (self.tmp / 'Procfile').read_text(encoding='utf-8')

    def test_lee_el_rol_de_get_config_si_el_shell_no_lo_tiene(self):
        self.assertEqual(self._hook('ai_workers'), 'worker_rag: ia\n')

    def test_rol_del_shell_sigue_valiendo(self):
        self.assertEqual(self._hook(None, EKI_EB_ROLE='ai_workers'), 'worker_rag: ia\n')

    def test_sin_rol_deja_el_procfile_completo(self):
        self.assertEqual(self._hook(None), 'beat: completo\n')
        self.assertEqual(self._hook(''), 'beat: completo\n')
