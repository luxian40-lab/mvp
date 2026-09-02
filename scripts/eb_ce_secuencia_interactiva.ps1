# Prueba CE — Secuencia interactiva (RAG + texto/micro_video + WA QA).
param(
    [string]$Environment = "eki-prod-final",
    [string]$TelQa = "573026480629",
    [int]$GenerateVideos = 2,
    [switch]$DryRunOnly
)

. "$PSScriptRoot\_eb_env_prod_bash.ps1"

$briefPath = Join-Path $PSScriptRoot "fixtures\ce_brief_gestion_financiera.txt"
if (-not (Test-Path $briefPath)) { throw "Falta $briefPath" }
$briefB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw $briefPath)))

$dryFlag = if ($DryRunOnly) { "dry_run=True" } else { "dry_run=False" }
$genVideos = if ($DryRunOnly) { 0 } else { $GenerateVideos }

$bash = @"
$(Get-EbEnvProdBash)
GC=/opt/elasticbeanstalk/bin/get-config
for key in OPENAI_API_KEY RUNWAY_API_KEY ELEVENLABS_API_KEY ELEVENLABS_VOICE_ID; do
  export "`$key=`$(`$GC environment -k `$key 2>/dev/null)"
done
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
export COURSE_ENGINE_LOCAL_DIR=/tmp/course_engine/runs
export TEL_QA=$TelQa
cd /var/app/current && source /var/app/venv/*/bin/activate
python3 <<'PY'
import base64
import json
import os
import sys
import time

import django
django.setup()

from core.models import Curso, Modulo
from core.course_engine.interactive_generator import InteractiveSequenceGenerator
from core.twilio_media import evaluar_mp4_listo_whatsapp, _descargar_bytes
from core.utils import enviar_whatsapp_twilio

BRIEF_B64 = "$briefB64"
brief = base64.b64decode(BRIEF_B64).decode("utf-8")

curso = Curso.objects.filter(pk=22).first()
mod = Modulo.objects.filter(curso_id=22, numero=8).order_by("id").first()
if not curso:
    print("[FAIL] Curso 22 no encontrado")
    sys.exit(1)
print(f"Curso: {curso.nombre} | Modulo M{mod.numero if mod else '?'}: {mod.titulo if mod else 'n/a'}")
print(f"Brief chars: {len(brief)} | generate_videos: $genVideos | dry_run: $dryFlag")

gen = InteractiveSequenceGenerator()
out = gen.generar(
    cliente_id=curso.cliente_id,
    curso_id=curso.id,
    brief=brief,
    modulo_id=mod.id if mod else None,
    $dryFlag,
    max_bloques=14,
    max_micro_videos=6,
    generar_micro_videos=$genVideos,
    runway_duration_sec=8,
)
for p in out.pasos:
    print(p)
print(f"Run ID: {out.run_id}")
print(f"Manifest: {out.manifest_path}")
print(f"Costo USD: est={out.costo_estimado_usd:.2f} real={out.costo_real_usd:.2f}")
if out.errors:
    print("Errores:", out.errors)

if not out.pasos_wa:
    print("[FAIL] Sin pasos WA")
    sys.exit(1)

# Gate videos generados
for paso in out.pasos_wa:
    if paso.tipo == "video" and paso.media_url:
        raw = _descargar_bytes(paso.media_url) or b""
        gate = evaluar_mp4_listo_whatsapp(raw)
        print(f"Gate WA paso {paso.orden}:", json.dumps(gate, ensure_ascii=False))
        if not gate.get("apto"):
            sys.exit(1)

if $dryFlag:
    print("[OK] Dry-run secuencia — sin envio WA")
    sys.exit(0)

tel = os.environ.get("TEL_QA", "573026480629")
pref = "[eki QA secuencia] "
# Enviar primeros 4 pasos (texto + video + texto + error)
orden_envio = [1, 2, 3, 4]
for paso in out.pasos_wa:
    if paso.orden not in orden_envio:
        continue
    if paso.tipo == "video" and paso.media_url:
        r = enviar_whatsapp_twilio(tel, pref + paso.titulo, media_url=paso.media_url.strip())
    else:
        r = enviar_whatsapp_twilio(tel, pref + paso.contenido)
    print(f"WA paso {paso.orden}:", json.dumps(r, ensure_ascii=False))
    if not r.get("success"):
        sys.exit(1)
    time.sleep(2)

print("[OK] Secuencia enviada a", tel[-10:])
PY
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
