# -*- coding: utf-8 -*-
"""Activa videos WA ya listos (media_wa_apto=True) que quedaron inactivos."""
from django.core.management.base import BaseCommand

from core.media_pasos_listos import reparar_curso_videos_wa_inactivos
from core.models import Curso


class Command(BaseCommand):
    help = (
        'Activa PasoModulo con MP4 ya apto para WhatsApp que están inactivos. '
        'No recodifica. No envía WhatsApp.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--reset-progreso',
            action='store_true',
            help=(
                'Reinicia el índice de pasos de estudiantes que están en un '
                'módulo tocado y aún no lo completaron.'
            ),
        )

    def handle(self, *args, **options):
        curso_id = options['curso_id']
        try:
            curso = Curso.objects.get(pk=curso_id)
        except Curso.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Curso {curso_id} no existe'))
            return

        from core.media_pasos_listos import contar_videos_wa_listos_inactivos

        n_antes = sum(contar_videos_wa_listos_inactivos(m) for m in curso.modulos.all())
        self.stdout.write(
            f'=== ACTIVAR VIDEOS LISTOS {curso.id} {curso.nombre} inactivos={n_antes} ==='
        )
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'DRY-RUN activaría {n_antes} video(s)'))
            return

        stats = reparar_curso_videos_wa_inactivos(
            curso, reset_progreso=options['reset_progreso'],
        )
        self.stdout.write(
            f'ACTIVADOS pasos={stats["pasos"]} modulos={stats["modulos"]} '
            f'progresos_reset={stats["progresos_reset"]}'
        )
        if stats['pasos']:
            self.stdout.write(self.style.SUCCESS('OK'))
        else:
            self.stdout.write('Nada que activar')
