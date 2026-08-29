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
"""Intento agresivo de rescate M8/M9 + logs ampliados Impulso."""
import hashlib
import os
import subprocess
import tempfile

import django

django.setup()

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import Estudiante, PasoModulo, WhatsappLog
from core.twilio_media import (
    _descargar_bytes,
    _subir_bytes_s3,
    evaluar_mp4_listo_whatsapp,
    probe_mp4_codecs,
)

TARGETS = {
    243: "https://eki-produccion.s3.us-east-2.amazonaws.com/modulos/pasos/wa_safe/2026/08/modulo_154_20260809201433_0233_h264_main_faststart.mp4",
    245: "https://eki-produccion.s3.us-east-2.amazonaws.com/modulos/pasos/wa_safe/2026/08/modulo_155_20260818175603_026_h264_main_faststart.mp4",
    248: "https://eki-produccion.s3.us-east-2.amazonaws.com/modulos/pasos/wa_safe/2026/08/modulo_155_20260818194632_29_h264_main_faststart.mp4",
}


def ffmpeg_rescue(raw: bytes) -> bytes | None:
    """Varias pasadas agresivas cuando el bitstream está dañado."""
    src = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    dst = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    src.write(raw)
    src.close()
    dst.close()
    attempts = [
        [
            "ffmpeg", "-y", "-err_detect", "ignore_err",
            "-fflags", "+genpts+igndts+discardcorrupt",
            "-i", src.name,
            "-map", "0:v:0", "-an",
            "-c:v", "libx264", "-profile:v", "main", "-level", "3.1",
            "-pix_fmt", "yuv420p", "-vf", "scale=min(iw\\,720):-2",
            "-preset", "veryfast", "-crf", "28",
            "-movflags", "+faststart", dst.name,
        ],
        [
            "ffmpeg", "-y", "-err_detect", "ignore_err",
            "-fflags", "+genpts+igndts+discardcorrupt",
            "-i", src.name,
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
            "-pix_fmt", "yuv420p", "-vf", "scale=640:-2,fps=24",
            "-preset", "veryfast", "-crf", "30",
            "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-ar", "44100",
            "-shortest", "-movflags", "+faststart", dst.name,
        ],
        [
            "ffmpeg", "-y", "-err_detect", "ignore_err",
            "-fflags", "+genpts+igndts+discardcorrupt",
            "-i", src.name,
            "-vn", "-c:a", "aac", "-b:a", "64k", "-ac", "1",
            "/tmp/_audio_only_tmp.aac",
        ],
    ]
    best = None
    try:
        for i, cmd in enumerate(attempts[:2]):
            print("  try", i, " ".join(cmd[-8:]))
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                print("   fail rc", r.returncode, (r.stderr or "")[-200:])
                continue
            with open(dst.name, "rb") as f:
                out = f.read()
            gate = evaluar_mp4_listo_whatsapp(out)
            print("   out", len(out), probe_mp4_codecs(out), gate.get("razon"))
            if gate.get("apto") and len(out) > 200_000:
                best = out
                break
            if out and (best is None or len(out) > len(best)):
                best = out
    finally:
        for p in (src.name, dst.name):
            try:
                os.unlink(p)
            except OSError:
                pass
    return best


# --- logs ampliados ---
desde = timezone.now() - timedelta(days=120)
tels = list(
    Estudiante.objects.filter(progresos__curso_id=22)
    .values_list("telefono", flat=True)
    .distinct()
)
print("Inscritos", len(tels))
q = Q()
for t in tels:
    if t:
        q |= Q(telefono__endswith=str(t)[-10:])

# Cualquier fallo SENT
fallos = WhatsappLog.objects.filter(q, tipo="SENT", fecha__gte=desde).exclude(
    estado__iexact="delivered"
).exclude(estado__iexact="read").exclude(estado__iexact="sent").order_by("-fecha")[:40]
print("Fallos no-delivered/read/sent:", fallos.count())
for log in fallos[:20]:
    print(
        log.fecha.strftime("%Y-%m-%d"),
        (log.telefono or "")[-10:],
        log.estado,
        (log.error_detalle or "")[:70],
        ((log.mensaje or "")[:60]).replace("\n", " "),
    )

# Cualquier 630xx en todos los logs (no solo inscritos)
g = WhatsappLog.objects.filter(
    fecha__gte=desde
).filter(
    Q(error_detalle__icontains="63021") | Q(error_detalle__icontains="63019")
).order_by("-fecha")[:25]
print("\nGlobal 63019/63021 120d:", g.count())
for log in g:
    print(
        log.fecha.strftime("%Y-%m-%d"),
        (log.telefono or "")[-10:],
        (log.error_detalle or "")[:80],
    )

print("\n=== RESCATE M8/M9 ===")
for pid, url in TARGETS.items():
    print("\nP", pid)
    raw = _descargar_bytes(url)
    if not raw:
        print(" download fail")
        continue
    print(" before", probe_mp4_codecs(raw), len(raw))
    fixed = ffmpeg_rescue(raw)
    if not fixed:
        print(" rescue fail")
        continue
    gate = evaluar_mp4_listo_whatsapp(fixed)
    print(" gate", gate)
    if not gate.get("apto"):
        print(" still not apto — needs master reupload")
        continue
    digest = hashlib.sha1(f"rescue-{pid}-{len(fixed)}".encode()).hexdigest()[:12]
    key = f"modulos/pasos/wa_safe/2026/08/repair_paso_{pid}_{digest}_h264_main_faststart.mp4"
    new_url = _subir_bytes_s3(key, fixed, "video/mp4")
    if not new_url:
        print(" s3 fail")
        continue
    p = PasoModulo.objects.get(id=pid)
    p.media_url = new_url
    p.media_wa_apto = True
    p.save(update_fields=["media_url", "media_wa_apto"])
    print(" UPDATED", new_url)

print("\nDONE_RESCUE")
PY
