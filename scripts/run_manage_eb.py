#!/usr/bin/env python3
"""Ejecuta manage.py en EB cargando /opt/elasticbeanstalk/deployment/env (sudo)."""
import os
import subprocess
import sys

ENV_PATH = '/opt/elasticbeanstalk/deployment/env'
APP_DIR = '/var/app/current'
PYTHON = '/var/app/venv/staging-LQM1lest/bin/python'


def load_env(path: str) -> None:
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ[key] = value


def main() -> int:
    if len(sys.argv) < 2:
        print('Uso: run_manage_eb.py <comando manage.py ...>', file=sys.stderr)
        return 2
    load_env(ENV_PATH)
    os.chdir(APP_DIR)
    cmd = [PYTHON, 'manage.py', *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == '__main__':
    raise SystemExit(main())
