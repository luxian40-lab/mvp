"""Quita la pausa de una campaña Meta y sus contadores de fallo."""
from django.core.management.base import BaseCommand, CommandError

from core.campana_meta_ritmo import reanudar
from core.models_campana_meta import CampanaMeta


class Command(BaseCommand):
    help = 'Reanuda una campaña pausada. Uso: campana_reanudar <id>'

    def add_arguments(self, parser):
        parser.add_argument('campana_id', type=int)

    def handle(self, *args, **options):
        try:
            campana = CampanaMeta.objects.get(pk=options['campana_id'])
        except CampanaMeta.DoesNotExist as exc:
            raise CommandError('No existe esa campaña.') from exc
        reanudar(campana)
        self.stdout.write(f'reanudada {campana.pk}')
