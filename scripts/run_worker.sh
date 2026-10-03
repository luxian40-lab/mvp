#!/bin/bash
# Worker. CELERY_POOL=prefork|threads, CELERY_CONCURRENCY (default prefork, 1).
# CELERY_QUEUES default: conversacion + masivo + celery + media_encode.
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
QUEUES="${CELERY_QUEUES:-conversacion,masivo,celery,media_encode}"
exec celery -A mvp_project worker \
  -Q "$QUEUES" \
  -n "fast@%h" \
  --loglevel=info \
  --pool="$POOL" \
  --concurrency="$CONC" \
  --max-tasks-per-child=150
