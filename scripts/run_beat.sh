#!/bin/bash
# Beat corre con EKI_ROLE=all. Con web o worker solo si RUN_BEAT=1. Un solo beat por broker.
set -euo pipefail
ROLE="${EKI_ROLE:-all}"
case "$ROLE" in
  web|worker|all) ;;
  *) echo "EKI_ROLE invalido: $ROLE" >&2; exit 1 ;;
esac
if [ "$ROLE" = "all" ] || [ "${RUN_BEAT:-0}" = "1" ]; then
  exec celery -A mvp_project beat --loglevel=info
fi
exec sleep infinity
