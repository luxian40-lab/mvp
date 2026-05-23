#!/bin/bash
# Ejecutar en instancia EB: sudo /bin/bash /var/app/current/scripts/eb_copiar_cursos.sh [--reset]
set -e
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT OPENAI_API_KEY; do
  val="$("$GC" environment -k "$key" 2>/dev/null || true)"
  if [ -n "$val" ]; then export "$key"="$val"; fi
done
export USE_S3=True
export AWS_STORAGE_BUCKET_NAME="${AWS_STORAGE_BUCKET_NAME:-eki-produccion}"
export AWS_S3_REGION_NAME="${AWS_S3_REGION_NAME:-us-east-2}"
cd /var/app/current
# shellcheck disable=SC1091
source /var/app/venv/*/bin/activate
python manage.py copiar_cursos "$@"
echo "OK: copiar_cursos completado."
