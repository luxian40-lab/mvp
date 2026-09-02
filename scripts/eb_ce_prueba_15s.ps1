# Prueba Course Engine 15s en prod — gate eki_wa_v1 + envío QA WhatsApp.
param(
    [string]$Environment = "eki-prod-final",
    [string]$TelQa = "573026480629"
)

. "$PSScriptRoot\_eb_env_prod_bash.ps1"

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
import json
import os
import subprocess
import sys

import django

django.setup()

from core.models import Curso, Modulo
from core.course_engine.video_generator import CourseVideoGenerator
from core.twilio_media import evaluar_mp4_listo_whatsapp, _descargar_bytes

curso = Curso.objects.filter(pk=22).first()
if not curso or not curso.cliente_id:
    print("[FAIL] Curso 22 sin cliente")
    sys.exit(1)
mod = Modulo.objects.filter(curso_id=22, numero=8).order_by("id").first()
if not mod:
    mod = Modulo.objects.filter(curso_id=22).order_by("numero").first()
print(f"Curso: {curso.nombre} cliente={curso.cliente_id}")
print(f"Modulo: M{mod.numero} id={mod.id} {mod.titulo}")

brief = (
    "Tres claves de finanzas rurales para jovenes del campo: separa gastos, "
    "guarda un fondo de emergencia y registra cada peso que entra y sale."
)

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
print(f"Costo real USD: {out.costo_real_usd:.2f}")
print(f"Errores: {out.run.errors}")

url = out.run.video_url
local = out.video_local
print(f"Video S3: {url}")
print(f"Video local: {local}")

if not url and not local:
    print("[FAIL] Sin video generado")
    sys.exit(1)

raw = b""
# Validar el archivo que va a WhatsApp (S3 wa_safe), no el compose local pre-gate.
if url:
    raw = _descargar_bytes(url) or b""
elif local and local.is_file():
    raw = local.read_bytes()

if raw:
    gate = evaluar_mp4_listo_whatsapp(raw)
    print("Gate WA:", json.dumps(gate, ensure_ascii=False))
    if not gate.get("apto"):
        print("[FAIL] Video no pasa gate eki_wa_v1")
        sys.exit(1)
    dur = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", "-",
        ],
        input=raw,
        capture_output=True,
    )
    if dur.returncode == 0:
        print(f"Duracion ffprobe: {float(dur.stdout.decode().strip()):.1f}s")

if not url:
    print("[WARN] Sin URL S3 — no se envia WA")
    sys.exit(0)

from core.utils import enviar_whatsapp_twilio

tel = os.environ.get("TEL_QA", "573026480629")
msg = (
    "[eki QA] Prueba Course Engine 15s — finanzas rurales. "
    "Si ves el video con buena calidad, responde OK."
)
r = enviar_whatsapp_twilio(tel, msg, media_url=url.strip())
print("WA send:", json.dumps(r, ensure_ascii=False))
if not r.get("success"):
    print("[FAIL] Envio WA fallo")
    sys.exit(1)
print("[OK] Prueba completada — revisa WhatsApp", tel[-10:])
PY
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
