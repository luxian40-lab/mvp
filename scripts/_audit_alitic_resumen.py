# -*- coding: utf-8 -*-
"""Auditoría resumen curso 7 Alitic: certificado + progreso."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
django.setup()

from core.models import ProgresoEstudiante, ModuloCompletado
from core.models_certificados import Certificado

CURSO_ID = 7

certs = (
    Certificado.objects.filter(curso_id=CURSO_ID, emitido=True)
    .select_related("estudiante")
    .order_by("estudiante__nombre")
)
print(f"{'NOMBRE':<35} {'MOD':>3} {'PND':>3} {'WA':>3} {'COMP':>5} {'M8':>3} {'M9':>3}")
print("-" * 60)
tot = comp = wa = 0
for cert in certs:
    est = cert.estudiante
    prog = (
        ProgresoEstudiante.objects.filter(estudiante=est, curso_id=CURSO_ID)
        .select_related("modulo_actual")
        .first()
    )
    mod = prog.modulo_actual.numero if prog and prog.modulo_actual_id else "-"
    completado = bool(prog and prog.completado)
    m8 = m9 = "-"
    if prog:
        nums = set(
            ModuloCompletado.objects.filter(progreso=prog)
            .values_list("modulo__numero", flat=True)
        )
        m8 = "Y" if 8 in nums else "N"
        m9 = "Y" if 9 in nums else "N"
    ctx = est.contexto_temporal or {}
    pend = ctx.get("cert_envio_pendiente")
    pend_ok = "Y" if pend and pend.get("curso_id") == CURSO_ID else "N"
    w = "Y" if cert.enviado_whatsapp else "N"
    tot += 1
    comp += int(completado)
    wa += int(cert.enviado_whatsapp)
    print(
        f"{est.nombre[:35]:<35} {str(mod):>3} {pend_ok:>3} {w:>3} {str(completado):>5} {m8:>3} {m9:>3}"
    )
print("-" * 60)
print(f"TOTAL {tot} | diploma_wa={wa} | completado={comp}/{tot}")
