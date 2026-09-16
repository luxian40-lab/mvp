#!/bin/bash
# Verifica que el RAG de un curso se instancia sin error de permisos (usuario webapp).
# Uso: CURSO_ID=35 bash eb_diag_chroma.sh
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "$key=$($GC environment -k $key 2>/dev/null || true)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
export CURSO_ID="${CURSO_ID:-35}"
cd /var/app/current

echo "=== como ec2-user (esperado: falla por permisos)"
source /var/app/venv/*/bin/activate
python3 - <<'PY' || true
import os
import django
django.setup()
from core.models import Curso
from core.rag_manager import rag_manager
c = Curso.objects.filter(id=int(os.environ['CURSO_ID'])).first()
print('curso', c.id, c.nombre, 'cliente', c.cliente_id)
print('rag =>', rag_manager.obtener_rag(c.cliente_id, c.id))
PY

echo "=== como webapp (dueño de CHROMA_DB_DIR y de los procesos web/celery)"
sudo -u webapp -E env HOME=/tmp PYTHONPATH=/var/app/current DJANGO_SETTINGS_MODULE=mvp_project.settings_production \
  CURSO_ID="$CURSO_ID" \
  DB_NAME="$DB_NAME" DB_USER="$DB_USER" DB_PASSWORD="$DB_PASSWORD" DB_HOST="$DB_HOST" DB_PORT="$DB_PORT" \
  AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  AWS_STORAGE_BUCKET_NAME="$AWS_STORAGE_BUCKET_NAME" AWS_S3_REGION_NAME="$AWS_S3_REGION_NAME" USE_S3=True \
  /var/app/venv/*/bin/python3 - <<'PY'
import getpass
import os
import django
django.setup()
from core.models import Curso, DocumentoRAG
from core.rag_manager import rag_manager
print('usuario', getpass.getuser())
c = Curso.objects.filter(id=int(os.environ['CURSO_ID'])).first()
rag = rag_manager.obtener_rag(c.cliente_id, c.id)
print('rag =>', 'OK' if rag else 'None')
if rag:
    print('coleccion items =', rag.collection.count())
print('documentos RAG del curso =', DocumentoRAG.objects.filter(curso_id=c.id).count())
PY
