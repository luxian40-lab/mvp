# Prueba CE — Gestión Financiera (contexto visual + 15s + WA QA).
param(
    [string]$Environment = "eki-prod-final",
    [string]$TelQa = "573026480629"
)

. "$PSScriptRoot\_eb_env_prod_bash.ps1"

$briefPath = Join-Path $PSScriptRoot "fixtures\ce_brief_gestion_financiera.txt"
if (-not (Test-Path $briefPath)) { throw "Falta $briefPath" }
$briefB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw $briefPath)))

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
import subprocess
import sys

import django
django.setup()

from core.models import Curso, Modulo
from core.course_engine.video_generator import CourseVideoGenerator
from core.twilio_media import evaluar_mp4_listo_whatsapp, _descargar_bytes

BRIEF_B64 = "$briefB64"
brief = base64.b64decode(BRIEF_B64).decode("utf-8")

curso = Curso.objects.filter(pk=22).first()
mod = Modulo.objects.filter(curso_id=22, numero=8).order_by("id").first()
print(f"Curso: {curso.nombre} | Modulo M{mod.numero}: {mod.titulo}")
print(f"Brief chars: {len(brief)}")

gen = CourseVideoGenerator()
out = gen.generar(
    cliente_id=curso.cliente_id,
    curso_id=curso.id,
    brief=brief,
    modulo_id=mod.id,
    micro_realista=True,
    visual_style="documental",
    runway_duration_sec=10,
    target_duration_sec=15,
)
for p in out.pasos:
    print(p)
print(f"Costo USD: {out.costo_real_usd:.2f}")
print(f"Errores: {out.run.errors}")

url = out.run.video_url
if not url:
    print("[FAIL] Sin video")
    sys.exit(1)
print(f"Video S3: {url}")

raw = _descargar_bytes(url) or b""
gate = evaluar_mp4_listo_whatsapp(raw)
print("Gate WA:", json.dumps(gate, ensure_ascii=False))
if not gate.get("apto"):
    sys.exit(1)
dur = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", "-"],
    input=raw, capture_output=True,
)
if dur.returncode == 0:
    print(f"Duracion: {float(dur.stdout.decode().strip()):.1f}s")

from core.utils import enviar_whatsapp_twilio
tel = os.environ.get("TEL_QA", "573026480629")
msg = "[eki QA] Video gestion financiera y rentabilidad — contexto visual alineado. Responde OK si cuadra."
r = enviar_whatsapp_twilio(tel, msg, media_url=url.strip())
print("WA:", json.dumps(r, ensure_ascii=False))
if not r.get("success"):
    sys.exit(1)
print("[OK] Enviado a", tel[-10:])
PY
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
