"""Chequeo antes de lanzar una campaña Meta. No imprime teléfonos."""
from django.core.management.base import BaseCommand, CommandError

from core.campana_meta_ritmo import resumen_preflight
from core.models_campana_meta import CampanaMeta


class Command(BaseCommand):
    help = 'Resume plantilla, opt-in y duración estimada. Uso: campana_preflight <id>'

    def add_arguments(self, parser):
        parser.add_argument('campana_id', type=int)

    def handle(self, *args, **options):
        try:
            campana = CampanaMeta.objects.select_related('plantilla').get(pk=options['campana_id'])
        except CampanaMeta.DoesNotExist as exc:
            raise CommandError('No existe esa campaña.') from exc
        for linea in resumen_preflight(campana):
            self.stdout.write(linea)
