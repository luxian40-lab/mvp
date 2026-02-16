#!/bin/bash
# Hook de postdeploy para ejecutar migraciones y collectstatic

set -e

echo "=================================="
echo "POST-DEPLOY HOOK: 99_migrate.sh"
echo "=================================="

# Obtener variable de entorno para controlar ejecución
RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"

echo "RUN_MIGRATIONS=$RUN_MIGRATIONS"

if [ "$RUN_MIGRATIONS" != "true" ]; then
    echo "❌ RUN_MIGRATIONS no está en 'true' - SKIP migraciones"
    echo "   Para ejecutar migraciones, establece RUN_MIGRATIONS=true"
    exit 0
fi

echo "✅ RUN_MIGRATIONS=true - Ejecutando migraciones..."

# Activar el virtual environment de EB
source /var/app/venv/*/bin/activate

# Ir al directorio de la aplicación
cd /var/app/current

# Ejecutar migraciones
echo "📦 Ejecutando migrate..."
python manage.py migrate --noinput

# Collectstatic
echo "📦 Ejecutando collectstatic..."
python manage.py collectstatic --noinput

echo "✅ Post-deploy completado exitosamente"
