# Smoke curso C informativo en prod: inscripción + aviso WA + OTP *aula*.
# Uso: .\scripts\eb_smoke_curso_c_informativo.ps1 -EnviarWhatsApp
param(
    [string]$Telefono = '3026480629',
    [string]$Environment = 'eki-prod-final',
    [switch]$EnviarWhatsApp
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_eb_env_prod_bash.ps1"
$digits = ($Telefono -replace '\D', '')
if ($digits.Length -eq 10 -and $digits.StartsWith('3')) { $digits = "57$digits" }
$sendWa = if ($EnviarWhatsApp) { 'True' } else { 'False' }

$py = @"
import os, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Curso, Estudiante, Modulo
from core.utils import enviar_whatsapp_twilio

tel = '$digits'
enviar = $sendWa
print('tel=', tel, 'enviar_wa=', enviar)

est = Estudiante.objects.filter(telefono=tel).first()
if not est:
    est = Estudiante.objects.filter(telefono__endswith=tel[-10:]).first()

if est and est.cliente_id:
    cli = est.cliente
    print('estudiante reusado', est.id, 'cliente', cli.id, cli.nombre)
else:
    cli, _ = Cliente.objects.get_or_create(
        nombre='eki piloto curso C informativo',
        defaults=dict(
            nit='900000CURSOC',
            contacto_principal='Piloto eki',
            email='piloto.cursoc@eki.technology',
            telefono=tel,
            activo=True,
            portal_productos='cursos',
        ),
    )
    print('cliente', cli.id)

curso, cc = Curso.objects.get_or_create(
    cliente=cli,
    nombre='Curso C — clases Aprende (piloto)',
    defaults=dict(
        descripcion='Curso informativo: contenido en Aprende, WhatsApp solo avisos.',
        activo=True,
        usar_agentes_ia=False,
        dias_espera_entre_modulos=0,
        modo_aula='clases',
        usar_gamificacion=False,
        orden=99,
    ),
)
upd_c = []
if curso.usar_agentes_ia:
    curso.usar_agentes_ia = False
    upd_c.append('usar_agentes_ia')
if getattr(curso, 'modo_aula', None) != 'clases':
    curso.modo_aula = 'clases'
    upd_c.append('modo_aula')
if getattr(curso, 'usar_gamificacion', True):
    curso.usar_gamificacion = False
    upd_c.append('usar_gamificacion')
if upd_c:
    curso.save(update_fields=upd_c)
print('curso', curso.id, 'created', cc, 'modo_aula', curso.modo_aula, 'gamif', curso.usar_gamificacion)

mod, mc = Modulo.objects.get_or_create(
    curso=curso,
    numero=1,
    defaults=dict(
        titulo='Clase 1 — bienvenida (grabada)',
        descripcion='Primera clase del piloto informativo.',
        contenido='Bienvenida al curso C. Mira el video y luego entrega la tarea en Aprende si aplica.',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        modo_entrega='legacy',
    ),
)
updates = []
if (mod.modo_entrega or '') != 'legacy':
    mod.modo_entrega = 'legacy'
    updates.append('modo_entrega')
if not (mod.video_url or '').strip():
    mod.video_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    updates.append('video_url')
if updates:
    mod.save(update_fields=updates)
print('modulo', mod.id, 'created', mc, 'modo', mod.modo_entrega)

if est:
    est.activo = True
    if (est.estado_onboarding or '') != 'completado':
        est.estado_onboarding = 'completado'
    if (est.estado_chat or '') != 'ACTIVO':
        est.estado_chat = 'ACTIVO'
    if not est.acepto_terminos:
        est.acepto_terminos = True
    if not est.cliente_id:
        est.cliente = cli
    est.save()
else:
    est = Estudiante.objects.create(
        cliente=cli,
        nombre='QA Curso C',
        telefono=tel,
        cedula='QA-CURSOC-' + tel[-4:],
        municipio='Bogotá',
        activo=True,
        estado_chat='ACTIVO',
        estado_onboarding='completado',
        acepto_terminos=True,
    )
    print('estudiante creado', est.id)

prog, creado = inscribir_estudiante_en_curso(est, curso)
print('progreso', prog.id, 'creado', creado, 'modulo_actual', prog.modulo_actual_id)
assert prog.modulo_actual_id == mod.id, 'FAIL: modulo_actual no es clase 1'

from aprende.acceso_modulos import modulos_visibles_aula
from aprende.biblioteca_service import items_biblioteca_aula

vis = list(modulos_visibles_aula(est, curso))
print('modulos_visibles', [(m.numero, m.titulo) for m in vis])
assert any(m.id == mod.id for m in vis), 'FAIL: clase 1 no visible en aula'
media = items_biblioteca_aula(est)
print('biblioteca_items', len(media))
assert len(media) >= 1, 'FAIL: biblioteca vacía'

from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp
msg = emitir_acceso_desde_whatsapp(est)
m = re.search(r'\*(\d{6})\*', msg or '')
assert m, 'FAIL: OTP no generado (posible rate limit *aula*)'
codigo = m.group(1)
print('otp_emit_ok', '**' + codigo[-2:])

aviso = (
    'Hola, prueba eki *curso C* (clases en Aprende, no por listo). '
    'Abre https://aprende.eki.technology/aprende/estudiante/login/ '
    'o escribe *aula* en este chat.'
)
if enviar:
    r1 = enviar_whatsapp_twilio(tel, aviso)
    print('wa_aviso', r1)
    r2 = enviar_whatsapp_twilio(tel, msg)
    print('wa_otp', r2)
    assert r1.get('success') and r2.get('success'), 'FAIL: envío WhatsApp'
else:
    print('wa_skip (usa -EnviarWhatsApp)')

print('QA_PASS curso_c_informativo')
print('Login: https://aprende.eki.technology/aprende/estudiante/login/')
print('Curso esperado: Curso C — clases Aprende (piloto)')
"@

$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
$(Get-EbEnvProdBash)
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
python manage.py migrate core 0130 --noinput || python manage.py migrate --noinput
echo $pyB64 | base64 -d > /tmp/smoke_curso_c.py
python /tmp/smoke_curso_c.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Smoke curso C en $Environment tel=$digits enviar=$EnviarWhatsApp" -ForegroundColor Cyan
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
