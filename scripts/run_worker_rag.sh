#!/bin/bash
# Indexación RAG. Concurrencia propia (RAG_WORKER_CONCURRENCY), no CELERY_CONCURRENCY.
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
CONC="${RAG_WORKER_CONCURRENCY:-1}"
case "$CONC" in
  ''|*[!0-9]*) echo "RAG_WORKER_CONCURRENCY invalido: $CONC" >&2; exit 1 ;;
esac
QUEUES="${CELERY_QUEUES_RAG:-rag_index}"
exec celery -A mvp_project worker \
  -Q "$QUEUES" \
  -n "rag@%h" \
  --loglevel=info \
  --pool="$POOL" \
  --concurrency="$CONC" \
  --max-tasks-per-child=20
