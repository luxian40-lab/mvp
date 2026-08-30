# -*- coding: utf-8 -*-
"""QA smoke — muestra TTS ~5 s (ElevenLabs Voice ID)."""
from django.core.management.base import BaseCommand

from core.course_engine.voice_preview import generar_muestra_voz
from core.models import Curso, Modulo


class Command(BaseCommand):
    help = 'Genera muestra de voz Course Engine (~5 s) para QA — curso, modulo o voice-id directo.'

    def add_arguments(self, parser):
        parser.add_argument('--voice-id', type=str, default='', help='ElevenLabs Voice ID directo')
        parser.add_argument('--curso-id', type=int, default=None)
        parser.add_argument('--modulo-id', type=int, default=None)
        parser.add_argument('--label', type=str, default='', help='Etiqueta visible en salida')

    def handle(self, *args, **options):
        voice_id = (options['voice_id'] or '').strip()
        label = (options['label'] or '').strip()

        if options['modulo_id']:
            modulo = Modulo.objects.select_related('curso').filter(pk=options['modulo_id']).first()
            if not modulo:
                self.stderr.write(self.style.ERROR('Modulo no encontrado'))
                raise SystemExit(1)
            voice_id = voice_id or modulo.get_course_engine_voice_id() or ''
            if not label:
                from core.course_engine.voice_config import resolver_voice_label_modulo
                label = resolver_voice_label_modulo(modulo)
            self.stdout.write(f'Modulo {modulo.pk}: {modulo.titulo} | tier={modulo.get_course_engine_tier()}')

        elif options['curso_id']:
            curso = Curso.objects.filter(pk=options['curso_id']).first()
            if not curso:
                self.stderr.write(self.style.ERROR('Curso no encontrado'))
                raise SystemExit(1)
            from core.course_engine.voice_config import resolver_voice_id_curso
            voice_id = voice_id or resolver_voice_id_curso(curso) or ''
            label = label or curso.course_engine_voice_label or curso.nombre
            self.stdout.write(f'Curso {curso.pk}: {curso.nombre} | tier={curso.course_engine_tier}')

        if not voice_id:
            self.stderr.write(
                self.style.ERROR('Pasa --voice-id, --curso-id o --modulo-id con Voice ID configurado')
            )
            raise SystemExit(1)

        out = generar_muestra_voz(voice_id, voice_label=label or voice_id)
        if not out.ok:
            self.stderr.write(self.style.ERROR(f'QA_FAIL muestra voz: {out.error}'))
            raise SystemExit(1)

        tts = out.tts
        self.stdout.write(self.style.SUCCESS('QA_PASS muestra voz'))
        self.stdout.write(f'Voice ID: {out.voice_id}')
        self.stdout.write(f'Etiqueta: {out.voice_label}')
        self.stdout.write(f'Provider: {tts.provider} | bytes: {tts.bytes_size}')
        self.stdout.write(f'URL MP3: {tts.url}')
