#!/bin/bash
# Worker. Sin --pool (prefork implícito). -Q default: conversacion,masivo,celery,media_encode,llm,certificados.
# EKI_ROLE=web también arranca este worker: la caja de IA no lee masivo ni conversacion.
# CELERY_POOL=threads añade --pool=threads. CELERY_QUEUES cambia -Q.
set -euo pipefail
# La caja de IA (EKI_EB_ROLE=ai_workers) no tiene la config de envío: nunca corre el worker general.
if [ "${EKI_EB_ROLE:-}" = "ai_workers" ]; then
  exec sleep infinity
fi
ROLE="${EKI_ROLE:-all}"
case "$ROLE" in
  web|worker|all) ;;
  *) echo "EKI_ROLE invalido: $ROLE" >&2; exit 1 ;;
esac
if [ "$ROLE" != "worker" ] && [ "$ROLE" != "all" ] && [ "$ROLE" != "web" ]; then
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
QUEUES="${CELERY_QUEUES:-conversacion,masivo,celery,media_encode,llm,certificados}"
# Flag off: las dos cajas escuchan encode. Flag on y sin CELERY_QUEUES: solo eki-ai-workers.
if [ -z "${CELERY_QUEUES:-}" ]; then
  _solo_ai="$(printf '%s' "${EKI_MEDIA_ENCODE_SOLO_AI:-}" | tr '[:upper:]' '[:lower:]')"
  case "$_solo_ai" in
    1|true|yes|on)
      QUEUES="conversacion,masivo,celery,llm,certificados"
      ;;
  esac
fi
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
