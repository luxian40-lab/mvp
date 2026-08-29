# -*- coding: utf-8 -*-
"""Smoke TTS outbound — texto → MP3 S3 (sin envío WA)."""
from django.core.management.base import BaseCommand

from core.course_engine.tts_service import generar_audio_tts


class Command(BaseCommand):
    help = 'Genera audio TTS de prueba y muestra URL S3 (Course Engine).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--texto',
            type=str,
            default='Hola, soy eki. Este es un audio de prueba para WhatsApp.',
        )
        parser.add_argument('--voz', type=str, default='nova')
        parser.add_argument('--model', type=str, default='tts-1')

    def handle(self, *args, **options):
        texto = options['texto']
        self.stdout.write(f'Texto ({len(texto)} chars): {texto[:80]}…')

        result = generar_audio_tts(
            texto,
            voice=options['voz'],
            model=options['model'],
        )
        if not result:
            self.stderr.write(self.style.ERROR('TTS falló — revisar OPENAI_API_KEY y logs'))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS('TTS OK'))
        self.stdout.write(f'URL: {result.url}')
        self.stdout.write(f'S3 key: {result.s3_key}')
        self.stdout.write(f'Bytes: {result.bytes_size}')
        self.stdout.write(f'Voice: {result.voice} | hash: {result.text_hash}')
