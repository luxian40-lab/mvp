#!/bin/bash
set -eu
cd /var/app/current
# shellcheck disable=SC1091
source /var/app/venv/*/bin/activate
if [ -x /opt/elasticbeanstalk/bin/get-config ]; then
  eval "$(sudo /opt/elasticbeanstalk/bin/get-config environment | python3 -c 'import sys,json,shlex; d=json.load(sys.stdin); print(" ".join("export %s=%s"%(k,shlex.quote(str(v))) for k,v in d.items()))')"
fi
export PYTHONPATH=/var/app/current
export DJANGO_SETTINGS_MODULE=mvp_project.settings
export AWS_EXECUTION_ENV="${AWS_EXECUTION_ENV:-AWS_ECS_EC2}"
python <<'PY'
import django
django.setup()
from django.db import connection
from core.inscripcion_curso import inscribir_estudiante_en_curso, resolver_curso_por_nombre
from core.models import Curso, Estudiante
from core.utils_telefono import normalizar_telefono

tel = normalizar_telefono('3026480629')
print('db', connection.vendor, connection.settings_dict.get('HOST') or connection.settings_dict.get('NAME'))
print('tel', tel)
curso = resolver_curso_por_nombre('Tome las riendas de su dinero')
if curso is None:
    curso = Curso.objects.filter(nombre__icontains='riendas', activo=True).order_by('id').first()
print('curso', getattr(curso, 'id', None), getattr(curso, 'nombre', None))
if curso is None:
    raise SystemExit('no curso')
est = Estudiante.objects.filter(telefono=tel).first()
if est is None:
    est = Estudiante.objects.create(
        telefono=tel,
        nombre='Prueba Smoke eki',
        cedula='smoke' + tel[-8:],
        cliente=curso.cliente,
        activo=True,
        estado_chat='ESPERANDO_HABEAS_DATA',
        acepto_terminos=False,
    )
    print('CREATED', est.id)
else:
    fields = []
    if curso.cliente_id and est.cliente_id != curso.cliente_id:
        est.cliente = curso.cliente
        fields.append('cliente')
    if not est.activo:
        est.activo = True
        fields.append('activo')
    if not est.acepto_terminos and est.estado_chat != 'ESPERANDO_HABEAS_DATA':
        est.estado_chat = 'ESPERANDO_HABEAS_DATA'
        fields.append('estado_chat')
    if fields:
        est.save(update_fields=fields)
        print('UPDATED', fields)
    print('EXISTING', est.id, est.nombre, est.estado_chat, getattr(est.cliente, 'nombre', None), 'acepto', est.acepto_terminos)
prog, creado = inscribir_estudiante_en_curso(est, curso)
print('PROGRESO', prog.id, 'creado', creado, 'mod', getattr(prog.modulo_actual, 'numero', None), getattr(prog.modulo_actual, 'titulo', None))
print('NO_CAMPANA')
PY
