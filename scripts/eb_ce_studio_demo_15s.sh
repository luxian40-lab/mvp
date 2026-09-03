#!/bin/bash
# Demo 15s con el MISMO pipeline del Course Engine Studio (VideoPilotGenerator,
# modo_demo) + gate eki_wa_v1 + envio QA WhatsApp.
# Valida de paso que se usa la voz elegida en el curso, no la default del entorno.
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_NUMBER TWILIO_PHONE_NUMBER TWILIO_WHATSAPP_FROM AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME OPENAI_API_KEY RUNWAY_API_KEY ELEVENLABS_API_KEY ELEVENLABS_VOICE_ID; do
  export "$key=$($GC environment -k $key 2>/dev/null)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
export COURSE_ENGINE_LOCAL_DIR=/tmp/course_engine/runs
cd /var/app/current
source /var/app/venv/*/bin/activate

export TEL_QA="${TEL_QA:-573026480629}"
export CE_CURSO_ID="${CE_CURSO_ID:-22}"

python3 <<'PY'
import json
import os
import subprocess
import sys

import django

django.setup()

from core.course_engine.video_pilot_generator import VideoPilotGenerator
from core.course_engine.voice_config import label_voz, resolver_voice_id_curso
from core.models import Curso
from core.twilio_media import evaluar_mp4_listo_whatsapp, _descargar_bytes

curso_id = int(os.environ.get("CE_CURSO_ID", "22"))
curso = Curso.objects.filter(pk=curso_id).first()
if not curso or not curso.cliente_id:
    print(f"[FAIL] Curso {curso_id} inexistente o sin cliente")
    sys.exit(1)

voz_esperada = resolver_voice_id_curso(curso)
print(f"Curso: {curso.nombre} (cliente={curso.cliente_id})")
print(f"Voz del curso: {label_voz(voz_esperada) or voz_esperada or 'default entorno'}")

brief = os.environ.get("CE_BRIEF", "").strip() or (
    "Tres claves de finanzas rurales para jovenes del campo: separa los gastos del "
    "hogar y del cultivo, guarda un fondo de emergencia y registra cada peso que "
    "entra y sale del emprendimiento."
)

gen = VideoPilotGenerator()
# Sin modulo_id a proposito: es el caso que antes ignoraba la voz del curso.
out = gen.generar(
    cliente_id=curso.cliente_id,
    curso_id=curso.id,
    brief=brief,
    foco=os.environ.get("CE_FOCO", ""),
    modo_demo=True,
    target_sec=14.0,
    max_duracion_seg=15.0,
)

for p in out.pasos:
    print(p)
print(f"Costo estimado USD: {out.costo_estimado_usd}")
print(f"Errores: {out.errors}")

# Gate 1: la voz usada debe ser la del curso
if voz_esperada and out.voice_id != voz_esperada:
    print(f"[FAIL] Voz usada {out.voice_id!r} != voz del curso {voz_esperada!r}")
    sys.exit(1)
print(f"[OK] Voz aplicada: {label_voz(out.voice_id) or out.voice_id}")

url = (out.paso_wa.media_url if out.paso_wa else "") or ""
local = out.video_local
print(f"Video S3: {url}")
print(f"Video local: {local}")
if not url and not local:
    print("[FAIL] Sin video generado")
    sys.exit(1)

raw = b""
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
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", "-"],
        input=raw,
        capture_output=True,
    )
    if dur.returncode == 0:
        segundos = float(dur.stdout.decode().strip())
        print(f"Duracion ffprobe: {segundos:.1f}s")
        if segundos > 16.0:
            print(f"[FAIL] Demo excede 15s (+1s tolerancia): {segundos:.1f}s")
            sys.exit(1)

if not url:
    print("[WARN] Sin URL S3 - no se envia WA")
    sys.exit(0)

from core.utils import enviar_whatsapp_twilio

tel = os.environ.get("TEL_QA", "573026480629")
msg = (
    "[eki QA] Course Engine Studio - demo 15s. "
    f"Voz: {label_voz(out.voice_id) or 'default'}. "
    "Si se ve y se escucha bien, responde OK."
)
r = enviar_whatsapp_twilio(tel, msg, media_url=url.strip())
print("WA send:", json.dumps(r, ensure_ascii=False))
if not r.get("success"):
    print("[FAIL] Envio WA fallo")
    sys.exit(1)
print("[OK] Demo enviado - revisa WhatsApp", tel[-10:])
PY
