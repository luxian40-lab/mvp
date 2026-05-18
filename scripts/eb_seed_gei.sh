#!/bin/bash
# Ejecutar en instancia EB: sudo /bin/bash /var/app/current/scripts/eb_seed_gei.sh
set -e
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "$key"="$("$GC" environment -k "$key")"
done
export USE_S3=True
export AWS_STORAGE_BUCKET_NAME="${AWS_STORAGE_BUCKET_NAME:-eki-produccion}"
export AWS_S3_REGION_NAME="${AWS_S3_REGION_NAME:-us-east-2}"
cd /var/app/current
# shellcheck disable=SC1091
source /var/app/venv/*/bin/activate
python manage.py sembrar_flujos_gei_automatico --reset
python manage.py crear_cliente_preserva
echo "OK: flujos GEI sembrados en PostgreSQL de produccion."
