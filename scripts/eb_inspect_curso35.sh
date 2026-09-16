#!/bin/bash
# Solo lectura: pasos/secciones del curso 35 para redactar guías de reto fieles al contenido.
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME OPENAI_API_KEY; do
  export "$key=$($GC environment -k $key 2>/dev/null)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
cd /var/app/current
source /var/app/venv/*/bin/activate

python manage.py shell <<'PY'
from core.models import Curso
c = Curso.objects.get(id=35)
for m in c.modulos.order_by('numero'):
    print('=== M%s | %s | modo=%s' % (m.numero, m.titulo, getattr(m, 'modo_entrega', '?')))
    for s in m.secciones.order_by('orden'):
        print('  SEC %s: %s' % (s.orden, s.titulo))
        for p in s.pasos.order_by('orden'):
            txt = (p.contenido or '').replace('\n', ' ')[:300]
            print('    P%s [%s] %s' % (p.orden, p.tipo, txt))
    n_pasos_sueltos = m.pasos.filter(seccion__isnull=True).count()
    print('  pasos sin seccion:', n_pasos_sueltos)
    for p in m.pasos.filter(seccion__isnull=True).order_by('orden')[:8]:
        print('    P%s [%s] %s' % (p.orden, p.tipo, (p.contenido or '').replace('\n', ' ')[:300]))
PY
