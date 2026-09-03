# -*- coding: utf-8 -*-
"""Genera y guarda MP3 demo de las 4 voces eki en static/course_engine/voices/."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.course_engine.tts import generar_narracion_archivo
from core.course_engine.voice_config import catalogo_voces
from core.course_engine.voice_demos import _static_demo_rel, demo_slug_for_voice_id
from core.course_engine.voice_preview import MUESTRA_VOZ_TEXTO


class Command(BaseCommand):
    help = 'Genera MP3 demo (~5 s) de cada voz del catálogo Course Engine → static/course_engine/voices/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerar aunque el archivo ya exista',
        )

    def handle(self, *args, **options):
        force = bool(options.get('force'))
        base = Path(settings.BASE_DIR) / 'static' / 'course_engine' / 'voices'
        base.mkdir(parents=True, exist_ok=True)

        ok = err = skip = 0
        for v in catalogo_voces():
            vid = v['id']
            slug = demo_slug_for_voice_id(vid)
            dest = base / f'{slug}.mp3'
            rel = _static_demo_rel(slug)

            if dest.is_file() and not force:
                self.stdout.write(f'SKIP {v["label"]} → {rel} (ya existe; --force para regenerar)')
                skip += 1
                continue

            self.stdout.write(f'Generando {v["label"]} ({vid})…')
            out = generar_narracion_archivo(
                MUESTRA_VOZ_TEXTO,
                dest,
                voice=vid,
            )
            if out and dest.is_file():
                self.stdout.write(self.style.SUCCESS(f'OK {rel} ({dest.stat().st_size} bytes)'))
                ok += 1
            else:
                self.stderr.write(self.style.ERROR(f'FAIL {v["label"]} — revise ELEVENLABS_API_KEY'))
                err += 1

        self.stdout.write('')
        if ok:
            self.stdout.write(self.style.SUCCESS(f'Listo: {ok} demo(s) en static/course_engine/voices/'))
        if skip:
            self.stdout.write(f'{skip} omitida(s).')
        if err:
            raise SystemExit(1)
