# Renombra curso clases (mojibake) e inscribe estudiantes Cenipalma sin progreso.
param(
    [string]$Environment = 'eki-prod-final',
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$dry = if ($DryRun) { 'True' } else { 'False' }
$py = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()
from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante

dry = $dry
cli = Cliente.objects.get(nombre='Cenipalma')
curso = Curso.objects.filter(cliente=cli, modo_aula='clases').order_by('id').last()
assert curso, 'no curso clases'
nombre_ok = 'Cenipalma — Clases Aprende'
print('antes', repr(curso.nombre))
if curso.nombre != nombre_ok:
    if not dry:
        curso.nombre = nombre_ok
        curso.save(update_fields=['nombre'])
    print('renombrado_a', repr(nombre_ok), 'dry', dry)
else:
    print('nombre_ya_ok')

sin = Estudiante.objects.filter(cliente=cli, activo=True).exclude(
    id__in=ProgresoEstudiante.objects.filter(curso=curso).values_list('estudiante_id', flat=True)
)
print('faltan', sin.count())
n = 0
for est in sin.iterator():
    if dry:
        continue
    _, creado = inscribir_estudiante_en_curso(est, curso)
    if creado:
        n += 1
print('inscritos_nuevos', n if not dry else 0)
print('progresos_final', ProgresoEstudiante.objects.filter(curso=curso, estudiante__cliente=cli).count())
print('QA_PASS fix_cenipalma_nombre_inscribir')
"@
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
echo $pyB64 | base64 -d > /tmp/fix_ceni_nombre.py
python /tmp/fix_ceni_nombre.py
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Fix nombre+inscribir dry=$DryRun" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw 'failed' }
