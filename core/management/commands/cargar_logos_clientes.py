"""Rellena logo_url de clientes conocidos (solo si está vacío)."""
from django.core.management.base import BaseCommand
from django.templatetags.static import static

from core.client_logos import logo_estatico_para_nombre
from core.models import Cliente, Curso


class Command(BaseCommand):
    help = 'Asigna logos estáticos a clientes con curso si logo_url está vacío.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Pisa logo_url existente.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        ids = set(Curso.objects.exclude(cliente_id=None).values_list('cliente_id', flat=True))
        qs = Cliente.objects.filter(id__in=ids).order_by('nombre')
        n = 0
        for cli in qs:
            rel = logo_estatico_para_nombre(cli.nombre)
            if not rel:
                self.stdout.write(f'  skip (sin mapa): {cli.nombre}')
                continue
            if cli.logo_url.strip() and not opts['force']:
                self.stdout.write(f'  keep: {cli.nombre}')
                continue
            url = static(rel)
            if url.startswith('/'):
                url = 'https://admin.eki.technology' + url
            self.stdout.write(f'  {cli.nombre} → {url}')
            if not opts['dry_run']:
                cli.logo_url = url
                cli.save(update_fields=['logo_url'])
            n += 1
        verbo = 'previstos' if opts['dry_run'] else 'guardados'
        self.stdout.write(self.style.SUCCESS(f'Logos {verbo}: {n}'))
