#!/bin/bash
# Script que se ejecuta despues de cada deployment en AWS Elastic Beanstalk

# Activar el entorno virtual
source /var/app/venv/*/bin/activate

# Ir al directorio de la aplicacion
cd /var/app/current

# Ejecutar migraciones de base de datos
echo "Ejecutando migraciones..."
python manage.py migrate --noinput

# Recolectar archivos estaticos
echo "Recolectando archivos estaticos..."
python manage.py collectstatic --noinput

echo "Post-deploy completado"
