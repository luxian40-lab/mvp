"""Pares (campaña, estudiante) con más de un envío. No imprime teléfonos."""
from django.core.management.base import BaseCommand
from django.db.models import Count

from core.models_campana_meta import EnvioCampanaMeta


class Command(BaseCommand):
    help = 'Lista envíos Meta duplicados por campaña y estudiante.'

    def handle(self, *args, **options):
        filas = (
            EnvioCampanaMeta.objects.values('campana_id', 'estudiante_id')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .order_by('campana_id', 'estudiante_id')
        )
        total = filas.count()
        self.stdout.write(f'duplicados {total}')
        for fila in filas[:50]:
            self.stdout.write(
                f"campana {fila['campana_id']} estudiante_id {fila['estudiante_id']} n {fila['n']}"
            )
        if total:
            self.stderr.write('Hay duplicados. No se puede crear la restricción única.')
            raise SystemExit(2)
