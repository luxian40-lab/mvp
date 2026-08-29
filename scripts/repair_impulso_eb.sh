#!/bin/bash
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

from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from core.models import Curso, Estudiante, PasoModulo, WhatsappLog
from core.module_steps import pasos_activos_qs
from core.media_wa_audit import _head_url_ok
from core.twilio_media import (
    _descargar_bytes,
    _subir_bytes_s3,
    evaluar_mp4_listo_whatsapp,
    optimizar_mp4_bytes_whatsapp,
    probe_mp4_codecs,
)

CURSO_ID = 22
TODOS_VIDEOS = True

curso = Curso.objects.get(pk=CURSO_ID)
print("=== REPAIR", curso.id, curso.nombre, "===")

# --- logs fallos inscritos ---
desde = timezone.now() - timedelta(days=90)
tels = list(
    Estudiante.objects.filter(progresos__curso_id=CURSO_ID)
    .values_list("telefono", flat=True)
    .distinct()
)
print(f"Inscritos tel distintos: {len(tels)}")
q_tel = Q()
for t in tels:
    if t:
        q_tel |= Q(telefono__endswith=str(t)[-10:])
fallos = (
    WhatsappLog.objects.filter(q_tel, tipo="SENT", fecha__gte=desde)
    .filter(
        Q(estado__iexact="undelivered")
        | Q(estado__iexact="failed")
        | Q(error_detalle__icontains="63021")
        | Q(error_detalle__icontains="63019")
    )
    .order_by("-fecha")[:30]
)
print(f"--- Fallos WA 90d: {fallos.count()} ---")
for log in fallos:
    print(
        log.fecha.strftime("%Y-%m-%d %H:%M"),
        (log.telefono or "")[-10:],
        log.estado,
        (log.error_detalle or "")[:60],
        ((log.mensaje or "")[:80]).replace("\n", " "),
    )

stats = {"video_ok": 0, "video_skip": 0, "video_fail": 0, "img_ok": 0}
resultados = []

for mod in curso.modulos.all().order_by("numero", "id"):
    for paso in pasos_activos_qs(mod):
        url = (paso.media_url or "").strip()
        if not url:
            continue
        low = url.lower().split("?")[0]
        if low.endswith((".mp4", ".m4v", ".mov")):
            print(f"\nP{paso.pk} M{mod.numero} apto={paso.media_wa_apto} ...{url[-65:]}")
            raw = _descargar_bytes(url)
            if not raw:
                print("  DOWNLOAD FAIL")
                stats["video_fail"] += 1
                continue
            gate = evaluar_mp4_listo_whatsapp(raw)
            if gate.get("apto") and paso.media_wa_apto is True and not TODOS_VIDEOS:
                print("  SKIP ok")
                stats["video_skip"] += 1
                continue
            print("  before", probe_mp4_codecs(raw), gate.get("razon"), len(raw))
            fixed = optimizar_mp4_bytes_whatsapp(raw)
            gate2 = evaluar_mp4_listo_whatsapp(fixed or b"")
            print("  after", probe_mp4_codecs(fixed or b""), gate2.get("razon"), len(fixed or b""))
            if not fixed or not gate2.get("apto"):
                stats["video_fail"] += 1
                resultados.append({"paso_id": paso.pk, "ok": False})
                print("  FAIL encode")
                continue
            digest = hashlib.sha1(f"repair-c{CURSO_ID}-p{paso.pk}-{len(fixed)}".encode()).hexdigest()[:12]
            key = f"modulos/pasos/wa_safe/2026/08/repair_paso_{paso.pk}_{digest}_h264_main_faststart.mp4"
            new_url = _subir_bytes_s3(key, fixed, "video/mp4")
            if not new_url:
                stats["video_fail"] += 1
                print("  FAIL S3")
                continue
            paso.media_url = new_url
            paso.media_wa_apto = True
            paso.save(update_fields=["media_url", "media_wa_apto"])
            stats["video_ok"] += 1
            resultados.append({"paso_id": paso.pk, "ok": True, "url": new_url})
            print("  UPDATED", new_url[-75:])
        elif low.endswith((".jpg", ".jpeg", ".png", ".webp", ".pdf")):
            if paso.media_wa_apto is True:
                continue
            if _head_url_ok(url) is False:
                print(f"P{paso.pk} imagen HEAD fail")
                continue
            paso.media_wa_apto = True
            paso.save(update_fields=["media_wa_apto"])
            stats["img_ok"] += 1
            print(f"P{paso.pk} imagen apto=True")

print("\nSTATS", json.dumps(stats))
print(json.dumps(resultados, ensure_ascii=False, indent=2))
print("REPAIR_OK" if stats["video_fail"] == 0 else "REPAIR_FAIL")
PY
