#!/bin/bash
# Reindexa DocumentosRAG en error usando el usuario webapp (Chroma escribible).
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME USE_S3; do
  export "$key=$($GC environment -k $key 2>/dev/null || true)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
cd /var/app/current
source /var/app/venv/*/bin/activate

# Correr como webapp para poder escribir Chroma
sudo -u webapp -E env HOME=/tmp PYTHONPATH=/var/app/current DJANGO_SETTINGS_MODULE=mvp_project.settings_production \
  DB_NAME="$DB_NAME" DB_USER="$DB_USER" DB_PASSWORD="$DB_PASSWORD" DB_HOST="$DB_HOST" DB_PORT="$DB_PORT" \
  AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  AWS_STORAGE_BUCKET_NAME="$AWS_STORAGE_BUCKET_NAME" AWS_S3_REGION_NAME="$AWS_S3_REGION_NAME" USE_S3=True \
  /var/app/venv/*/bin/python3 <<'PY'
import django
django.setup()
from core.models import DocumentoRAG
from core.course_engine.voice_demos import url_demo_voz
from core.course_engine.voice_config import catalogo_voces

print('=== REINDEX errores ===')
for d in DocumentoRAG.objects.filter(estado='error').order_by('id'):
    print(f'reindex id={d.id} {d.nombre}...', end=' ')
    n = d.indexar()
    d.refresh_from_db()
    print(f'chunks={n} estado={d.estado}')

print('=== VOICE DEMOS URLs ===')
for v in catalogo_voces():
    out = url_demo_voz(v['id'])
    print(v['label'], out.get('ok'), out.get('url', '')[:80])
PY
