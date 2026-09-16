#!/bin/bash
# Microcapsula emergencia incendios forestales (~20s) — QA WhatsApp only.
# Plan fijo (no LLM fallback Error1). No muta modulos/cursos.
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

from core.course_engine import video_pilot_generator as vpg_mod
from core.course_engine.video_pilot_generator import VideoPilotGenerator
from core.course_engine.video_storyboard import SegmentoStoryboard, VideoLeccionPlan
from core.course_engine.voice_config import label_voz, resolver_voice_id_curso
from core.models import Curso
from core.twilio_media import evaluar_mp4_listo_whatsapp, _descargar_bytes
from core.utils import enviar_whatsapp_twilio
from core.utils_telefono import normalizar_telefono

tel = normalizar_telefono(os.environ.get("TEL_QA", "573026480629"))
if not str(tel).endswith("3026480629"):
    print("[FAIL] Solo permitido QA 3026480629")
    sys.exit(1)

curso_id = int(os.environ.get("CE_CURSO_ID", "22"))
curso = Curso.objects.filter(pk=curso_id).select_related("cliente").first()
if not curso or not curso.cliente_id:
    print(f"[FAIL] Curso {curso_id} inexistente o sin cliente")
    sys.exit(1)

print(f"Curso ancla (sin mutar): {curso.nombre} id={curso.id}")
voz = resolver_voice_id_curso(curso)
print(f"Voz: {label_voz(voz) or voz or 'default'}")

plan = VideoLeccionPlan(
    titulo="Que hacer ante un incendio forestal",
    objetivo="Aplicar alerta 123, alejarse y protegerse del humo ante incendio forestal",
    categoria_visual="agro",
    duracion_objetivo_seg=20.0,
    guion_completo=(
        "Si ves humo o fuego, no intentes enfrentarlo. Alejate rapidamente hacia una zona segura "
        "y avisa al 123, indicando tu ubicacion. Protegete del humo cubriendo nariz y boca. "
        "Sigue siempre las indicaciones de Bomberos y autoridades. "
        "Recuerda: primero tu vida, despues el fuego."
    ),
    segmentos=[
        SegmentoStoryboard(
            orden=1,
            tipo="escena",
            duracion_seg=5.0,
            guion="Si ves humo o fuego, no intentes enfrentarlo.",
            subtitulo="Ves humo o fuego?",
            escena_visual=(
                "Documentary photo: Andean rural hills at dawn with soft morning haze over forest canopy, "
                "Tolima Colombia landscape, calm light, no flames, photorealistic."
            ),
        ),
        SegmentoStoryboard(
            orden=2,
            tipo="tarjeta",
            duracion_seg=5.0,
            guion="Alejate rapidamente hacia una zona segura y no intentes apagarlo.",
            subtitulo="No intentes apagarlo.",
            tarjeta_titulo="No seas heroe",
            tarjeta_puntos=[
                "No intentes apagarlo",
                "Alejate a zona segura",
                "Alerta al 123",
            ],
            escena_visual=(
                "Person walking calmly away on a rural dirt road toward safety, "
                "green hills behind, Colombia countryside, photorealistic documentary."
            ),
        ),
        SegmentoStoryboard(
            orden=3,
            tipo="escena",
            duracion_seg=5.0,
            guion="Avisa al 123 e indica tu ubicacion.",
            subtitulo="Alerta al 123 y da tu ubicacion.",
            escena_visual=(
                "Close-up of a hand holding a smartphone with keypad visible, "
                "outdoor rural background, soft daylight, photorealistic."
            ),
        ),
        SegmentoStoryboard(
            orden=4,
            tipo="escena_cierre",
            duracion_seg=5.0,
            guion=(
                "Protegete del humo cubriendo nariz y boca. Sigue a Bomberos y autoridades. "
                "Primero tu vida, despues el fuego."
            ),
            subtitulo="Alejate, protege nariz y boca.",
            escena_visual=(
                "Family walking together on a rural road, light scarves covering nose and mouth "
                "from dusty air, calm documentary style, Colombian countryside hills."
            ),
        ),
    ],
)

# Evita fallback Error1 del planificador LLM
vpg_mod.planificar_video_leccion = lambda *a, **k: plan

brief = (
    "Microcapsula emergencia incendios forestales Tolima. "
    "No seas heroe: alerta, alejate y protege la vida."
)
foco = (
    "Emergencia incendios: reportar 123, no apagar, proteger nariz y boca, alejarse."
)

gen = VideoPilotGenerator()
out = gen.generar(
    cliente_id=curso.cliente_id,
    curso_id=curso.id,
    brief=brief,
    foco=foco,
    voice_id=voz or None,
    modo_demo=True,
    target_sec=20.0,
    max_duracion_seg=21.0,
    runway_duration_sec=5,
)

for p in out.pasos:
    print(p)
print(f"Errores: {out.errors}")
if out.plan:
    print(f"Plan: {out.plan.titulo} segs={len(out.plan.segmentos)}")

url = (out.paso_wa.media_url if out.paso_wa else "") or ""
local = out.video_local
print(f"Video S3: {url}")
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
        print(f"Duracion ffprobe: {float(dur.stdout.decode().strip()):.1f}s")

if not url:
    print("[WARN] Sin URL S3")
    sys.exit(0)

caption = (
    "Que hacer ante un incendio forestal?\n\n"
    "Si ves humo o fuego, no intentes enfrentarlo. Alejate hacia una zona segura y avisa al 123 "
    "con tu ubicacion. Cubre nariz y boca. Sigue a Bomberos y autoridades.\n\n"
    "Recuerda: primero tu vida, despues el fuego.\n\n"
    "[eki QA] Microcapsula emergencia Tolima — solo prueba."
)
r = enviar_whatsapp_twilio(tel, caption, media_url=url.strip())
print("WA send:", json.dumps(r, ensure_ascii=False))
if not r.get("success"):
    print("[FAIL] Envio WA fallo")
    sys.exit(1)
print("[OK] Microcapsula incendio enviada a", tel[-10:])
PY
