#!/bin/bash
set -eu
cd /var/app/current
# shellcheck disable=SC1091
source /var/app/venv/*/bin/activate
ENVF=/opt/elasticbeanstalk/deployment/env
if [ -f "$ENVF" ]; then
  set -a
  # shellcheck disable=SC2163
  while IFS= read -r line; do
    [ -n "$line" ] && export "$line"
  done < <(sudo tr '\0' '\n' < "$ENVF")
  set +a
fi
if [ -z "${DATABASE_URL:-}${DB_HOST:-}" ] && [ -x /opt/elasticbeanstalk/bin/get-config ]; then
  eval "$(sudo /opt/elasticbeanstalk/bin/get-config environment | python3 -c 'import sys,json,shlex; d=json.load(sys.stdin); print(" ".join("export %s=%s"%(k,shlex.quote(str(v))) for k,v in d.items()))')"
fi
export PYTHONPATH=/var/app/current
export DJANGO_SETTINGS_MODULE=mvp_project.settings
export AWS_EXECUTION_ENV="${AWS_EXECUTION_ENV:-AWS_ECS_EC2}"
python <<'PY'
import django
django.setup()
from core.models import ConfiguracionGlobal, Estudiante
from core.utils_telefono import normalizar_telefono
from core.whatsapp_service import (
    TWILIO_CONTENT_SIDS,
    _resolver_content_sid_habeas_data,
    enviar_habeas_data,
)

TEL = normalizar_telefono('3026480629')
est = Estudiante.objects.filter(telefono=TEL).select_related('cliente').first()
if not est:
    raise SystemExit(f'ERROR: no estudiante {TEL}')

sid = _resolver_content_sid_habeas_data(cliente=est.cliente)
cfg = ConfiguracionGlobal.get_solo()
print('tel', TEL)
print('estudiante', est.id, est.nombre)
print('cliente', getattr(est.cliente, 'id', None), getattr(est.cliente, 'nombre', None))
print('sid_cliente', (getattr(est.cliente, 'content_sid_habeas_data_twilio', '') or '')[:48])
print('sid_global', (cfg.content_sid_habeas_data_global or '')[:48])
print('sid_fallback', TWILIO_CONTENT_SIDS['habeas_data'])
print('sid_usado', sid)
print('antes', est.estado_chat, est.acepto_terminos)

est.acepto_terminos = False
est.fecha_aceptacion_terminos = None
est.estado_chat = 'ESPERANDO_HABEAS_DATA'
est.save(update_fields=['acepto_terminos', 'fecha_aceptacion_terminos', 'estado_chat'])
print('despues', est.estado_chat, est.acepto_terminos)

result = enviar_habeas_data(TEL, cliente=est.cliente)
print('envio', result)
if not result.get('success'):
    raise SystemExit(2)
print('OK: revisa WhatsApp y toca Acepto / No acepto')
PY
