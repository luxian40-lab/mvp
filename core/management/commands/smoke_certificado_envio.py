"""
Emite (o regenera) certificado para un estudiante y lo envía por WhatsApp.
Uso (prod/local con Twilio):

  python manage.py smoke_certificado_envio --telefono 573026480629 --force

Si el estudiante no tiene progreso completado, crea/usa un curso demo corto
y marca el progreso como completado para disparar la emisión.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils import timezone


class Command(BaseCommand):
    help = 'Genera certificado + envía por WhatsApp (smoke fin de curso).'

    def add_arguments(self, parser):
        parser.add_argument('--telefono', required=True, help='E.164 sin +, ej. 573026480629')
        parser.add_argument('--force', action='store_true', help='Regenerar PNG/PDF aunque ya exista')
        parser.add_argument(
            '--sin-envio',
            action='store_true',
            help='Solo generar/verificar, no enviar WhatsApp',
        )

    def handle(self, *args, **options):
        from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
        from core.models_certificados import Certificado
        from core.certificado_service import (
            crear_certificado_automatico,
            enviar_certificado_whatsapp,
            generar_y_guardar_certificado,
        )

        tel = ''.join(c for c in str(options['telefono']) if c.isdigit())
        if tel.startswith('0'):
            tel = '57' + tel.lstrip('0')
        if len(tel) == 10:
            tel = '57' + tel

        est = Estudiante.objects.filter(telefono=tel).first()
        if not est:
            self.stderr.write(self.style.ERROR(f'No hay estudiante con teléfono {tel}'))
            return

        # Preferir curso con progreso; si no, crear demo mínimo
        prog = (
            ProgresoEstudiante.objects.filter(estudiante=est)
            .select_related('curso')
            .order_by('-fecha_inicio')
            .first()
        )
        if prog and prog.curso:
            curso = prog.curso
        else:
            try:
                from core.signals_conocimientos import curso_actualizado
                post_save.disconnect(curso_actualizado, sender=Curso)
                reconnect = True
            except Exception:
                reconnect = False
                curso_actualizado = None
            try:
                cliente = est.cliente or Cliente.objects.filter(activo=True).first()
                if not cliente:
                    cliente = Cliente.objects.create(
                        nombre='Smoke Cert',
                        nit='900SMOKE-1',
                        contacto_principal='Ops',
                        email='smoke@eki.technology',
                        telefono='573000000001',
                        activo=True,
                    )
                    est.cliente = cliente
                    est.save(update_fields=['cliente'])
                curso, _ = Curso.objects.get_or_create(
                    cliente=cliente,
                    nombre='Curso smoke certificado',
                    defaults={'descripcion': 'Smoke E2E certificado', 'activo': True, 'duracion_semanas': 2},
                )
                if not Modulo.objects.filter(curso=curso).exists():
                    Modulo.objects.create(curso=curso, numero=1, titulo='Módulo 1')
                prog, _ = ProgresoEstudiante.objects.get_or_create(
                    estudiante=est,
                    curso=curso,
                    defaults={
                        'completado': True,
                        'fecha_inicio': timezone.now() - timedelta(days=14),
                        'fecha_completado': timezone.now(),
                    },
                )
            finally:
                if reconnect and curso_actualizado:
                    post_save.connect(curso_actualizado, sender=Curso)

        if prog and not prog.completado:
            prog.completado = True
            prog.fecha_completado = timezone.now()
            prog.save(update_fields=['completado', 'fecha_completado'])

        cert = Certificado.objects.filter(estudiante=est, curso=curso).first()
        if not cert:
            cert = crear_certificado_automatico(est, curso)
        if not cert:
            # Fallback directo si elegibilidad bloquea en smoke
            cert = Certificado.objects.create(
                estudiante=est,
                curso=curso,
                calificacion_final=90,
                fecha_inicio=(timezone.now() - timedelta(days=14)).date(),
                fecha_completado=date.today(),
            )

        ok = generar_y_guardar_certificado(cert, force=bool(options['force']))
        cert.refresh_from_db()
        self.stdout.write(
            f'codigo={cert.codigo_verificacion} generado={ok} '
            f'png={bool(cert.archivo_imagen)} pdf={bool(cert.archivo_pdf)} '
            f'hash={(cert.hash_sha256 or "")[:12]} org={cert.organizacion_emisora!r}'
        )
        self.stdout.write(f'verificar={cert.obtener_url_verificacion()}')

        if options['sin_envio']:
            self.stdout.write(self.style.WARNING('Sin envío (--sin-envio)'))
            return

        enviado = enviar_certificado_whatsapp(cert)
        if enviado:
            self.stdout.write(self.style.SUCCESS(f'WhatsApp OK → {tel}'))
        else:
            self.stderr.write(self.style.ERROR(f'WhatsApp FALLÓ → {tel}'))
