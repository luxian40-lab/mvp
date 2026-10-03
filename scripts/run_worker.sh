#!/bin/bash
# Worker. Default = Procfile anterior (sin --pool; prefork implícito, -Q celery,media_encode).
# CELERY_POOL=threads añade --pool=threads. CELERY_QUEUES cambia -Q.
set -euo pipefail
ROLE="${EKI_ROLE:-all}"
case "$ROLE" in
  web|worker|all) ;;
  *) echo "EKI_ROLE invalido: $ROLE" >&2; exit 1 ;;
esac
if [ "$ROLE" != "worker" ] && [ "$ROLE" != "all" ]; then
  exec sleep infinity
fi
POOL="${CELERY_POOL:-prefork}"
case "$POOL" in
  prefork|threads) ;;
  *) echo "CELERY_POOL invalido: $POOL" >&2; exit 1 ;;
esac
CONC="${CELERY_CONCURRENCY:-1}"
case "$CONC" in
  ''|*[!0-9]*) echo "CELERY_CONCURRENCY invalido: $CONC" >&2; exit 1 ;;
esac
QUEUES="${CELERY_QUEUES:-celery,media_encode}"
POOL_ARG=()
if [ "$POOL" = "threads" ]; then
  POOL_ARG=(--pool=threads)
fi
exec celery -A mvp_project worker \
  -Q "$QUEUES" \
  -n "fast@%h" \
  --loglevel=info \
  "${POOL_ARG[@]}" \
  --concurrency="$CONC" \
  --max-tasks-per-child=150
