# Inventario + reparación: videos WA listos (apto=True) inactivos.
#   .\scripts\eb_repair_videos_inactivos.ps1
#   .\scripts\eb_repair_videos_inactivos.ps1 -ApplyIds 52
param(
    [int[]]$ApplyIds = @()
)
$ErrorActionPreference = 'Stop'
$applyCsv = ($ApplyIds -join ',')
$py = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()
from core.models import PasoModulo, ProgresoEstudiante, ModuloCompletado, Curso
from core.module_steps import reset_progreso_pasos_modulo

APPLY = [int(x) for x in '$applyCsv'.split(',') if x.strip()]

def es_video(url):
    low = (url or '').lower().split('?')[0]
    return low.endswith(('.mp4', '.m4v', '.mov'))

qs = (
    PasoModulo.objects.filter(activo=False, media_wa_apto=True)
    .exclude(media_url='')
    .select_related('modulo', 'modulo__curso', 'seccion')
    .order_by('modulo__curso_id', 'modulo__numero', 'orden', 'id')
)
print('==== INVENTARIO video listo inactivo ====')
por = {}
n = 0
for p in qs:
    if not es_video(p.media_url):
        continue
    n += 1
    c = p.modulo.curso
    por.setdefault(c.id, {'nombre': c.nombre, 'n': 0, 'mods': set(), 'pasos': []})
    por[c.id]['n'] += 1
    por[c.id]['mods'].add(p.modulo_id)
    por[c.id]['pasos'].append(p)
    print(
        f"  c{c.id} M{p.modulo.numero} p{p.id} pub={p.modulo.publicado_wa} "
        f"sec_act={getattr(p.seccion,'activa',None)} {(p.titulo or '')[:40]!r}"
    )
print('TOTAL', n, 'cursos', len(por))
for cid, info in sorted(por.items()):
    print(f"  CURSO {cid} {info['nombre']!r} n={info['n']} mods={sorted(info['mods'])}")

if not APPLY:
    print('==== DRY (pass -ApplyIds) ====')
else:
    print('==== APPLY', APPLY, '====')
    for cid in APPLY:
        info = por.get(cid)
        if not info:
            print('  skip', cid, 'sin inactivos listos')
            continue
        mods = set()
        act = 0
        for p in info['pasos']:
            p.activo = True
            p.save(update_fields=['activo'])
            if p.seccion_id and not p.seccion.activa:
                p.seccion.activa = True
                p.seccion.save(update_fields=['activa'])
            mods.add(p.modulo_id)
            act += 1
        nprog = 0
        for prog in ProgresoEstudiante.objects.filter(curso_id=cid, modulo_actual_id__in=list(mods)):
            if prog.completado:
                continue
            if ModuloCompletado.objects.filter(progreso=prog, modulo_id=prog.modulo_actual_id).exists():
                continue
            reset_progreso_pasos_modulo(prog)
            nprog += 1
        print(f'  c{cid} ACTIVADOS={act} RESET_PROG={nprog}')
    print('==== APPLY DONE ====')
"@
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
export PYTHONPATH=/var/app/current
cd /var/app/current && source /var/app/venv/*/bin/activate
echo $pyB64 | base64 -d > /tmp/repair_vid_inact.py
python /tmp/repair_vid_inact.py
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] videos WA inactivos prod apply=$applyCsv" -ForegroundColor Cyan
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
