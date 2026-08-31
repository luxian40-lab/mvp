# -*- coding: utf-8 -*-
"""Genera video completo de una leccion (Course Engine)."""
from django.core.management.base import BaseCommand

from core.course_engine.local_store import local_runs_root
from core.course_engine.video_generator import CourseVideoGenerator


class Command(BaseCommand):
    help = (
        'CourseVideoGenerator: RAG -> storyboard -> imagenes + ElevenLabs + Runway + ffmpeg -> MP4. '
        'Use --modulo-id para tier y voice_id del curso/modulo.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True)
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument('--brief', type=str, default='')
        parser.add_argument('--modulo-id', type=int, default=None, help='Herencia tier + ElevenLabs Voice ID')
        parser.add_argument('--voice-id', type=str, default='', help='Override Voice ID ElevenLabs')
        parser.add_argument(
            '--tier',
            type=str,
            default='economico',
            choices=['economico', 'estandar', 'premium'],
            help='Ignorado si --modulo-id (usa tier del modulo/curso)',
        )
        parser.add_argument('--modelo', type=str, default='gpt-4o-mini')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo storyboard + costo estimado (sin APIs de pago)',
        )
        parser.add_argument(
            '--profile',
            type=str,
            default='default',
            choices=['default', 'documental'],
            help='documental = foto real + Runway gen4_turbo (menos look IA)',
        )
        parser.add_argument(
            '--runway-duration',
            type=int,
            default=5,
            help='Segundos Runway por clip (2-10, default 5)',
        )
        parser.add_argument(
            '--micro-realista',
            action='store_true',
            help='Solo 1 clip corto: keyframe documental + Runway + ElevenLabs (muy real)',
        )

    def handle(self, *args, **options):
        brief = options['brief']
        if not brief.strip() and not options['modulo_id']:
            self.stderr.write(self.style.ERROR('Pasa --brief o --modulo-id'))
            raise SystemExit(1)

        visual_style = (options.get('profile') or 'default').strip()
        if visual_style == 'default':
            visual_style = ''
        if options.get('micro_realista') and not visual_style:
            visual_style = 'documental'

        gen = CourseVideoGenerator()
        out = gen.generar(
            cliente_id=options['cliente_id'],
            curso_id=options['curso_id'],
            brief=brief,
            tier=options['tier'],
            modelo=options['modelo'],
            dry_run=options['dry_run'],
            modulo_id=options['modulo_id'],
            voice_id=options['voice_id'] or None,
            visual_style=visual_style,
            runway_duration_sec=options['runway_duration'],
            micro_realista=options['micro_realista'],
        )

        for paso in out.pasos:
            self.stdout.write(paso)

        self.stdout.write(f'Run: {out.run.run_id} -> {local_runs_root() / out.run.run_id}')
        self.stdout.write(f'Costo est.: ${out.costo_estimado_usd:.2f} | real (imagenes): ${out.costo_real_usd:.2f}')

        if out.video_local:
            self.stdout.write(self.style.SUCCESS(f'Video local: {out.video_local}'))
        if out.run.video_url:
            self.stdout.write(self.style.SUCCESS(f'Video S3: {out.run.video_url}'))

        for err in out.run.errors:
            self.stdout.write(self.style.WARNING(err))

        if out.run.errors and not out.video_local and not options['dry_run']:
            raise SystemExit(1)
