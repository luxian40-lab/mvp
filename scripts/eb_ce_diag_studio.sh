#!/bin/bash
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME USE_S3 ELEVENLABS_API_KEY ELEVENLABS_VOICE_ID OPENAI_API_KEY RUNWAY_API_KEY REDIS_URL CELERY_BROKER_URL; do
  export "$key=$($GC environment -k $key 2>/dev/null || true)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
cd /var/app/current
source /var/app/venv/*/bin/activate

python3 <<'PY'
import os
import django
django.setup()

from django.contrib.staticfiles import finders
from mvp_project.static_safe import static_safe
from core.course_engine.voice_config import catalogo_voces
from core.course_engine.voice_demos import url_demo_voz, demo_slug_for_voice_id
from core.models import DocumentoRAG

print('=== DEPS (keys present, no values) ===')
for k in ('ELEVENLABS_API_KEY', 'ELEVENLABS_VOICE_ID', 'OPENAI_API_KEY', 'RUNWAY_API_KEY', 'USE_S3'):
    v = (os.environ.get(k) or '').strip()
    print(f"  {k}: {'SET' if v else 'MISSING'}")

print('=== CELERY course_engine ===')
try:
    from mvp_project.celery import app as celery_app
    insp = celery_app.control.inspect(timeout=3.0)
    active = insp.active_queues() or {}
    ce = []
    for worker, queues in active.items():
        names = [q.get('name') for q in (queues or [])]
        if 'course_engine' in names:
            ce.append(worker)
    print('  workers on course_engine:', ce or 'NONE')
except Exception as e:
    print('  inspect failed:', e)

print('=== VOICE DEMOS ===')
for v in catalogo_voces():
    slug = demo_slug_for_voice_id(v['id'])
    found = finders.find(f'course_engine/voices/{slug}.mp3')
    try:
        url = static_safe(f'course_engine/voices/{slug}.mp3')
    except Exception as e:
        url = f'ERR:{e}'
    demo = url_demo_voz(v['id'])
    print(f"{v['label']:14} slug={slug:16} find={bool(found)} static={url} demo.ok={demo.get('ok')} source={demo.get('source')}")

print('=== RECENT RAG DOCS curso 22 ===')
for d in DocumentoRAG.objects.filter(curso_id=22).order_by('-id')[:8]:
    print(f"id={d.id} nombre={d.nombre!r} estado={d.estado} chunks={d.chunks_indexados} archivo={d.archivo}")

print('=== ALL RAG ERRORS last 10 ===')
for d in DocumentoRAG.objects.filter(estado='error').order_by('-id')[:10]:
    print(f"id={d.id} curso={d.curso_id} nombre={d.nombre!r} archivo={d.archivo}")
PY
