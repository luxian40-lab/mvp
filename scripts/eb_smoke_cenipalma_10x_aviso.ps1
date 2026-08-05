# Prueba Cenipalma 10x: inscribe + grupo + aviso HX (sin Habeas/*listo*).
# Uso:
#   .\scripts\eb_smoke_cenipalma_10x_aviso.ps1
#   .\scripts\eb_smoke_cenipalma_10x_aviso.ps1 -EnviarWhatsApp
param(
    [string]$Telefono = '3026480629',
    [string]$Environment = 'eki-prod-final',
    [string]$ContentSid = 'HX96ce7dbd39502b11aefd2aaa967c5de0',
    [switch]$EnviarWhatsApp
)

$ErrorActionPreference = 'Stop'
$digits = ($Telefono -replace '\D', '')
if ($digits.Length -eq 10 -and $digits.StartsWith('3')) { $digits = "57$digits" }
$sendWa = if ($EnviarWhatsApp) { 'True' } else { 'False' }

$py = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Campana, Cliente, Curso, Estudiante
from core.models_extras import GrupoEstudiantes
from core.whatsapp_service import enviar_template_twilio

tel = '$digits'
sid = '$ContentSid'
enviar = $sendWa
print('tel=', tel, 'sid=', sid, 'enviar=', enviar)

cli = Cliente.objects.filter(nombre='Cenipalma').first()
assert cli, 'FAIL: Cliente Cenipalma no existe (corra setup_cenipalma_piloto)'
curso = Curso.objects.filter(cliente=cli, nombre__icontains='10x').order_by('id').last()
assert curso, 'FAIL: curso 10x no encontrado'
assert getattr(curso, 'modo_aula', '') == 'clases', f'FAIL: modo_aula={curso.modo_aula}'
print('cliente', cli.id, 'curso', curso.id, curso.nombre, 'modo', curso.modo_aula)

est = Estudiante.objects.filter(telefono=tel).first()
if not est:
    est = Estudiante.objects.filter(telefono__endswith=tel[-10:]).first()
assert est, f'FAIL: estudiante {tel} no existe'
if est.cliente_id != cli.id:
    est.cliente = cli
    est.save(update_fields=['cliente'])
    print('estudiante movido a Cenipalma')
est.activo = True
if (est.estado_onboarding or '') != 'completado':
    est.estado_onboarding = 'completado'
if (est.estado_chat or '') != 'ACTIVO':
    est.estado_chat = 'ACTIVO'
if not est.acepto_terminos:
    est.acepto_terminos = True
est.save()
print('estudiante', est.id, est.nombre)

prog, creado = inscribir_estudiante_en_curso(est, curso)
print('progreso', prog.id, 'nuevo' if creado else 'existente')

g, _ = GrupoEstudiantes.objects.get_or_create(
    cliente=cli,
    nombre='Cenipalma · 10x Aprende',
    defaults={'emoji': '👥', 'activo': True},
)
g.estudiantes.add(est)
if not g.cursos.filter(pk=curso.pk).exists():
    g.cursos.add(curso)
print('grupo', g.id, g.nombre)

camp, cc = Campana.objects.get_or_create(
    nombre='Cenipalma 10x — aviso inicio (piloto)',
    cliente=cli,
    defaults={
        'template_twilio_id': sid,
        'es_campana_curso': False,
        'curso_destino': curso,
        'tipo_audiencia': 'grupo',
        'grupo': g,
        'categoria': 'educacion',
    },
)
upd = []
if camp.template_twilio_id != sid:
    camp.template_twilio_id = sid
    upd.append('template_twilio_id')
if camp.es_campana_curso:
    camp.es_campana_curso = False
    upd.append('es_campana_curso')
if camp.curso_destino_id != curso.id:
    camp.curso_destino = curso
    upd.append('curso_destino')
if camp.tipo_audiencia != 'grupo' or camp.grupo_id != g.id:
    camp.tipo_audiencia = 'grupo'
    camp.grupo = g
    upd.extend(['tipo_audiencia', 'grupo'])
if upd:
    camp.save(update_fields=list(dict.fromkeys(upd)))
print('campana', camp.id, 'created', cc, 'es_inicio_wa', camp.es_campana_curso, 'sid', camp.template_twilio_id)

if enviar:
    r = enviar_template_twilio(
        telefono=tel,
        content_sid=sid,
        variables={'1': (est.nombre or 'Estudiante').split()[0]},
    )
    print('wa_template', r)
    assert r.get('success'), f'FAIL envio: {r}'
else:
    print('wa_skip (usa -EnviarWhatsApp)')

print('QA_PASS cenipalma_10x_aviso')
print('Ops futuro: Campañas →', camp.nombre, '→ audiencia = grupo', g.nombre)
print('Aprende: https://aprende.eki.technology/aprende/estudiante/login/ (*aula*)')
"@

$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_NUMBER TWILIO_PHONE_NUMBER TWILIO_WHATSAPP_FROM; do
  export "`$key=`"`$(`$GC environment -k `$key 2>/dev/null)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
echo $pyB64 | base64 -d > /tmp/smoke_cenipalma_10x.py
python /tmp/smoke_cenipalma_10x.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Smoke Cenipalma 10x en $Environment tel=$digits enviar=$EnviarWhatsApp" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw "smoke failed" }
