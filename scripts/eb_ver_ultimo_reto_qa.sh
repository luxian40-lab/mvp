#!/bin/bash
# Solo lectura: mensaje enviado al TEL_QA por SID (verificar formato del reto).
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

export SID_QA="${SID_QA:-}"

python manage.py shell <<'PY'
import os
import re

from core.models import WhatsappLog

sid = os.environ.get('SID_QA', '')
log = WhatsappLog.objects.filter(mensaje_id=sid).first() if sid else None
if log is None:
    log = WhatsappLog.objects.filter(tipo='SENT').order_by('-id').first()

texto = (log.mensaje or '') if log else ''
print('ID:', getattr(log, 'id', None), '| fecha:', getattr(log, 'fecha', None))
print('LEN:', len(texto), '| LINEAS:', len(texto.splitlines()))
emojis = re.findall(
    '[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u27BF\u2B00-\u2BFF\uFE0F]', texto
)
print('EMOJIS:', len(emojis), emojis[:10])
print('TIENE_BLOQUES:', any(x in texto for x in ('RETO DE CAMPO', 'Hoy:', 'Tiempo:', 'Evidencia:')))
print('----- TEXTO -----')
print(texto)
print('----- FIN -----')
PY
