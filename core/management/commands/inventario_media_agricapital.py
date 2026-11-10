# -*- coding: utf-8 -*-
"""S0 AgriCapital: lista cursos y MB de media (solo ese cliente)."""
import json

from django.core.management.base import BaseCommand

from core.lineas.agricapital_inventario import inventariar_media_agricapital, resumenes_a_dict
from core.lineas.registro_agricapital import cliente_id_configurado


class Command(BaseCommand):
    help = (
        'Inventario de media de cursos AgriCapital (MB por curso). '
        'Requiere EKI_AGRICAPITAL_CLIENTE_ID. No envía WhatsApp.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sin-head',
            action='store_true',
            help='No pide Content-Length por HTTP (solo lista URLs)',
        )
        parser.add_argument('--json', action='store_true', help='Salida JSON')

    def handle(self, *args, **options):
        cliente_id = cliente_id_configurado()
        if cliente_id is None:
            self.stderr.write(
                self.style.ERROR(
                    'EKI_AGRICAPITAL_CLIENTE_ID vacío: no hay AgriCapital configurado.'
                )
            )
            return

        resumenes = inventariar_media_agricapital(head_urls=not options['sin_head'])
        if options['json']:
            self.stdout.write(
                json.dumps(
                    {
                        'cliente_id': cliente_id,
                        'cursos': resumenes_a_dict(resumenes),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        self.stdout.write(
            f'\n=== INVENTARIO MEDIA AGRICAPITAL (cliente {cliente_id}) ===\n'
            f'Cursos: {len(resumenes)}\n'
        )
        if not resumenes:
            self.stdout.write('Sin cursos en el carrusel / activos de AgriCapital.')
            return

        total_mb = 0.0
        for cur in resumenes:
            total_mb += cur.mb_conocidos
            self.stdout.write(
                f'• [{cur.curso_id}] {cur.curso_nombre}: '
                f'{cur.archivos} archivo(s), '
                f'{cur.mb_conocidos} MB conocidos'
                + (f', {cur.sin_tamano} sin tamaño' if cur.sin_tamano else '')
            )
            for fila in cur.filas:
                tam = f'{fila.mb} MB' if fila.mb is not None else (fila.error or '?')
                self.stdout.write(f'    - {fila.origen} {fila.ref}: {tam}')

        self.stdout.write(
            self.style.SUCCESS(
                f'\nTotal MB conocidos (suma de cursos): {round(total_mb, 2)} MB'
            )
        )
