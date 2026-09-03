#!/bin/bash
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

python3 <<'PY'
import django
django.setup()
from core.models import DocumentoRAG, Curso
from core.rag_manager import rag_manager

print('=== DOCS estado!=indexado last 15 ===')
for d in DocumentoRAG.objects.exclude(estado='indexado').order_by('-id')[:15]:
    print(f"id={d.id} curso={d.curso_id} nombre={d.nombre!r} estado={d.estado} chunks={d.chunks_indexados} file={d.archivo}")

print('=== DOCS recientes cualquier estado ===')
for d in DocumentoRAG.objects.order_by('-id')[:15]:
    print(f"id={d.id} curso={d.curso_id} nombre={d.nombre!r} estado={d.estado} chunks={d.chunks_indexados}")

# Reintentar indexar el más reciente en error
err = DocumentoRAG.objects.filter(estado='error').order_by('-id').first()
if err:
    print(f'=== REINDEX TRY id={err.id} {err.nombre} ===')
    try:
        n = err.indexar()
        print('chunks=', n, 'estado=', err.estado)
    except Exception as e:
        print('EXC', type(e).__name__, e)

# Chroma writable?
import os
from django.conf import settings
p = getattr(settings, 'CHROMA_DB_DIR', '')
print('CHROMA_DB_DIR', p, 'exists', os.path.isdir(p), 'writable', os.access(p, os.W_OK) if p else False)
print('as user', os.getuid() if hasattr(os,'getuid') else '?')
PY
