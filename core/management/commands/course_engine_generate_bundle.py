# -*- coding: utf-8 -*-
"""Genera paquete mixto por modulo (video + infografia + podcast segun curso)."""
from django.core.management.base import BaseCommand

from core.course_engine.bundle_generator import CourseBundleGenerator
from core.course_engine.format_config import FORMAT_CHOICES, describe_formato
from core.course_engine.local_store import local_runs_root
from core.models import Curso


class Command(BaseCommand):
    help = (
        'Course Engine bundle: 1 modulo → MP4 + PNG + MP3 segun '
        'course_engine_format del curso (RAG + misma leccion).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True)
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument('--modulo-id', type=int, default=None)
        parser.add_argument('--brief', type=str, default='')
        parser.add_argument('--voice-id', type=str, default='')
        parser.add_argument('--tier', type=str, default='', help='Override tier video')
        parser.add_argument(
            '--formato',
            type=str,
            default='',
            choices=[c[0] for c in FORMAT_CHOICES],
            help='Override formato del curso',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        curso = Curso.objects.filter(pk=options['curso_id']).first()
        if curso:
            self.stdout.write(describe_formato(curso))

        gen = CourseBundleGenerator()
        out = gen.generar(
            cliente_id=options['cliente_id'],
            curso_id=options['curso_id'],
            modulo_id=options['modulo_id'],
            brief=options['brief'],
            dry_run=options['dry_run'],
            voice_id=options['voice_id'] or None,
            tier_override=options['tier'] or None,
            formato_override=options['formato'] or None,
        )

        for paso in out.pasos:
            self.stdout.write(paso)

        self.stdout.write(f'Run: {out.run_id} -> {local_runs_root() / out.run_id}')
        self.stdout.write(f'Costo est.: ${out.costo_estimado_usd:.2f} | real: ${out.costo_real_usd:.2f}')

        for asset in sorted(out.assets, key=lambda a: a.paso_orden):
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Paso {asset.paso_orden} [{asset.tipo}] {asset.label}: {asset.url or asset.local_path}'
                )
            )

        if out.manifest_path:
            self.stdout.write(f'Manifest: {out.manifest_path}')

        for err in out.errors:
            self.stdout.write(self.style.WARNING(err))

        if out.errors and not out.assets and not options['dry_run']:
            raise SystemExit(1)
