# -*- coding: utf-8 -*-
"""QA smoke: plantilla certificado Alitic → OK → diploma (prod)."""
import os
import sys
import time
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")

_aws_key = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
_aws_bucket = (os.environ.get("AWS_STORAGE_BUCKET_NAME") or "").strip()
if not _aws_key or not _aws_bucket:
    print(
        "FAIL: faltan AWS_ACCESS_KEY_ID o AWS_STORAGE_BUCKET_NAME en el entorno. "
        "Use scripts/eb_smoke_cert_alitic.ps1 o source scripts/eb_env_prod.sh en EB."
    )
    sys.exit(10)

django.setup()

from core.models import Curso, Estudiante, ModuloCompletado, ProgresoEstudiante
from core.models_certificados import Certificado, PlantillaCertificado
from core.certificado_presencial_service import (
    crear_certificado_presencial,
    enviar_previo_whatsapp,
    marcar_cert_envio_pendiente,
)
from core.views import _procesar_twilio_webhook

PHONE_SUFFIX = "3026480629"
CONTENT_SID = "HX6b8ed985eee273c3850452c03608cfa9"
CURSO_ID = 7
SIMULAR_OK = os.environ.get("QA_SIMULAR_OK", "0") == "1"

tel = f"57{PHONE_SUFFIX}" if len(PHONE_SUFFIX) == 10 else PHONE_SUFFIX
est = (
    Estudiante.objects.filter(telefono=tel).first()
    or Estudiante.objects.filter(telefono__icontains=PHONE_SUFFIX).order_by("-id").first()
)
if not est:
    print("FAIL estudiante no encontrado", tel)
    sys.exit(1)

curso = Curso.objects.filter(pk=CURSO_ID).first()
if not curso:
    print("FAIL curso", CURSO_ID)
    sys.exit(1)

plantilla = (
    PlantillaCertificado.objects.filter(nombre__icontains="alitic").first()
    or PlantillaCertificado.objects.filter(pk=10).first()
)

prog = ProgresoEstudiante.objects.filter(estudiante=est, curso=curso).select_related("modulo_actual").first()
cert = Certificado.objects.filter(estudiante=est, curso=curso).first()

print("=== PRE ===")
print("est", est.id, est.nombre, est.telefono)
print("curso", curso.id, curso.nombre)
print("mod_actual", getattr(prog.modulo_actual, "numero", None) if prog else None)
print("cert_existente", cert.codigo_verificacion if cert else None, "emitido", bool(cert and cert.emitido))
print("content_sid", CONTENT_SID)
print("s3_bucket", _aws_bucket)

if not cert or not cert.emitido or not (cert.archivo_imagen and str(cert.archivo_imagen.name).startswith("certificados/generados/")):
    cert, estado = crear_certificado_presencial(
        est,
        curso,
        regenerar_si_existe=True,
        generar_archivo=True,
        plantilla=plantilla,
        permitir_otro_cliente=True,
    )
    print("cert_gen", estado, cert.codigo_verificacion if cert else None, "emitido", bool(cert and cert.emitido))
    if cert and cert.archivo_imagen:
        print("archivo_imagen", cert.archivo_imagen.name)

if not cert or not cert.emitido or not cert.archivo_imagen:
    print("FAIL no se pudo emitir certificado (revisar S3 PutObject y plantilla Alitic)")
    sys.exit(2)

res = enviar_previo_whatsapp(est, curso, twilio_content_sid=CONTENT_SID)
print("=== PLANTILLA ===")
print(res)

if not res.get("success"):
    print("FAIL plantilla no enviada", res.get("response"))
    sys.exit(3)

try:
    marcar_cert_envio_pendiente(est, cert, curso, cerrar_avance=False)
except TypeError:
    marcar_cert_envio_pendiente(est, cert, curso)
est.refresh_from_db()
print("pendiente", (est.contexto_temporal or {}).get("cert_envio_pendiente"))
print("mensaje_id", res.get("mensaje_id"))

if not SIMULAR_OK:
    print("OK plantilla enviada — responde OK en WhatsApp para recibir diploma")
    sys.exit(0)

sid = f"SM_qa_cert_{int(time.time() * 1000)}"
_procesar_twilio_webhook(
    {
        "Body": "OK",
        "From": f"whatsapp:+{tel}",
        "To": "whatsapp:+573202948806",
        "MessageSid": sid,
        "NumMedia": "0",
    }
)
time.sleep(3)
est.refresh_from_db()
cert.refresh_from_db()
if prog:
    prog.refresh_from_db()

pend_after = (est.contexto_temporal or {}).get("cert_envio_pendiente")
mods = list(
    ModuloCompletado.objects.filter(progreso=prog).values_list("modulo__numero", flat=True)
) if prog else []

print("=== POST OK ===")
print("pendiente_limpio", pend_after is None)
print("cert_enviado_wa", cert.enviado_whatsapp)
print("completado", bool(prog and prog.completado))
print("mod_actual", getattr(prog.modulo_actual, "numero", None) if prog else None)
print("mods_completados", sorted(mods))

if pend_after:
    print("FAIL pendiente sigue activo")
    sys.exit(4)
if not cert.enviado_whatsapp:
    print("FAIL cert no marcado enviado_whatsapp")
    sys.exit(5)

print("QA_PASS smoke cert Alitic OK")
