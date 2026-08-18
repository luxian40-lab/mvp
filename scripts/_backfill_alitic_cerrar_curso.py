# -*- coding: utf-8 -*-
"""Backfill: cerrar curso 7 (Alitic) para quien ya tiene diploma WA en M8/M9."""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
django.setup()

from core.models import Estudiante
from core.models_certificados import Certificado
from core.certificado_presencial_service import (
    cerrar_curso_si_tramo_final,
    progreso_en_tramo_cierre,
)

CURSO_ID = 7
DRY = os.environ.get("DRY_RUN", "0") == "1"

certs = (
    Certificado.objects.filter(curso_id=CURSO_ID, emitido=True)
    .select_related("estudiante", "curso")
    .order_by("estudiante__nombre")
)
print("DRY_RUN", DRY, "certs", certs.count())

cerrados = omitidos = ya = pend_upd = 0
for cert in certs:
    est = cert.estudiante
    curso = cert.curso
    from core.models import ProgresoEstudiante

    prog = ProgresoEstudiante.objects.filter(estudiante=est, curso=curso).select_related("modulo_actual").first()
    mod = prog.modulo_actual.numero if prog and prog.modulo_actual_id else None
    en_tramo = progreso_en_tramo_cierre(prog, curso) if prog else False

    ctx = est.contexto_temporal or {}
    pend = ctx.get("cert_envio_pendiente")
    if pend and pend.get("curso_id") == CURSO_ID and not pend.get("cerrar_avance"):
        if not DRY:
            pend["cerrar_avance"] = True
            ctx["cert_envio_pendiente"] = pend
            est.contexto_temporal = ctx
            est.save(update_fields=["contexto_temporal"])
        pend_upd += 1
        print("PEND+cerrar_avance", est.id, est.nombre[:30])

    if not cert.enviado_whatsapp:
        print("SKIP no_wa", est.nombre[:30], "mod", mod, "pend", bool(pend))
        continue
    if not en_tramo:
        print("SKIP no_tramo", est.nombre[:30], "mod", mod, "completado", bool(prog and prog.completado))
        omitidos += 1
        continue
    if prog and prog.completado:
        print("SKIP ya_completo", est.nombre[:30])
        ya += 1
        continue

    if DRY:
        print("WOULD cerrar", est.nombre[:30], "mod", mod)
        cerrados += 1
        continue

    estado = cerrar_curso_si_tramo_final(est, curso)
    prog.refresh_from_db()
    print("CERRAR", estado, est.nombre[:30], "mod", mod, "->", prog.modulo_actual.numero if prog.modulo_actual_id else None, "completado", prog.completado)
    if estado == "cerrado":
        cerrados += 1
    elif estado == "ya_completo":
        ya += 1
    else:
        omitidos += 1

print("RESUMEN cerrados", cerrados, "omitidos", omitidos, "ya_completo", ya, "pend_actualizados", pend_upd)
if DRY:
    print("OK dry-run")
    sys.exit(0)
sys.exit(0 if cerrados >= 0 else 1)
