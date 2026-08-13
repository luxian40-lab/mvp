#!/bin/bash
set -eu
cd /var/app/current
source /var/app/venv/*/bin/activate
ENVF=/opt/elasticbeanstalk/deployment/env
if [ -f "$ENVF" ]; then
  set -a
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
from core.models import Curso
from aprende.calificacion_aula_service import recalcular_notas_asistencia_curso
from aprende.ranking_service import ranking_curso_profesor
from core.gamificacion import EvaluacionNotaGamificacion
from core.gamificacion_modo import curso_usa_calificacion

curso = Curso.objects.select_related('cliente').get(pk=34)
print('curso', curso.id, curso.nombre, 'clases', curso.es_modo_clases())
print('usa_calificacion', curso_usa_calificacion(curso.cliente, curso))
n = recalcular_notas_asistencia_curso(curso)
print('notas_asistencia_recalc', n)
print('total_eval_notas', EvaluacionNotaGamificacion.objects.filter(curso=curso).count())
rk = ranking_curso_profesor(curso.cliente, curso, limite=5)
print('ranking_modo', rk.get('modo'), 'filas', len(rk.get('filas') or []))
for f in (rk.get('filas') or [])[:5]:
    print(f.get('posicion'), f.get('nombre'), f.get('valor'))
PY
