# Envío QA del video Course Engine 15s ya generado (sin regenerar).
param(
    [string]$Environment = "eki-prod-final",
    [string]$TelQa = "573026480629",
    [string]$VideoUrl = "https://eki-produccion.s3.us-east-2.amazonaws.com/media/course_engine/videos/wa_safe/e4138caee748_h264_main_faststart.mp4"
)

. "$PSScriptRoot\_eb_env_prod_bash.ps1"

$bash = @"
$(Get-EbEnvProdBash)
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
cd /var/app/current && source /var/app/venv/*/bin/activate
python3 <<'PY'
import json
import os
import subprocess
import django
django.setup()
from core.twilio_media import evaluar_mp4_listo_whatsapp, _descargar_bytes
from core.utils import enviar_whatsapp_twilio

url = "$VideoUrl"
tel = "$TelQa"
raw = _descargar_bytes(url) or b""
gate = evaluar_mp4_listo_whatsapp(raw)
print("Gate WA:", json.dumps(gate, ensure_ascii=False))
dur = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", "-"],
    input=raw, capture_output=True,
)
if dur.returncode == 0:
    print(f"Duracion: {float(dur.stdout.decode().strip()):.1f}s")
msg = "[eki QA] Prueba Course Engine 15s — finanzas rurales. Si ves el video con buena calidad, responde OK."
r = enviar_whatsapp_twilio(tel, msg, media_url=url)
print("WA send:", json.dumps(r, ensure_ascii=False))
if not r.get("success"):
    raise SystemExit(1)
print("[OK] Enviado a", tel[-10:])
PY
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
