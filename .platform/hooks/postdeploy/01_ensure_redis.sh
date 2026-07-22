#!/bin/bash
# Tras cada deploy: Redis local solo si no hay ElastiCache.
set +e
ENVF=/opt/elasticbeanstalk/deployment/env
if [ -f "$ENVF" ]; then
  # shellcheck disable=SC1090
  set -a; . "$ENVF" 2>/dev/null || true; set +a
fi
USE_LOCAL=1
case "${USE_LOCAL_REDIS:-1}" in
  0|false|FALSE|no|NO|off|OFF) USE_LOCAL=0 ;;
esac
BROKER="${CELERY_BROKER_URL:-${REDIS_URL:-}}"
case "$BROKER" in
  redis://127.0.0.1*|redis://localhost*|"" ) ;;
  redis://*|rediss://*) USE_LOCAL=0 ;;
esac
if [ "$USE_LOCAL" != "1" ]; then
  echo "[01_ensure_redis] Broker externo — no iniciar redis local."
  exit 0
fi
if systemctl list-unit-files 2>/dev/null | grep -q '^redis6\.service'; then
  systemctl start redis6 || true
elif systemctl list-unit-files 2>/dev/null | grep -q '^redis\.service'; then
  systemctl start redis || true
fi
