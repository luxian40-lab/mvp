"""Un solo beat: el hook de prebuild elige Procfile.ai en la caja de IA y run_beat.sh decide por rol."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
HOOK = RAIZ / '.platform' / 'hooks' / 'prebuild' / '01_eki_procfile_role.sh'
CONFIGHOOK = RAIZ / '.platform' / 'confighooks' / 'prebuild' / '01_eki_procfile_role.sh'
RUN_BEAT = RAIZ / 'scripts' / 'run_beat.sh'
RUN_WORKER = RAIZ / 'scripts' / 'run_worker.sh'


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


class RunBeatTests(_ConBash):
    def _beat(self, **env) -> str:
        fake = self.tmp / 'bin'
        fake.mkdir(exist_ok=True)
        _ejecutable(fake, 'celery', 'echo "BEAT $*"')
        _ejecutable(fake, 'sleep', 'echo "DUERME $*"')
        return self._correr(RUN_BEAT, env, fake=fake)

    def test_web_sin_run_beat_no_corre_beat(self):
        self.assertIn('DUERME infinity', self._beat(EKI_ROLE='web'))

    def test_web_con_run_beat_corre_beat(self):
        self.assertIn('BEAT -A mvp_project beat', self._beat(EKI_ROLE='web', RUN_BEAT='1'))

    def test_all_corre_beat(self):
        self.assertIn('BEAT -A mvp_project beat', self._beat(EKI_ROLE='all'))

    def test_worker_solo_con_run_beat(self):
        self.assertIn('DUERME infinity', self._beat(EKI_ROLE='worker'))
        self.assertIn('BEAT -A mvp_project beat', self._beat(EKI_ROLE='worker', RUN_BEAT='1'))

    def test_caja_ia_nunca_corre_beat(self):
        salida = self._beat(EKI_EB_ROLE='ai_workers', RUN_BEAT='1')
        self.assertIn('DUERME infinity', salida)
        self.assertNotIn('BEAT', salida)
        self.assertIn('DUERME infinity', self._beat(EKI_EB_ROLE='ai_workers'))


class RunWorkerTests(_ConBash):
    def _worker(self, **env) -> str:
        fake = self.tmp / 'bin'
        fake.mkdir(exist_ok=True)
        _ejecutable(fake, 'celery', 'echo "WORKER $*"')
        _ejecutable(fake, 'sleep', 'echo "DUERME $*"')
        return self._correr(RUN_WORKER, env, fake=fake)

    def test_sin_rol_de_eb_corre_el_worker_general(self):
        self.assertIn('WORKER -A mvp_project worker', self._worker())
        self.assertIn('WORKER -A mvp_project worker', self._worker(EKI_EB_ROLE='web', EKI_ROLE='web'))

    def test_caja_ia_nunca_corre_el_worker_general(self):
        salida = self._worker(EKI_EB_ROLE='ai_workers')
        self.assertIn('DUERME infinity', salida)
        self.assertNotIn('WORKER', salida)


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


class ConfighookProcfileTests(_ConBash):
    """eb setenv corre .platform/confighooks/, no .platform/hooks/: el rol se aplica igual."""

    def _setenv(self, rol_get_config: str) -> bytes:
        destino = self.tmp / '.platform' / 'hooks' / 'prebuild'
        destino.mkdir(parents=True)
        shutil.copy(HOOK, destino / HOOK.name)
        (self.tmp / 'Procfile').write_bytes(b'beat: completo\r\n')
        (self.tmp / 'Procfile.ai').write_bytes(b'# caja IA\r\nworker_rag: ia\r\n')
        get_config = _ejecutable(
            self.tmp, 'get-config',
            f'[ "$1 $2 $3" = "environment -k EKI_EB_ROLE" ] && printf "%s" "{rol_get_config}"',
        )
        self._correr(CONFIGHOOK, {'EKI_GET_CONFIG': _posix(get_config)})
        return (self.tmp / 'Procfile').read_bytes()

    def test_setenv_en_caja_ia_conserva_procfile_ai_sin_cr(self):
        self.assertEqual(self._setenv('ai_workers'), b'worker_rag: ia\n')

    def test_setenv_en_web_deja_el_procfile_completo(self):
        self.assertEqual(self._setenv('web'), b'beat: completo\n')
