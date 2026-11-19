"""Snapshot W2 de colas Celery (profundidad + edad). Pegar en docs/INFORME_W2_COLAS.md."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from core.analitica.colas_w2 import snapshot_colas_w2


class Command(BaseCommand):
    help = 'Lee conversacion/masivo/media_encode: LLEN y edad del mensaje más viejo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Salida JSON (para pegar en el informe W2).',
        )

    def handle(self, *args, **options):
        snap = snapshot_colas_w2()
        if options['json']:
            self.stdout.write(json.dumps(snap, ensure_ascii=False, indent=2))
            return
        if not snap.get('ok'):
            self.stderr.write(self.style.ERROR(snap.get('error') or 'sin lectura'))
            return
        self.stdout.write(f"tomado_en={snap.get('tomado_en')}")
        self.stdout.write(f"mas_viejo_seg={snap.get('mas_viejo_seg')}")
        for nombre, fila in (snap.get('colas') or {}).items():
            self.stdout.write(
                f"{nombre}: profundidad={fila.get('profundidad')} "
                f"edad_seg={fila.get('edad_seg')} fuente={fila.get('fuente')}"
            )
