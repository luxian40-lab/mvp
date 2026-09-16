"""Correlación v0: clusters territoriales por densidad + k-anonimato."""

from django.core.management.base import BaseCommand

from core.event_engine import correlacionar_clusters


class Command(BaseCommand):
    help = (
        'Calcula alertas territoriales (density_v0). '
        'Umbrales: ALERTA_TERRITORIAL_VENTANA_HORAS / MIN_K.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--ventana-horas', type=int, default=None)
        parser.add_argument('--min-k', type=int, default=None)
        parser.add_argument('--tipo-prefijo', type=str, default='')

    def handle(self, *args, **options):
        alertas = correlacionar_clusters(
            ventana_horas=options['ventana_horas'],
            min_k=options['min_k'],
            tipo_prefijo=options['tipo_prefijo'] or '',
        )
        self.stdout.write(self.style.SUCCESS(f'Alertas activas/actualizadas: {len(alertas)}'))
        for a in alertas:
            self.stdout.write(
                f"  · {a.familia}.{a.subtipo} @ {a.territory_id} "
                f"n={a.conteo} score={a.score}"
            )
