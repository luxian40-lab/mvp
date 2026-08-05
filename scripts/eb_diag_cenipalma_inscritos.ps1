# Solo diagnostica (sin escribir): cursos Cenipalma + cuántos tienen progreso clases.
param([string]$Environment = 'eki-prod-final')
$ErrorActionPreference = 'Stop'
$py = @'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
django.setup()
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
cli = Cliente.objects.filter(nombre="Cenipalma").first()
print("cliente", cli.id if cli else None)
for c in Curso.objects.filter(cliente=cli):
    print("curso", c.id, repr(c.nombre), "activo", c.activo, "modo", c.modo_aula)
    print("  codepoints", [hex(ord(ch)) for ch in c.nombre if ord(ch) > 127])
curso = Curso.objects.filter(cliente=cli, modo_aula="clases").order_by("id").last()
print("pick_clases", curso.id if curso else None, repr(curso.nombre) if curso else None)
if curso:
    total = Estudiante.objects.filter(cliente=cli, activo=True).count()
    con = ProgresoEstudiante.objects.filter(curso=curso, estudiante__cliente=cli).count()
    print("est_activos", total, "progresos_clases", con, "faltan", total - con)
'@
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key 2>/dev/null)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
echo $pyB64 | base64 -d > /tmp/diag_ceni.py
python /tmp/diag_ceni.py
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
