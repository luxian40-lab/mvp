#!/bin/bash
# Solo lectura: últimos mensajes del TEL_QA (respuesta al reto y su evaluación).
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "$key=$($GC environment -k $key 2>/dev/null)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
cd /var/app/current
source /var/app/venv/*/bin/activate

export TEL_QA="${TEL_QA:-573026480629}"

python manage.py shell <<'PY'
import os

from core.models import EstudianteEventoAprendizaje, WhatsappLog

tel = os.environ['TEL_QA']
qs = WhatsappLog.objects.filter(telefono__endswith=tel[-10:]).order_by('-id')[:6]
for log in reversed(list(qs)):
    print('>>>>> id=%s tipo=%s fecha=%s' % (log.id, log.tipo, log.fecha))
    print((log.mensaje or '')[:1200])
    print('<<<<<')

print('=== EVENTOS DE RETO ===')
evs = EstudianteEventoAprendizaje.objects.filter(
    tipo__in=[
        EstudianteEventoAprendizaje.TIPO_RETO_PLANTEADO,
        EstudianteEventoAprendizaje.TIPO_RETO_RESPONDIDO,
    ],
).order_by('-id')[:4]
for ev in evs:
    meta = ev.metadata or {}
    print('ev=%s tipo=%s curso=%s tipo_resp=%s puntaje=%s evidencia=%s' % (
        ev.id, ev.tipo, ev.curso_id, meta.get('tipo_respuesta'),
        meta.get('puntaje'), bool(meta.get('evidencia_url'))))
PY
