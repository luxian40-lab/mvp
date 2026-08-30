# -*- coding: utf-8 -*-
"""Genera video completo de una lección (Fase 2A — sin Runway)."""
from django.core.management.base import BaseCommand

from core.course_engine.local_store import local_runs_root
from core.course_engine.video_generator import CourseVideoGenerator


class Command(BaseCommand):
    help = (
        'CourseVideoGenerator: RAG → storyboard → DALL-E + ElevenLabs + ffmpeg → MP4. '
        'Tier economico por defecto (sin video IA / Runway).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True)
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument('--brief', type=str, required=True)
        parser.add_argument(
            '--tier',
            type=str,
            default='economico',
            choices=['economico', 'estandar', 'premium'],
        )
        parser.add_argument('--modelo', type=str, default='gpt-4o-mini')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo storyboard + costo estimado (sin DALL-E/TTS/ffmpeg)',
        )

    def handle(self, *args, **options):
        gen = CourseVideoGenerator()
        out = gen.generar(
            cliente_id=options['cliente_id'],
            curso_id=options['curso_id'],
            brief=options['brief'],
            tier=options['tier'],
            modelo=options['modelo'],
            dry_run=options['dry_run'],
        )

        for paso in out.pasos:
            self.stdout.write(paso)

        self.stdout.write(f'Run: {out.run.run_id} → {local_runs_root() / out.run.run_id}')
        self.stdout.write(f'Costo est.: ${out.costo_estimado_usd:.2f} | real (imágenes): ${out.costo_real_usd:.2f}')

        if out.video_local:
            self.stdout.write(self.style.SUCCESS(f'Video local: {out.video_local}'))
        if out.run.video_url:
            self.stdout.write(self.style.SUCCESS(f'Video S3: {out.run.video_url}'))

        for err in out.run.errors:
            self.stdout.write(self.style.WARNING(err))

        if out.run.errors and not out.video_local and not options['dry_run']:
            raise SystemExit(1)
