#!/bin/bash
# QA interno: audita + repara media WA en todos los cursos activos.
# Omite solo Impulso Joven Rural (curso 22) modulos 8 y 9.
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
import time

import django

django.setup()

from core.media_wa_audit import auditar_media_cursos, filas_a_dict
from core.models import Curso, PasoModulo
from core.module_steps import pasos_activos_qs
from core.modulo_publicacion import _head_url_ok
from core.twilio_media import (
    _descargar_bytes,
    _subir_bytes_s3,
    evaluar_mp4_listo_whatsapp,
    optimizar_mp4_bytes_whatsapp,
    probe_mp4_codecs,
)

SKIP_CURSO_MOD = {(22, 8), (22, 9)}  # Impulso M8/M9 — usuario regenera masters
TAG = int(time.time())

print("=== FASE 1: AUDITORIA (todos cursos activos) ===")
filas, resumen = auditar_media_cursos(solo_activos=True, head_urls=True, solo_riesgo=True)
print(
    f"Cursos: {resumen.cursos} | Media: {resumen.pasos_media} | "
    f"fail={resumen.fail} warn={resumen.warn} ok={resumen.ok}"
)
for cur_key, counts in sorted(resumen.por_curso.items()):
    if counts["fail"] or counts["warn"]:
        print(f"  {cur_key} -> fail={counts['fail']} warn={counts['warn']}")

audit_riesgo = filas_a_dict(filas)
print(f"Filas riesgo: {len(audit_riesgo)}")

print("\n=== FASE 2: REPARACION ===")
stats = {
    "video_ok": 0,
    "video_skip": 0,
    "video_fail": 0,
    "video_skip_impulso89": 0,
    "img_ok": 0,
    "img_fail": 0,
}
resultados = []


def skip_paso(curso_id, mod_num):
    return (curso_id, mod_num) in SKIP_CURSO_MOD


for curso in Curso.objects.filter(activo=True).order_by("nombre", "id"):
    for mod in curso.modulos.all().order_by("numero", "id"):
        if skip_paso(curso.id, mod.numero or 0):
            stats["video_skip_impulso89"] += sum(
                1
                for p in pasos_activos_qs(mod)
                if (p.media_url or "").lower().split("?")[0].endswith((".mp4", ".m4v", ".mov"))
            )
            continue
        for paso in pasos_activos_qs(mod):
            url = (paso.media_url or "").strip()
            if not url:
                continue
            low = url.lower().split("?")[0]

            if low.endswith((".mp4", ".m4v", ".mov")):
                gate = None
                raw = None
                if paso.media_wa_apto is True:
                    raw = _descargar_bytes(url)
                    if raw:
                        gate = evaluar_mp4_listo_whatsapp(raw)
                        if gate.get("apto"):
                            stats["video_skip"] += 1
                            continue

                print(
                    f"\nV P{paso.pk} C{curso.id} M{mod.numero} apto={paso.media_wa_apto} "
                    f"pub={mod.publicado_wa} ...{url[-55:]}"
                )
                if raw is None:
                    raw = _descargar_bytes(url)
                if not raw:
                    stats["video_fail"] += 1
                    resultados.append(
                        {
                            "paso_id": paso.pk,
                            "curso": curso.nombre,
                            "mod": mod.numero,
                            "ok": False,
                            "razon": "download",
                        }
                    )
                    continue
                if gate is None:
                    gate = evaluar_mp4_listo_whatsapp(raw)
                print("  before", probe_mp4_codecs(raw), gate.get("razon"), len(raw))
                fixed = optimizar_mp4_bytes_whatsapp(raw)
                gate2 = evaluar_mp4_listo_whatsapp(fixed or b"")
                print("  after", probe_mp4_codecs(fixed or b""), gate2.get("razon"), len(fixed or b""))
                if not fixed or not gate2.get("apto"):
                    stats["video_fail"] += 1
                    paso.media_wa_apto = False
                    paso.save(update_fields=["media_wa_apto"])
                    resultados.append(
                        {
                            "paso_id": paso.pk,
                            "curso": curso.nombre,
                            "mod": mod.numero,
                            "ok": False,
                            "razon": gate2.get("razon") or "encode",
                        }
                    )
                    continue
                digest = hashlib.sha1(f"qa-all-{TAG}-p{paso.pk}-{len(fixed)}".encode()).hexdigest()[:12]
                key = f"modulos/pasos/wa_safe/2026/08/repair_paso_{paso.pk}_{digest}_h264_main_faststart.mp4"
                new_url = _subir_bytes_s3(key, fixed, "video/mp4")
                if not new_url:
                    stats["video_fail"] += 1
                    resultados.append(
                        {
                            "paso_id": paso.pk,
                            "curso": curso.nombre,
                            "mod": mod.numero,
                            "ok": False,
                            "razon": "s3",
                        }
                    )
                    continue
                paso.media_url = new_url
                paso.media_wa_apto = True
                paso.save(update_fields=["media_url", "media_wa_apto"])
                stats["video_ok"] += 1
                resultados.append(
                    {
                        "paso_id": paso.pk,
                        "curso": curso.nombre,
                        "mod": mod.numero,
                        "ok": True,
                        "url": new_url,
                    }
                )
                print("  UPDATED", new_url[-70:])

            elif low.endswith((".jpg", ".jpeg", ".png", ".webp", ".pdf")):
                if paso.media_wa_apto is True:
                    continue
                head = _head_url_ok(url)
                if head is True:
                    paso.media_wa_apto = True
                    paso.save(update_fields=["media_wa_apto"])
                    stats["img_ok"] += 1
                    print(f"I P{paso.pk} C{curso.id} imagen apto=True")
                elif head is False:
                    paso.media_wa_apto = False
                    paso.save(update_fields=["media_wa_apto"])
                    stats["img_fail"] += 1
                    resultados.append(
                        {
                            "paso_id": paso.pk,
                            "curso": curso.nombre,
                            "mod": mod.numero,
                            "tipo": "img",
                            "ok": False,
                            "razon": "head_fail",
                        }
                    )

print("\n=== FASE 3: AUDITORIA POST ===")
_, resumen2 = auditar_media_cursos(solo_activos=True, head_urls=True, solo_riesgo=True)
print(
    f"POST fail={resumen2.fail} warn={resumen2.warn} ok={resumen2.ok} "
    f"(media total {resumen2.pasos_media})"
)

out = {
    "tag": TAG,
    "stats": stats,
    "pre_audit": {
        "fail": resumen.fail,
        "warn": resumen.warn,
        "ok": resumen.ok,
        "pasos_media": resumen.pasos_media,
    },
    "post_audit": {
        "fail": resumen2.fail,
        "warn": resumen2.warn,
        "ok": resumen2.ok,
        "pasos_media": resumen2.pasos_media,
    },
    "resultados": resultados,
    "fallos_restantes": filas_a_dict(
        auditar_media_cursos(solo_activos=True, head_urls=True, solo_riesgo=True)[0]
    ),
}
print("\nSTATS", json.dumps(stats))
print("FALLOS_RESTANTES", len(out["fallos_restantes"]))
for row in out["fallos_restantes"][:40]:
    print(
        f"  [{row['nivel']}] C{row['curso_id']} M{row['modulo_numero']} P{row['paso_id']} "
        f"{row.get('motivo')} pub={row['publicado_wa']}"
    )
verdict = "QA_PASS" if resumen2.fail == 0 else "QA_PARTIAL"
print(verdict)
PY
