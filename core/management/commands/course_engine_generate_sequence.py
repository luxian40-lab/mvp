# -*- coding: utf-8 -*-
"""Secuencia interactiva Course Engine — RAG + bloques texto/micro_video para WhatsApp."""
from pathlib import Path

from django.core.management.base import BaseCommand

from core.course_engine.interactive_generator import InteractiveSequenceGenerator
from core.course_engine.local_store import local_runs_root


class Command(BaseCommand):
    help = (
        'Course Engine secuencia interactiva: RAG + brief largo → plan de bloques '
        'texto/micro_video (manifest pasos WA). No concatena en un solo video plano.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True)
        parser.add_argument('--curso-id', type=int, required=True)
        parser.add_argument('--modulo-id', type=int, default=None)
        parser.add_argument('--brief', type=str, default='')
        parser.add_argument(
            '--brief-file',
            type=str,
            default='',
            help='Archivo UTF-8 con capítulo o manual completo',
        )
        parser.add_argument('--voice-id', type=str, default='')
        parser.add_argument('--dry-run', action='store_true', help='Solo plan + manifest (sin Runway)')
        parser.add_argument('--max-bloques', type=int, default=12)
        parser.add_argument('--max-micro-videos', type=int, default=6)
        parser.add_argument(
            '--generate-videos',
            type=int,
            default=0,
            help='Cuántos micro_video generar con Runway (0=solo plan). Piloto: 2',
        )
        parser.add_argument('--runway-duration', type=int, default=8, help='Segundos Runway por clip (2-10)')

    def handle(self, *args, **options):
        brief = options['brief']
        brief_file = (options.get('brief_file') or '').strip()
        if brief_file:
            brief = Path(brief_file).read_text(encoding='utf-8')

        if not brief.strip() and not options['modulo_id']:
            self.stderr.write(self.style.ERROR('Pasa --brief, --brief-file o --modulo-id'))
            raise SystemExit(1)

        gen = InteractiveSequenceGenerator()
        out = gen.generar(
            cliente_id=options['cliente_id'],
            curso_id=options['curso_id'],
            modulo_id=options['modulo_id'],
            brief=brief,
            voice_id=options['voice_id'] or None,
            dry_run=options['dry_run'],
            max_bloques=options['max_bloques'],
            max_micro_videos=options['max_micro_videos'],
            generar_micro_videos=options['generate_videos'],
            runway_duration_sec=options['runway_duration'],
        )

        for paso in out.pasos:
            self.stdout.write(paso)

        self.stdout.write(f'Run: {out.run_id} -> {local_runs_root() / out.run_id}')

        if out.secuencia:
            self.stdout.write(self.style.SUCCESS(f"Lección: {out.secuencia.titulo_leccion}"))
            for b in out.secuencia.bloques:
                tag = b.tipo.upper()
                preview = (b.guion[:60] + '…') if len(b.guion) > 60 else b.guion
                self.stdout.write(f'  [{b.orden:02d}] {tag} {b.titulo}: {preview}')

        self.stdout.write('--- Pasos WhatsApp sugeridos ---')
        for p in out.pasos_wa:
            media = ' + video' if p.media_url else ''
            preview = p.contenido if len(p.contenido) <= 80 else p.contenido[:80] + '…'
            self.stdout.write(f'  Paso {p.orden} [{p.tipo}]{media}: {preview}')

        self.stdout.write(
            f'Costo est.: ${out.costo_estimado_usd:.2f} | real: ${out.costo_real_usd:.2f}'
        )
        if out.manifest_path:
            self.stdout.write(f'Manifest: {out.manifest_path}')

        for err in out.errors:
            self.stdout.write(self.style.WARNING(err))

        if out.errors and not out.pasos_wa:
            raise SystemExit(1)
