# -*- coding: utf-8 -*-
"""Verifica que label/genero del catalogo coincidan con la voz real en ElevenLabs."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.course_engine.voice_config import catalogo_voces

_GENERO_API = {'male': 'M', 'female': 'F'}


class Command(BaseCommand):
    help = (
        'Compara COURSE_ENGINE voices contra la API de ElevenLabs. '
        'Falla si el genero del catalogo no coincide con el real.'
    )

    def handle(self, *args, **options):
        import httpx

        api_key = getattr(settings, 'ELEVENLABS_API_KEY', '')
        if not api_key:
            self.stderr.write(self.style.ERROR('Falta ELEVENLABS_API_KEY'))
            raise SystemExit(1)

        problemas = []
        for v in catalogo_voces():
            vid = v['id']
            try:
                resp = httpx.get(
                    f'https://api.elevenlabs.io/v1/voices/{vid}',
                    headers={'xi-api-key': api_key},
                    timeout=30.0,
                )
            except Exception as exc:
                problemas.append(f"{v['label']}: error de red ({exc})")
                continue

            if resp.status_code != 200:
                problemas.append(f"{v['label']} ({vid}): HTTP {resp.status_code}")
                continue

            data = resp.json()
            labels = data.get('labels') or {}
            real_nombre = data.get('name') or '?'
            real_genero = _GENERO_API.get((labels.get('gender') or '').lower(), '?')
            acento = labels.get('accent') or '?'

            if real_genero != v.get('genero'):
                problemas.append(
                    f"{v['label']} ({vid}): catalogo genero={v.get('genero')} "
                    f"pero ElevenLabs dice {real_genero} ({real_nombre})"
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"MISMATCH {v['label']:14} -> {real_nombre} [{real_genero}, {acento}]"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK {v['label']:14} -> {real_nombre} [{real_genero}, {acento}]"
                    )
                )

        self.stdout.write('')
        if problemas:
            self.stderr.write(self.style.ERROR('QA_FAIL catalogo de voces:'))
            for p in problemas:
                self.stderr.write(f'  - {p}')
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS('QA_PASS catalogo de voces coherente.'))
