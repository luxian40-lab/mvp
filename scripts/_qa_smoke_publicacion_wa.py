# -*- coding: utf-8 -*-
"""
Smoke PUNTUAL publicación WA — teléfono ops 573026480629.

Sin envíos Twilio. Sin recorrer curso completo.
Ejecutar: python scripts/_qa_smoke_publicacion_wa.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHONE = '573026480629'

if __name__ == '__main__':
    print(f'=== QA smoke publicación WA (puntual, sin envíos) | tel={PHONE} ===', flush=True)
    env = os.environ.copy()
    env.setdefault('PYTHONUTF8', '1')
    cmd = [
        sys.executable,
        os.path.join(ROOT, 'manage.py'),
        'test',
        'core.tests_qa_publicacion_wa_completo',
        '-v',
        '2',
    ]
    rc = subprocess.call(cmd, cwd=ROOT, env=env)
    if rc != 0:
        print(f'QA_FAIL smoke_publicacion_wa exit={rc}', flush=True)
        sys.exit(1)
    print('QA_PASS smoke_publicacion_wa OK (8 checks puntuales, 0 envíos WA)', flush=True)
    sys.exit(0)
