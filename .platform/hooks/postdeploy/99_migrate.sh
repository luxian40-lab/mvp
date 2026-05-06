#!/bin/bash
# Post-deploy: migraciones / collectstatic. No usar set -e: un fallo aquí dejaba
# el entorno en versión inconsistente (502) aunque la app ya estuviera arreglada.

set +e

echo "=================================="
echo "POST-DEPLOY HOOK: 99_migrate.sh"
echo "=================================="

RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"

echo "RUN_MIGRATIONS=$RUN_MIGRATIONS"

if [ "$RUN_MIGRATIONS" != "true" ]; then
    echo "RUN_MIGRATIONS no es 'true' — omitiendo migrate/collectstatic en post-deploy."
    exit 0
fi

echo "RUN_MIGRATIONS=true — ejecutando migrate y collectstatic..."

source /var/app/venv/*/bin/activate
cd /var/app/current || exit 0

echo "📦 migrate..."
python manage.py migrate --noinput
MIG_EC=$?

echo "📦 collectstatic..."
python manage.py collectstatic --noinput
CS_EC=$?

if [ "$MIG_EC" -ne 0 ] || [ "$CS_EC" -ne 0 ]; then
    echo "⚠️ Post-deploy: migrate exit=$MIG_EC collectstatic exit=$CS_EC (revisa logs; el deploy no se aborta)."
fi

echo "✅ Post-deploy hook terminado (exit 0 para permitir health checks)."
exit 0
