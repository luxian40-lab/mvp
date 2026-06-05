#!/bin/bash
set -e
PID=$(pgrep -o -f gunicorn || true)
if [ -z "$PID" ]; then
  echo "ERROR: no gunicorn PID"
  exit 1
fi
sudo tr '\0' '\n' < "/proc/$PID/environ" > /tmp/ebenv.txt
set -a
. /tmp/ebenv.txt
set +a
cd /var/app/current
source /var/app/venv/staging-LQM1lest/bin/activate
python manage.py preparar_pruebas1_fedepanela --origen-nombre fedepanela --destino-nombre pruebas1 --content-sid HX33af3a0f2bb63715e03965c2bd642285
