# Deja al teléfono SOLO el curso Cenipalma — Clases Aprende (quita otros progresos/grupos WA).
# Uso:
#   .\scripts\eb_solo_cenipalma_clases.ps1
#   .\scripts\eb_solo_cenipalma_clases.ps1 -Telefono 3026480629
param(
    [string]$Telefono = '3026480629',
    [string]$Environment = 'eki-prod-final'
)

$ErrorActionPreference = 'Stop'
$digits = ($Telefono -replace '\D', '')
if ($digits.Length -eq 10 -and $digits.StartsWith('3')) { $digits = "57$digits" }

$py = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.models_extras import GrupoEstudiantes

tel = '$digits'
cli = Cliente.objects.filter(nombre='Cenipalma').first()
assert cli, 'FAIL: Cliente Cenipalma'
curso = Curso.objects.filter(cliente=cli, nombre='Cenipalma — Clases Aprende').first()
if not curso:
    curso = Curso.objects.filter(cliente=cli, modo_aula='clases').order_by('id').last()
assert curso, 'FAIL: curso clases'
print('cliente', cli.id, 'wallpaper=', (cli.wallpaper_aula_url or '')[:120])
print('curso keep', curso.id, curso.nombre, curso.modo_aula)

est = Estudiante.objects.filter(telefono=tel).first()
if not est:
    est = Estudiante.objects.filter(telefono__endswith=tel[-10:]).first()
assert est, f'FAIL: estudiante {tel}'
if est.cliente_id != cli.id:
    est.cliente = cli
    est.save(update_fields=['cliente'])
    print('estudiante movido a Cenipalma')
print('estudiante', est.id, est.nombre, est.telefono)

kept = 0
removed = 0
for p in list(ProgresoEstudiante.objects.filter(estudiante=est).select_related('curso')):
    if p.curso_id == curso.id:
        kept += 1
        print('KEEP progreso', p.id, p.curso.nombre)
    else:
        print('DEL progreso', p.id, p.curso_id, getattr(p.curso, 'nombre', '?'))
        p.delete()
        removed += 1
if kept == 0:
    from core.inscripcion_curso import inscribir_estudiante_en_curso
    prog, _ = inscribir_estudiante_en_curso(est, curso)
    print('inscrito progreso', prog.id)
    kept = 1

g_keep = 'Cenipalma · Clases Aprende'
for g in GrupoEstudiantes.objects.filter(estudiantes=est, cliente=cli):
    if g.nombre == g_keep or g.cursos.filter(pk=curso.pk).exists():
        print('KEEP grupo', g.id, g.nombre)
        continue
    g.estudiantes.remove(est)
    print('OUT grupo', g.id, g.nombre)

g, _ = GrupoEstudiantes.objects.get_or_create(
    cliente=cli, nombre=g_keep, defaults={'emoji': '👥', 'activo': True}
)
g.estudiantes.add(est)
if not g.cursos.filter(pk=curso.pk).exists():
    g.cursos.add(curso)

restantes = list(
    ProgresoEstudiante.objects.filter(estudiante=est).values_list('curso__nombre', flat=True)
)
print('progresos finales:', restantes)
print('QA_PASS solo_clases kept=', kept, 'removed=', removed)
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
echo $pyB64 | base64 -d > /tmp/solo_cenipalma_clases.py
python /tmp/solo_cenipalma_clases.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Solo Clases Aprende en $Environment tel=$digits" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw "solo clases failed" }
