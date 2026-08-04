"""Asegura plantilla de certificado por defecto (diseño eki Pillow)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models_certificados import PlantillaCertificado


NOMBRE_DEFAULT = 'eki diseño por defecto'


class Command(BaseCommand):
    help = (
        'Crea o marca como por_defecto la plantilla modo diseno_eki '
        '(evita el fallback S3/simple que se ve mal).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué haría',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        qs = PlantillaCertificado.objects.filter(activa=True).order_by('-por_defecto', 'nombre')
        self.stdout.write(f'Plantillas activas: {qs.count()}')
        for p in qs[:20]:
            self.stdout.write(
                f'  id={p.pk} por_defecto={p.por_defecto} modo={p.modo_plantilla} · {p.nombre}'
            )

        bueno = (
            PlantillaCertificado.objects.filter(
                activa=True, modo_plantilla='diseno_eki', por_defecto=True,
            ).first()
            or PlantillaCertificado.objects.filter(
                activa=True, modo_plantilla='diseno_eki', nombre__icontains='eki',
            ).first()
            or PlantillaCertificado.objects.filter(activa=True, modo_plantilla='diseno_eki').first()
        )

        if bueno:
            self.stdout.write(self.style.SUCCESS(
                f'Usando plantilla id={bueno.pk} «{bueno.nombre}» (diseno_eki)'
            ))
            if not bueno.por_defecto and not dry:
                bueno.por_defecto = True
                bueno.save()
                self.stdout.write(self.style.SUCCESS('Marcada por_defecto=True'))
            elif bueno.por_defecto:
                self.stdout.write('Ya es por_defecto.')
        else:
            self.stdout.write('No hay diseno_eki activa — creando…')
            if dry:
                self.stdout.write(f'[dry-run] crearía «{NOMBRE_DEFAULT}»')
                return
            bueno = PlantillaCertificado.objects.create(
                nombre=NOMBRE_DEFAULT,
                descripcion='Plantilla Pillow eki (nombre, curso, fecha, QR).',
                modo_plantilla='diseno_eki',
                activa=True,
                por_defecto=True,
                color_primario='#5F3A6E',
                color_secundario='#9A6CAC',
            )
            self.stdout.write(self.style.SUCCESS(f'Creada id={bueno.pk}'))

        # Prueba de render
        from core.certificado_diseno_eki import render_certificado_diseno_eki

        buf = render_certificado_diseno_eki(
            plantilla=bueno,
            nombre_estudiante='MARÍA GONZÁLEZ PÉREZ',
            curso_nombre='Curso de prueba eki',
            codigo_verificacion='eki-TEST-PREVIEW',
        )
        n = len(buf.getvalue()) if buf else 0
        if n > 5_000:
            self.stdout.write(self.style.SUCCESS(f'Preview OK ({n} bytes PNG)'))
        else:
            self.stdout.write(self.style.WARNING(f'Preview sospechoso ({n} bytes)'))
