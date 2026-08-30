# -*- coding: utf-8 -*-
"""Smoke Runway — genera unos segundos de video IA (image-to-video o text-to-video)."""
from pathlib import Path

from django.core.management.base import BaseCommand

from core.course_engine.local_store import local_runs_root
from core.course_engine.runway_service import (
    generar_video_desde_imagen,
    generar_video_desde_texto,
    runway_disponible,
    ultimo_error_runway,
)


class Command(BaseCommand):
    help = (
        'Prueba Runway Dev API: 4s de video IA. '
        'Requiere RUNWAY_API_KEY en .env (https://dev.runwayml.com). '
        'Modo imagen: --imagen + --prompt. Modo texto: --texto solo.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--imagen',
            type=str,
            default='',
            help='Ruta PNG/JPG keyframe (o usa imagen del ultimo run con --use-last-run)',
        )
        parser.add_argument(
            '--use-last-run',
            action='store_true',
            help='Usa escena_02 PNG del run mas reciente en tmp/course_engine/runs/',
        )
        parser.add_argument(
            '--prompt',
            type=str,
            default='Movimiento suave de camara sobre plantacion de cafe, luz natural',
        )
        parser.add_argument(
            '--texto',
            type=str,
            default='',
            help='Si se pasa, usa text-to-video (gen4.5) en lugar de image-to-video',
        )
        parser.add_argument('--duration', type=int, default=4, help='Segundos (2-10)')
        parser.add_argument(
            '--model',
            type=str,
            default='',
            help='Override modelo Runway (gen4_turbo, gen4.5, veo3.1_fast, ...)',
        )

    def handle(self, *args, **options):
        if not runway_disponible():
            self.stderr.write(
                self.style.ERROR(
                    'RUNWAY_API_KEY no configurada. '
                    'Crea cuenta en https://dev.runwayml.com -> API Keys -> agrega RUNWAY_API_KEY al .env'
                )
            )
            raise SystemExit(1)

        run_dir = local_runs_root() / 'runway_smoke'
        run_dir.mkdir(parents=True, exist_ok=True)

        texto = (options['texto'] or '').strip()
        model = options['model'] or None
        dur = options['duration']

        if texto:
            self.stdout.write(f'Text-to-video ({dur}s): {texto[:80]}...')
            result = generar_video_desde_texto(
                prompt=texto,
                run_dir=run_dir,
                nombre='smoke_text',
                duration_sec=dur,
                model=model,
            )
        else:
            img_path: Path | None = None
            if options['use_last_run']:
                runs = sorted(local_runs_root().glob('*/images/escena_02_*.png'), key=lambda p: p.stat().st_mtime)
                if runs:
                    img_path = runs[-1]
                    self.stdout.write(f'Keyframe: {img_path}')
            if options['imagen']:
                img_path = Path(options['imagen'])
            if not img_path or not img_path.is_file():
                self.stderr.write(
                    self.style.ERROR('Pasa --imagen ruta.png o --use-last-run')
                )
                raise SystemExit(1)

            self.stdout.write(f'Image-to-video ({dur}s): {options["prompt"][:80]}...')
            result = generar_video_desde_imagen(
                prompt=options['prompt'],
                run_dir=run_dir,
                escena_orden=1,
                local_image=img_path,
                duration_sec=dur,
                model=model,
            )

        if not result:
            detail = ultimo_error_runway() or 'revisar logs'
            self.stderr.write(self.style.ERROR(f'Runway fallo — {detail}'))
            raise SystemExit(1)

        size_mb = result.local_path.stat().st_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS('Runway OK'))
        self.stdout.write(f'Task: {result.task_id} | model: {result.model}')
        self.stdout.write(f'Video local: {result.local_path} ({size_mb:.2f} MB)')
        self.stdout.write(f'Costo est.: ${result.cost_usd:.2f}')
        if result.source_url:
            self.stdout.write(f'URL temporal Runway: {result.source_url[:120]}...')
