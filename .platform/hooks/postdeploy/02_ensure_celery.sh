#!/bin/bash
# Reinicia workers del Procfile (única cola celery) y verifica tarea Nat registrada.
# Evita duplicar worker (OOM en t3.medium). Logs → /var/log/eki-celery-check.log
set +e

LOG=/var/log/eki-celery-check.log
exec >>"$LOG" 2>&1
echo "=== $(date -Is) 02_ensure_celery ==="

ENVF=/opt/elasticbeanstalk/deployment/env
APP_DIR=/var/app/current
if [ ! -d "$APP_DIR" ]; then
  echo "skip: no $APP_DIR"
  exit 0
fi

VENV_BIN=""
for d in /var/app/venv/*/bin; do
  if [ -x "$d/celery" ]; then
    VENV_BIN="$d"
    break
  fi
done
if [ -z "$VENV_BIN" ]; then
  echo "WARN: celery binary not found"
  exit 0
fi

CELERY="$VENV_BIN/celery"
export PATH="$VENV_BIN:$PATH"
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH="/var/app/current:${PYTHONPATH:-}"
if [ -f "$ENVF" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENVF" 2>/dev/null || true
  set +a
fi
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production

# Desactivar unidades duplicadas de deploys anteriores (libera RAM)
for legacy in eki-celery-worker eki-celery-rag eki-celery-beat; do
  if systemctl list-unit-files 2>/dev/null | grep -q "^${legacy}.service"; then
    systemctl stop "$legacy" 2>/dev/null || true
    systemctl disable "$legacy" 2>/dev/null || true
    echo "stopped legacy $legacy"
  fi
done

# Procfile: worker + worker_rag + beat (EB ya los registra)
for svc in worker worker_rag beat; do
  if systemctl list-unit-files 2>/dev/null | grep -q "^${svc}.service"; then
    systemctl restart "${svc}.service" 2>/dev/null || true
    sleep 2
    if systemctl is-active --quiet "${svc}.service"; then
      echo "OK ${svc}.service active"
    else
      echo "WARN ${svc}.service not active"
      systemctl status "${svc}.service" --no-pager -l | head -20 || true
    fi
  else
    echo "WARN no ${svc}.service (Procfile)"
  fi
done

sleep 3
PING=$("$CELERY" -A mvp_project inspect ping --timeout 8 2>&1) || true
echo "ping: $PING"
if ! echo "$PING" | grep -q 'pong'; then
  echo "WARN: celery inspect ping sin pong"
fi

REG=$("$CELERY" -A mvp_project inspect registered --timeout 10 2>&1) || true
if echo "$REG" | grep -q 'procesar_bot_comercial_webhook_async'; then
  echo "OK task procesar_bot_comercial_webhook_async registered"
else
  echo "WARN task procesar_bot_comercial_webhook_async NOT in registered list"
  echo "$REG" | tail -30
fi

echo "done"
exit 0
