# -*- coding: utf-8 -*-
"""Course Engine — video único WA (escena + tarjeta + voz + subtítulos)."""
from pathlib import Path

from django.core.management.base import BaseCommand

from core.course_engine.local_store import local_runs_root
from core.course_engine.video_pilot_generator import FOCO_PILOTO_ERROR1, VideoPilotGenerator


class Command(BaseCommand):
    help = (
        'Course Engine piloto video único: brief → storyboard por segundos → '
        'escena Runway + tarjeta infográfica + TTS + subtítulos → un MP4 WA.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True)
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument('--modulo-id', type=int, default=None)
        parser.add_argument('--brief', type=str, default='')
        parser.add_argument('--brief-file', type=str, default='')
        parser.add_argument('--voice-id', type=str, default='')
        parser.add_argument('--foco', type=str, default='', help='Tema puntual del video (default: error 1)')
        parser.add_argument('--dry-run', action='store_true', help='Solo plan + manifest')
        parser.add_argument('--no-generate', action='store_true', help='Plan sin APIs de pago')
        parser.add_argument('--target-sec', type=float, default=14.0)
        parser.add_argument('--runway-duration', type=int, default=5)

    def handle(self, *args, **options):
        brief = options['brief']
        brief_file = (options.get('brief_file') or '').strip()
        if brief_file:
            brief = Path(brief_file).read_text(encoding='utf-8')

        if not brief.strip() and not options['modulo_id']:
            self.stderr.write(self.style.ERROR('Pasa --brief, --brief-file o --modulo-id'))
            raise SystemExit(1)

        foco = (options.get('foco') or '').strip() or FOCO_PILOTO_ERROR1

        gen = VideoPilotGenerator()
        out = gen.generar(
            cliente_id=options['cliente_id'],
            curso_id=options['curso_id'],
            modulo_id=options['modulo_id'],
            brief=brief,
            voice_id=options['voice_id'] or None,
            foco=foco,
            dry_run=options['dry_run'],
            generar_video=not options['no_generate'],
            target_sec=options['target_sec'],
            runway_duration_sec=options['runway_duration'],
        )

        for paso in out.pasos:
            self.stdout.write(paso)

        self.stdout.write(f'Run: {out.run_id} -> {local_runs_root() / out.run_id}')

        if out.plan:
            self.stdout.write(self.style.SUCCESS(f"Video: {out.plan.titulo}"))
            for s in out.plan.segmentos:
                self.stdout.write(
                    f'  [{s.orden:02d}] {s.tipo} {s.duracion_seg:.0f}s — {s.subtitulo or s.guion[:50]}'
                )

        if out.paso_wa:
            self.stdout.write('--- Envío WA sugerido (1 video) ---')
            self.stdout.write(f'  Caption: {out.paso_wa.caption}')
            if out.paso_wa.media_url:
                self.stdout.write(f'  Media: {out.paso_wa.media_url[:80]}…')

        self.stdout.write(
            f'Costo est.: ${out.costo_estimado_usd:.2f} | real: ${out.costo_real_usd:.2f}'
        )
        if out.manifest_path:
            self.stdout.write(f'Manifest: {out.manifest_path}')
        if out.video_local:
            self.stdout.write(f'Local: {out.video_local}')

        for err in out.errors:
            self.stdout.write(self.style.WARNING(err))

        if out.errors and not out.paso_wa:
            raise SystemExit(1)
