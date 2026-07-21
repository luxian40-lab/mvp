"""Crea o actualiza un certificado de prueba con codigo fijo (verificacion publica)."""

from datetime import date

from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante
from core.models_certificados import Certificado

CODIGO_DEMO = "eki-DEMO-PRUE-BA01"
CEDULA_DEMO = "9000000001"
TELEFONO_DEMO = "573009998877"


class Command(BaseCommand):
    help = (
        "Upsert certificado de prueba "
        f"({CODIGO_DEMO}) para https://certificados.eki.technology/"
    )

    def handle(self, *args, **options):
        # Evitar rebuild de base de conocimientos al crear curso demo
        try:
            from core.signals_conocimientos import curso_actualizado
            post_save.disconnect(curso_actualizado, sender=Curso)
            reconnect = True
        except Exception:
            reconnect = False
            curso_actualizado = None

        try:
            cliente, _ = Cliente.objects.get_or_create(
                nit="900000000-DEMO",
                defaults={
                    "nombre": "eki Demo Verificacion",
                    "contacto_principal": "Equipo eki",
                    "email": "demo-cert@eki.technology",
                    "telefono": "573000000000",
                    "activo": True,
                },
            )
            curso, _ = Curso.objects.get_or_create(
                cliente=cliente,
                nombre="Curso demo verificacion de certificados",
                defaults={
                    "descripcion": "Curso ficticio solo para probar la pagina publica de QR.",
                    "activo": True,
                },
            )
            est = Estudiante.objects.filter(cedula=CEDULA_DEMO).first()
            if est is None:
                est = Estudiante.objects.filter(telefono=TELEFONO_DEMO).first()
            if est is None:
                est = Estudiante.objects.create(
                    cedula=CEDULA_DEMO,
                    nombre="Maria Demo Verificacion",
                    telefono=TELEFONO_DEMO,
                    cliente=cliente,
                    estado_chat="ACTIVO",
                    acepto_terminos=True,
                    activo=True,
                )
            else:
                est.nombre = "Maria Demo Verificacion"
                est.cliente = cliente
                est.cedula = CEDULA_DEMO
                est.telefono = TELEFONO_DEMO
                est.activo = True
                est.save(update_fields=["nombre", "cliente", "cedula", "telefono", "activo"])

            cert = Certificado.objects.filter(
                codigo_verificacion__iexact=CODIGO_DEMO
            ).first()
            if cert is None:
                cert = Certificado(
                    codigo_verificacion=CODIGO_DEMO,
                    estudiante=est,
                    curso=curso,
                    calificacion_final=95,
                    fecha_inicio=date(2026, 1, 15),
                    fecha_completado=date(2026, 3, 20),
                    emitido=True,
                    fecha_emision=timezone.now(),
                )
                cert.save()
                creado = True
            else:
                cert.estudiante = est
                cert.curso = curso
                cert.calificacion_final = 95
                cert.fecha_inicio = date(2026, 1, 15)
                cert.fecha_completado = date(2026, 3, 20)
                cert.emitido = True
                if not cert.fecha_emision:
                    cert.fecha_emision = timezone.now()
                cert.save()
                creado = False

            url = cert.obtener_url_verificacion()
            self.stdout.write(self.style.SUCCESS(
                f"{'Creado' if creado else 'Actualizado'}: {cert.codigo_verificacion}"
            ))
            self.stdout.write(f"URL: {url}")
        finally:
            if reconnect and curso_actualizado is not None:
                post_save.connect(curso_actualizado, sender=Curso)
