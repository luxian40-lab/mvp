#!/usr/bin/env python
"""
Smoke Nat + Celery (pre-deploy / post-deploy).

Local (sin Redis):
  python scripts/smoke_nat_celery.py

Prod vía EB SSH (worker vivo + tarea registrada):
  python scripts/smoke_nat_celery.py --remote eki-prod-final
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _setup_django() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
    import django

    django.setup()
    import core.tasks  # noqa: F401 — registra tareas en el app Celery


def _fail(msg: str) -> None:
    print(f'QA_FAIL smoke_nat_celery: {msg}')
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print(f'  OK  {msg}')


def check_task_registered() -> None:
    from mvp_project.celery import app

    name = 'core.tasks.procesar_bot_comercial_webhook_async'
    if name not in app.tasks:
        _fail(f'tarea no registrada en Celery app: {name}')
    _ok(f'tarea registrada: {name}')


def check_settings_flags() -> None:
    from django.conf import settings

    if not hasattr(settings, 'NAT_WEBHOOK_CELERY_ASYNC'):
        _fail('falta NAT_WEBHOOK_CELERY_ASYNC en settings')
    _ok(f'NAT_WEBHOOK_CELERY_ASYNC={getattr(settings, "NAT_WEBHOOK_CELERY_ASYNC", None)}')
    broker = (getattr(settings, 'CELERY_BROKER_URL', None) or '').strip()
    if not broker:
        _fail('CELERY_BROKER_URL vacío')
    _ok(f'broker configurado ({broker[:28]}…)')


def check_enqueue_helper() -> None:
    from unittest.mock import patch

    from django.test.utils import override_settings

    from core.views import _encolar_bot_comercial_si_async

    post = {'MessageSid': 'SMsmoke1', 'Body': 'hola', 'From': 'whatsapp:+573001112233'}
    with override_settings(NAT_WEBHOOK_CELERY_ASYNC=False):
        if _encolar_bot_comercial_si_async(post):
            _fail('debería retornar False con NAT_WEBHOOK_CELERY_ASYNC=False')
    _ok('encolar respeta flag NAT_WEBHOOK_CELERY_ASYNC=False')

    with override_settings(NAT_WEBHOOK_CELERY_ASYNC=True):
        with patch('core.tasks.procesar_bot_comercial_webhook_async.delay') as mock_delay:
            if not _encolar_bot_comercial_si_async(post):
                _fail('debería encolar con flag True')
            mock_delay.assert_called_once()
    _ok('encolar llama delay() con flag True')

    with override_settings(NAT_WEBHOOK_CELERY_ASYNC=True):
        with patch('core.tasks.procesar_bot_comercial_webhook_async.delay', side_effect=ConnectionError('redis')):
            if _encolar_bot_comercial_si_async(post):
                _fail('debería fallback False si Redis falla')
    _ok('encolar fallback si Redis no responde')


def check_remote(environment: str) -> None:
    import subprocess

    # ec2-user no puede leer deployment/env; get-config exporta las vars EB.
    cmd = (
        'cd /var/app/current && '
        'export DJANGO_SETTINGS_MODULE=mvp_project.settings_production && '
        'export PYTHONPATH=/var/app/current && '
        'eval "$(/opt/elasticbeanstalk/bin/get-config environment | '
        'python3 -c \'import json,shlex,sys; '
        '[print(f"export {k}={shlex.quote(str(v))}") for k,v in json.load(sys.stdin).items()]\')" && '
        'for svc in worker worker_rag beat; do '
        'systemctl is-active --quiet "$svc.service" || { echo "INACTIVE $svc"; exit 3; }; '
        'done && '
        'VENV=$(ls -d /var/app/venv/*/bin/celery 2>/dev/null | head -1) && '
        'if [ -z "$VENV" ]; then echo NO_CELERY; exit 2; fi && '
        '"$VENV" -A mvp_project inspect ping --timeout 8 && '
        '"$VENV" -A mvp_project inspect registered --timeout 10 | grep -q procesar_bot_comercial_webhook_async'
    )
    proc = subprocess.run(
        ['eb', 'ssh', environment, '--command', cmd],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (proc.stdout or '') + (proc.stderr or '')
    if proc.returncode != 0:
        _fail(f'remoto {environment}: ping/register falló (rc={proc.returncode})\n{out[-800:]}')
    _ok(f'remoto {environment}: worker ping + tarea Nat registrada')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--remote', metavar='EB_ENV', help='Verificar worker en EB (eb ssh)')
    args = parser.parse_args()

    if args.remote:
        check_remote(args.remote)
        print('QA_PASS smoke_nat_celery (remote)')
        return

    _setup_django()
    check_task_registered()
    check_settings_flags()
    check_enqueue_helper()
    print('QA_PASS smoke_nat_celery (local)')


if __name__ == '__main__':
    main()
