#!/usr/bin/env python3
import json
import os
import subprocess
import sys

GET_CONFIG = '/opt/elasticbeanstalk/bin/get-config'
PYTHON = '/var/app/venv/staging-LQM1lest/bin/python'
APP_DIR = '/var/app/current'


def main():
    raw = subprocess.check_output([GET_CONFIG, 'environment'])
    env = json.loads(raw)
    os.environ.update({k: str(v) for k, v in env.items()})
    os.chdir(APP_DIR)
    cmd = [PYTHON, 'manage.py', *sys.argv[1:]]
    sys.exit(subprocess.call(cmd))


if __name__ == '__main__':
    main()
