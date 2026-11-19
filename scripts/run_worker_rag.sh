#!/bin/bash
# Indexación RAG. Concurrencia propia (RAG_WORKER_CONCURRENCY), no CELERY_CONCURRENCY.
# W1: con EKI_RAG_INDEX_SOLO_AI=true, solo eki-ai-workers indexa (prod duerme).
set -euo pipefail
# Flag on + caja prod: no competir con eki-ai-workers por rag_index.
_solo_ai="$(printf '%s' "${EKI_RAG_INDEX_SOLO_AI:-}" | tr '[:upper:]' '[:lower:]')"
case "$_solo_ai" in
  1|true|yes|on)
    if [ "${EKI_EB_ROLE:-}" != "ai_workers" ]; then
      exec sleep infinity
    fi
    ;;
esac
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
POOL_ARG=()
if [ "$POOL" = "threads" ]; then
  POOL_ARG=(--pool=threads)
fi
exec celery -A mvp_project worker \
  -Q "$QUEUES" \
  -n "rag@%h" \
  --loglevel=info \
  "${POOL_ARG[@]}" \
  --concurrency="$CONC" \
  --max-tasks-per-child=20
