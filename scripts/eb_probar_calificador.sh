#!/bin/bash
# Prueba del calificador (no envía WhatsApp): evalúa dos respuestas de ejemplo del curso 35.
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
from core.tutor_ia_modulo import evaluar_reto_facilitador

curso = Curso.objects.get(id=35)
m1 = curso.modulos.order_by('numero').first()
reto = (
    'Revise entre 5 y 10 colmenas de su apiario y registre cuántas presentan cría '
    'salteada, abejas temblorosas, mortalidad frente a la piquera o varroa visible. '
    'Señale la colmena más sospechosa y el criterio que usó.'
)

CASOS = [
    ('VAGA', 'Revisé el apiario y vi que algunas colmenas están raras, voy a estar pendiente.'),
    (
        'CON CIFRAS',
        'Revisé 10 colmenas: 3 con cría salteada, 2 con abejas temblorosas y en la número 7 '
        'conté unas 15 abejas muertas frente a la piquera. La más sospechosa es la 7 porque '
        'junta cría salteada y mortalidad. Voy a tomar muestra de 30 abejas adultas mañana.',
    ),
]

for etiqueta, respuesta in CASOS:
    puntaje, feedback = evaluar_reto_facilitador(
        [m1], respuesta, reto,
        estudiante_nombre='Julian',
        curso_nombre=curso.nombre,
    )
    print('===== %s -> %s/10' % (etiqueta, puntaje))
    print(feedback)
    print('=====')
PY
