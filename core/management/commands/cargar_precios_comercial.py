"""
Carga o actualiza precios comerciales desde JSON (o Excel) hacia Postgres.

Uso:
  python manage.py cargar_precios_comercial --archivo lista.json
  python manage.py cargar_precios_comercial --archivo lista.xlsx --cliente-id 12
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.precios_import import importar_precios_desde_archivo


class Command(BaseCommand):
    help = 'Carga precios comerciales desde JSON o Excel hacia Postgres (Nat)'

    def add_arguments(self, parser):
        parser.add_argument('--archivo', required=True, help='Ruta a .json, .xlsx o .xlsm')
        parser.add_argument(
            '--cliente-id',
            type=int,
            default=None,
            help='ID cliente (0 o omitir = catálogo general)',
        )
        parser.add_argument(
            '--desactivar-ausentes',
            action='store_true',
            help='Desactiva productos del cliente que no vengan en el archivo',
        )
        parser.add_argument('--dry-run', action='store_true', help='Valida sin escribir en BD')

    def handle(self, *args, **options):
        path = Path(options['archivo']).expanduser().resolve()
        try:
            result = importar_precios_desde_archivo(
                path,
                cliente_id=options.get('cliente_id'),
                desactivar_ausentes=bool(options.get('desactivar_ausentes')),
                dry_run=bool(options.get('dry_run')),
            )
        except (FileNotFoundError, ValueError) as e:
            raise CommandError(str(e)) from e

        if result.errores:
            raise CommandError('Errores de validación:\n' + '\n'.join(result.errores[:20]))

        if result.dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'[DRY-RUN] {result.total_validos} productos válidos para '
                f'cliente={result.cliente_nombre}'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Listo: creados={result.creados}, actualizados={result.actualizados}, '
            f'desactivados={result.desactivados}, cliente={result.cliente_nombre}'
        ))
