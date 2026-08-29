# -*- coding: utf-8 -*-
"""Pipeline Course Engine local — RAG → lección → storyboard → assets (ElevenLabs)."""
import json

from django.core.management.base import BaseCommand

from core.course_engine.local_store import local_runs_root
from core.course_engine.pipeline import ejecutar_pipeline_local


class Command(BaseCommand):
    help = (
        'Ejecuta Course Engine en local (NO prod). '
        'RAG empresa → OpenAI → storyboard → narración ElevenLabs → tmp/course_engine/'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True)
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument(
            '--brief',
            type=str,
            required=True,
            help='Tema o objetivo de la lección',
        )
        parser.add_argument('--modelo', type=str, default='gpt-4o-mini')
        parser.add_argument(
            '--hasta',
            type=str,
            default='assets',
            choices=['rag', 'lesson', 'analysis', 'storyboard', 'assets', 'compose'],
            help='Detener pipeline en este paso',
        )
        parser.add_argument(
            '--sin-audio',
            action='store_true',
            help='Omitir ElevenLabs/OpenAI TTS (solo JSON/storyboard)',
        )
        parser.add_argument('--json', action='store_true', help='Salida JSON completa')

    def handle(self, *args, **options):
        run = ejecutar_pipeline_local(
            cliente_id=options['cliente_id'],
            curso_id=options['curso_id'],
            brief=options['brief'],
            modelo=options['modelo'],
            generar_audio=not options['sin_audio'],
            hasta_paso=options['hasta'],
        )

        if options['json']:
            self.stdout.write(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS(f'Run {run.run_id} guardado en {local_runs_root() / run.run_id}'))
        if run.lesson:
            self.stdout.write(f'Lección: {run.lesson.titulo}')
        if run.storyboard:
            self.stdout.write(f'Escenas: {len(run.storyboard.escenas)}')
            for s in run.storyboard.escenas:
                audio = '🔊' if s.asset_url else '—'
                self.stdout.write(f'  {s.orden}. [{s.tipo.value}] {s.titulo} {audio}')
        if run.errors:
            for e in run.errors:
                self.stdout.write(self.style.WARNING(e))
        if run.video_url:
            self.stdout.write(f'Video: {run.video_url}')
