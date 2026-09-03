#!/bin/bash
# Repara MP4 Impulso Joven Rural (curso 22) — omite módulos 8 y 9.
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
eval "$(sudo "$GC" environment | python3 -c 'import json,shlex,sys; [print(f"export {k}={shlex.quote(str(v))}") for k,v in json.load(sys.stdin).items()]')"
cd /var/app/current
source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
python3 <<'PY'
import hashlib
import json

import django

django.setup()

from core.models import Curso, PasoModulo
from core.module_steps import pasos_activos_qs
from core.twilio_media import (
    _descargar_bytes,
    _subir_bytes_s3,
    evaluar_mp4_listo_whatsapp,
    optimizar_mp4_bytes_whatsapp,
    probe_mp4_codecs,
)

CURSO_ID = 22
SKIP_MOD_NUMS = {8, 9}

curso = Curso.objects.get(pk=CURSO_ID)
print("=== REPAIR", curso.id, curso.nombre, "skip mod", sorted(SKIP_MOD_NUMS), "===")

stats = {"video_ok": 0, "video_skip": 0, "video_fail": 0}
resultados = []

for mod in curso.modulos.all().order_by("numero", "id"):
    if mod.numero in SKIP_MOD_NUMS:
        print(f"\n--- SKIP modulo {mod.numero}: {mod.titulo} ---")
        continue
    for paso in pasos_activos_qs(mod):
        url = (paso.media_url or "").strip()
        if not url:
            continue
        low = url.lower().split("?")[0]
        if not low.endswith((".mp4", ".m4v", ".mov")):
            continue
        print(f"\nP{paso.pk} M{mod.numero} apto={paso.media_wa_apto} ...{url[-70:]}")
        raw = _descargar_bytes(url)
        if not raw:
            print("  DOWNLOAD FAIL")
            stats["video_fail"] += 1
            resultados.append({"paso_id": paso.pk, "mod": mod.numero, "ok": False, "razon": "download"})
            continue
        gate = evaluar_mp4_listo_whatsapp(raw)
        if gate.get("apto") and paso.media_wa_apto is True:
            print("  SKIP already apto")
            stats["video_skip"] += 1
            resultados.append({"paso_id": paso.pk, "mod": mod.numero, "ok": True, "skipped": True, "url": url})
            continue
        print("  before", probe_mp4_codecs(raw), gate.get("razon"), len(raw))
        fixed = optimizar_mp4_bytes_whatsapp(raw)
        gate2 = evaluar_mp4_listo_whatsapp(fixed or b"")
        print("  after", probe_mp4_codecs(fixed or b""), gate2.get("razon"), len(fixed or b""))
        if not fixed or not gate2.get("apto"):
            stats["video_fail"] += 1
            resultados.append({"paso_id": paso.pk, "mod": mod.numero, "ok": False, "razon": gate2.get("razon")})
            print("  FAIL encode")
            continue
        digest = hashlib.sha1(f"repair-c{CURSO_ID}-p{paso.pk}-{len(fixed)}".encode()).hexdigest()[:12]
        key = f"modulos/pasos/wa_safe/2026/08/repair_paso_{paso.pk}_{digest}_h264_main_faststart.mp4"
        new_url = _subir_bytes_s3(key, fixed, "video/mp4")
        if not new_url:
            stats["video_fail"] += 1
            resultados.append({"paso_id": paso.pk, "mod": mod.numero, "ok": False, "razon": "s3"})
            print("  FAIL S3")
            continue
        paso.media_url = new_url
        paso.media_wa_apto = True
        paso.save(update_fields=["media_url", "media_wa_apto"])
        stats["video_ok"] += 1
        resultados.append({"paso_id": paso.pk, "mod": mod.numero, "ok": True, "url": new_url})
        print("  UPDATED", new_url)

print("\nSTATS", json.dumps(stats))
print(json.dumps(resultados, ensure_ascii=False, indent=2))
print("REPAIR_OK" if stats["video_fail"] == 0 else "REPAIR_PARTIAL")
PY
