"""Rellena EventOutbox.territory_id desde telemetría / estudiante."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Estudiante, EstudianteEventoAprendizaje, EventOutbox
from core.territorio import obtener_territory_id_estudiante


class Command(BaseCommand):
    help = (
        'Backfill territory_id en EventOutbox vacío usando payload.telemetria_id '
        '→ Estudiante (y resolución DIVIPOLA si hace falta).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=2000)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        limit = max(1, int(options['limit'] or 2000))
        dry = bool(options['dry_run'])
        qs = (
            EventOutbox.objects.filter(Q(territory_id='') | Q(territory_id__isnull=True))
            .order_by('id')[:limit]
        )
        updated = 0
        skipped = 0
        for row in qs:
            tid = ''
            payload = row.payload or {}
            tel_id = payload.get('telemetria_id')
            if tel_id:
                ev = (
                    EstudianteEventoAprendizaje.objects.select_related('estudiante')
                    .filter(pk=tel_id)
                    .first()
                )
                if ev and ev.estudiante_id:
                    tid = obtener_territory_id_estudiante(ev.estudiante, persistir=not dry)
            if not tid and row.actor_pseudo:
                # sin telemetría: no reverseamos hash; skip
                skipped += 1
                continue
            if not tid:
                skipped += 1
                continue
            if dry:
                self.stdout.write(f'dry-run id={row.pk} → {tid}')
            else:
                row.territory_id = tid[:32]
                row.save(update_fields=['territory_id'])
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(f'backfill territory outbox: updated={updated} skipped={skipped} dry={dry}')
        )
