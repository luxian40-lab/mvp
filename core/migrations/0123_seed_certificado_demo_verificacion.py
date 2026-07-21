# Generated manually — seed certificado demo de verificación pública

from datetime import date

from django.db import migrations
from django.utils import timezone


CODIGO = "eki-DEMO-PRUE-BA01"
NIT = "900000000-DEMO"
CEDULA = "9000000001"
TELEFONO = "573009998877"


def seed_demo(apps, schema_editor):
    Cliente = apps.get_model("core", "Cliente")
    Curso = apps.get_model("core", "Curso")
    Estudiante = apps.get_model("core", "Estudiante")
    Certificado = apps.get_model("core", "Certificado")

    cliente = Cliente.objects.filter(nit=NIT).first()
    if cliente is None:
        cliente = Cliente.objects.create(
            nombre="eki Demo Verificacion",
            nit=NIT,
            contacto_principal="Equipo eki",
            email="demo-cert@eki.technology",
            telefono="573000000000",
            activo=True,
        )

    curso = Curso.objects.filter(
        cliente=cliente,
        nombre="Curso demo verificacion de certificados",
    ).first()
    if curso is None:
        curso = Curso.objects.create(
            cliente=cliente,
            nombre="Curso demo verificacion de certificados",
            descripcion="Curso ficticio solo para probar la pagina publica de QR.",
            activo=True,
        )

    est = Estudiante.objects.filter(cedula=CEDULA).first()
    if est is None:
        est = Estudiante.objects.filter(telefono=TELEFONO).first()
    if est is None:
        est = Estudiante.objects.create(
            cedula=CEDULA,
            nombre="Maria Demo Verificacion",
            telefono=TELEFONO,
            cliente=cliente,
            estado_chat="ACTIVO",
            acepto_terminos=True,
            activo=True,
        )
    else:
        est.nombre = "Maria Demo Verificacion"
        est.cliente = cliente
        est.cedula = CEDULA
        est.telefono = TELEFONO
        est.activo = True
        est.save(update_fields=["nombre", "cliente", "cedula", "telefono", "activo"])

    cert = Certificado.objects.filter(codigo_verificacion__iexact=CODIGO).first()
    if cert is None:
        Certificado.objects.create(
            codigo_verificacion=CODIGO,
            estudiante=est,
            curso=curso,
            calificacion_final=95,
            fecha_inicio=date(2026, 1, 15),
            fecha_completado=date(2026, 3, 20),
            emitido=True,
            fecha_emision=timezone.now(),
        )
    else:
        cert.estudiante = est
        cert.curso = curso
        cert.calificacion_final = 95
        cert.emitido = True
        if not cert.fecha_emision:
            cert.fecha_emision = timezone.now()
        cert.save()


def unseed_demo(apps, schema_editor):
    Certificado = apps.get_model("core", "Certificado")
    Certificado.objects.filter(codigo_verificacion__iexact=CODIGO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0122_estudiante_evento_aprendizaje"),
    ]

    operations = [
        migrations.RunPython(seed_demo, unseed_demo),
    ]
