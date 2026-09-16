"""Flush outbox → zona raw del Data Lake (S3 o URI local)."""

from django.core.management.base import BaseCommand

from core.event_engine import flush_outbox_pendientes


class Command(BaseCommand):
    help = 'Publica EventOutbox pendientes a lake/raw/ (DATA_LAKE_ENABLED).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **options):
        n = flush_outbox_pendientes(limit=options['limit'])
        self.stdout.write(self.style.SUCCESS(f'Publicados: {n}'))
