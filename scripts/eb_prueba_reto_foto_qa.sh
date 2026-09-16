#!/bin/bash
# QA: genera el reto real del M1 curso 35 con la nueva guía y lo envía SOLO a TEL_QA,
# dejando al estudiante en estado de reto para poder responder con una foto.
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_NUMBER TWILIO_PHONE_NUMBER TWILIO_WHATSAPP_FROM AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME OPENAI_API_KEY; do
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

from core.models import Curso, Estudiante, ProgresoEstudiante
from core.facilitador_perfil import nombre_display_facilitador
from core.tutor_ia_modulo import generar_reto_facilitador
from core.utils import enviar_whatsapp_twilio

tel = os.environ['TEL_QA']
curso = Curso.objects.get(id=35)
est = Estudiante.objects.filter(telefono__endswith=tel[-10:]).first()
print('estudiante:', est.id if est else None)
prog = ProgresoEstudiante.objects.filter(estudiante=est, curso=curso).first()
print('progreso:', prog.id if prog else None)

m1 = curso.modulos.order_by('numero').first()
reto = generar_reto_facilitador(
    [m1],
    curso.nombre,
    estudiante_nombre=est.nombre or 'Participante',
    curso=curso,
    modulo_checkpoint=m1,
)
print('--- RETO GENERADO ---')
print(reto)

est.contexto_temporal = {
    'tipo': 'reto_facilitador',
    'modulos_reto_ids': [m1.id],
    'reto_texto': reto,
    'progreso_id': prog.id if prog else None,
    'es_final': False,
}
est.estado_onboarding = 'esperando_respuesta_reto'
est.save(update_fields=['contexto_temporal', 'estado_onboarding'])

nombre = nombre_display_facilitador(curso)
cuerpo = (
    f'📋 *{nombre}*\n\n{reto}\n\n'
    '✍️ _Escriba, envíe un audio o mande la foto de su evidencia._'
)
r = enviar_whatsapp_twilio(tel, cuerpo)
print('envio ok:', r.get('success'), r.get('mensaje_id'))
PY
