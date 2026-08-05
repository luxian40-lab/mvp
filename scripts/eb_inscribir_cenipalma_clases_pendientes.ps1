# Diagnostica e inscribe en Cenipalma — Clases Aprende a estudiantes Cenipalma sin progreso.
# Uso: .\scripts\eb_inscribir_cenipalma_clases_pendientes.ps1
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

from core.inscripcion_curso import inscribir_estudiante_en_curso, resolver_curso_por_nombre
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante

dry = $dry
cli = Cliente.objects.filter(nombre='Cenipalma').first()
assert cli, 'FAIL Cenipalma'
cursos = list(Curso.objects.filter(cliente=cli).values_list('id', 'nombre', 'modo_aula', 'activo'))
print('cursos_cenipalma:')
for row in cursos:
    print(' ', row)

curso = resolver_curso_por_nombre('Cenipalma — Clases Aprende', cliente_nombre='Cenipalma')
if not curso:
    curso = resolver_curso_por_nombre('Cenipalma - Clases Aprende', cliente_nombre='Cenipalma')
assert curso, 'FAIL: no se resolvió curso clases'
print('curso_ok', curso.id, repr(curso.nombre), [hex(ord(c)) for c in curso.nombre if ord(c)>127])

ests = Estudiante.objects.filter(cliente=cli, activo=True)
total = ests.count()
ya = ProgresoEstudiante.objects.filter(estudiante__cliente=cli, curso=curso).count()
sin = ests.exclude(id__in=ProgresoEstudiante.objects.filter(curso=curso).values_list('estudiante_id', flat=True))
print('estudiantes_cenipalma', total, 'con_progreso_clases', ya, 'sin_progreso', sin.count())

n = 0
for est in sin.iterator():
    if dry:
        print('DRY', est.id, est.nombre, est.telefono)
    else:
        _, creado = inscribir_estudiante_en_curso(est, curso)
        if creado:
            n += 1
print('inscritos_nuevos', n, 'dry', dry)
print('QA_PASS cenipalma_inscribir')
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
echo $pyB64 | base64 -d > /tmp/inscribir_cenipalma.py
python /tmp/inscribir_cenipalma.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Inscribir Cenipalma Clases dry=$DryRun" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw 'failed' }
