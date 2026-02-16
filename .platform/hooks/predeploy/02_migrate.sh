#!/bin/bash
# Ejecutar migraciones Django antes del deploy

echo "=== EJECUTANDO MIGRACIONES DJANGO ==="

# Activar el virtual environment de EB
source /var/app/venv/*/bin/activate

# Ir al directorio staging
cd /var/app/staging

# Ejecutar migraciones
echo "Ejecutando migrate..."
python manage.py migrate --noinput 2>&1

# Collectstatic
echo "Ejecutando collectstatic..."
python manage.py collectstatic --noinput 2>&1

echo "=== MIGRACIONES COMPLETADAS ==="
