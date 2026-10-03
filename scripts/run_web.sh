#!/bin/bash
# Web. Con EKI_ROLE=worker este proceso no arranca gunicorn.
set -euo pipefail
ROLE="${EKI_ROLE:-all}"
case "$ROLE" in
  web|worker|all) ;;
  *) echo "EKI_ROLE invalido: $ROLE" >&2; exit 1 ;;
esac
if [ "$ROLE" != "web" ] && [ "$ROLE" != "all" ]; then
  exec sleep infinity
fi
exec gunicorn mvp_project.wsgi:application \
  --worker-class gthread --workers 1 --threads 8 \
  --timeout 900 --graceful-timeout 60 \
  --max-requests 300 --max-requests-jitter 40 \
  --bind 0.0.0.0:8000 --log-level info --worker-tmp-dir /dev/shm
