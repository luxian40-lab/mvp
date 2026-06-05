"""
Carga o actualiza el catálogo de productos de un cliente desde un Excel.

Columnas requeridas en el Excel:
  nombre_producto | descripcion | problema_que_resuelve

Columnas opcionales:
  ingrediente_activo | categoria | cultivos_objetivo |
  dosis | precio_cop | unidad | url_producto

Uso:
  python manage.py cargar_catalogo --cliente agronexo --archivo catalogo.xlsx
  python manage.py cargar_catalogo --cliente nitrofert --archivo catalogo.xlsx --limpiar
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.models import Cliente, ProductoCatalogo

COLUMNAS_REQUERIDAS = {'nombre_producto', 'descripcion', 'problema_que_resuelve'}
# Evita cargas masivas que bloqueen consola/worker en producción (ajustable por env).
MAX_FILAS_EXCEL = 2000


COLUMNAS_OPCIONALES = {
    'ingrediente_activo': 'ingrediente_activo',
    'categoria': 'categoria',
    'cultivos_objetivo': 'cultivos_objetivo',
    'dosis': 'dosis',
    'precio_cop': 'precio_cop',
    'unidad': 'unidad',
    'url_producto': 'url_producto',
}


class Command(BaseCommand):
    help = 'Carga el catálogo de productos de un cliente desde un archivo Excel'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cliente',
            required=True,
            help='Nombre exacto del cliente (organización) en Cliente',
        )
        parser.add_argument(
            '--archivo',
            required=True,
            help='Ruta al archivo Excel (.xlsx)',
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            default=False,
            help='Si se pasa, elimina todos los productos previos del cliente antes de cargar',
        )

    def handle(self, *args, **options):
        try:
            import pandas as pd
        except ImportError as e:
            raise CommandError('Se requiere pandas: pip install pandas openpyxl') from e

        nombre_cliente = options['cliente']
        ruta_archivo = options['archivo']
        limpiar = options['limpiar']

        try:
            cliente = Cliente.objects.get(nombre__iexact=nombre_cliente)
        except Cliente.DoesNotExist:
            raise CommandError(
                f'No se encontró cliente con nombre "{nombre_cliente}". '
                f'Clientes disponibles: '
                f'{list(Cliente.objects.values_list("nombre", flat=True))}'
            ) from None

        try:
            df = pd.read_excel(ruta_archivo)
        except FileNotFoundError:
            raise CommandError(f'Archivo no encontrado: {ruta_archivo}') from None
        except Exception as e:
            raise CommandError(f'Error leyendo el Excel: {e}') from e

        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

        faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
        if faltantes:
            raise CommandError(
                f'El Excel no tiene las columnas requeridas: {faltantes}\n'
                f'Columnas encontradas: {list(df.columns)}'
            )

        import os

        max_filas = int(os.environ.get('CATALOGO_MAX_FILAS', MAX_FILAS_EXCEL))
        if len(df) > max_filas:
            raise CommandError(
                f'El Excel tiene {len(df)} filas (máximo {max_filas}). '
                f'Divida el archivo o suba CATALOGO_MAX_FILAS. '
                f'Ejecute la carga por SSH, no desde el admin web.'
            )

        if limpiar:
            eliminados = ProductoCatalogo.objects.filter(cliente=cliente).delete()[0]
            self.stdout.write(
                f'🗑  Eliminados {eliminados} productos previos de {cliente.nombre}'
            )

        creados = 0
        actualizados = 0
        errores = 0

        for i, row in df.iterrows():
            try:
                nombre = str(row['nombre_producto']).strip()
                if not nombre or nombre == 'nan':
                    continue

                defaults = {
                    'descripcion': str(row.get('descripcion', '')).strip(),
                    'problema_que_resuelve': str(row.get('problema_que_resuelve', '')).strip(),
                }

                for col_excel, campo_modelo in COLUMNAS_OPCIONALES.items():
                    if col_excel in df.columns:
                        val = row.get(col_excel)
                        if pd.notna(val) and str(val).strip() not in ('', 'nan'):
                            if campo_modelo == 'precio_cop':
                                try:
                                    defaults[campo_modelo] = int(
                                        float(
                                            str(val).replace(',', '').replace('$', '').strip()
                                        )
                                    )
                                except ValueError:
                                    pass
                            else:
                                defaults[campo_modelo] = str(val).strip()

                _obj, created = ProductoCatalogo.objects.update_or_create(
                    cliente=cliente,
                    nombre=nombre,
                    defaults=defaults,
                )

                if created:
                    creados += 1
                else:
                    actualizados += 1

            except Exception as e:
                self.stderr.write(f'  ⚠️  Error en fila {i + 2}: {e}')
                errores += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Catálogo de {cliente.nombre} cargado:\n'
                f'   Creados:     {creados}\n'
                f'   Actualizados:{actualizados}\n'
                f'   Errores:     {errores}\n'
                f'   Total activos: {ProductoCatalogo.objects.filter(cliente=cliente, activo=True).count()}'
            )
        )
