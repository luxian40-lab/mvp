# -*- coding: utf-8 -*-
"""Smoke TTS — ElevenLabs (default) u OpenAI."""
from django.core.management.base import BaseCommand

from core.course_engine.tts import generar_narracion, ultimo_error_tts


class Command(BaseCommand):
    help = 'Genera narración de prueba (ElevenLabs por defecto) y muestra URL S3.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--texto',
            type=str,
            default='Hola, soy eki. Esta es una narración de prueba para el campo.',
        )
        parser.add_argument(
            '--provider',
            type=str,
            choices=['elevenlabs', 'openai'],
            default=None,
            help='Override COURSE_ENGINE_TTS_PROVIDER',
        )
        parser.add_argument('--voice', type=str, default=None, help='Voice ID ElevenLabs u OpenAI voice name')

    def handle(self, *args, **options):
        kwargs = {}
        if options['provider']:
            kwargs['provider'] = options['provider']
        if options['voice']:
            kwargs['voice'] = options['voice']

        result = generar_narracion(options['texto'], **kwargs)
        if not result:
            detail = ultimo_error_tts() or 'revisar API keys y logs'
            self.stderr.write(self.style.ERROR(f'TTS falló — {detail}'))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f'TTS OK ({result.provider})'))
        self.stdout.write(f'URL: {result.url}')
        self.stdout.write(f'Voice: {result.voice} | bytes: {result.bytes_size}')
