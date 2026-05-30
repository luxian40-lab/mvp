"""
Carga o actualiza precios comerciales desde JSON (o Excel) hacia Postgres.

Ejemplo JSON (lista_precios.json):

{
  "cliente_id": 12,
  "vigencia_desde": "2026-05-01",
  "vigencia_hasta": "2026-12-31",
  "desactivar_ausentes": true,
  "productos": [
    {
      "sku": "UREA-46-50KG",
      "nombre": "Urea 46% granular",
      "presentacion": "bulto 50 kg",
      "unidad": "bulto",
      "precio": 185000,
      "moneda": "COP",
      "categoria": "fertilizante",
      "notas": "Precio sin flete"
    }
  ]
}

Uso:
  python manage.py cargar_precios_comercial --archivo lista.json
  python manage.py cargar_precios_comercial --archivo lista.xlsx --cliente-id 12
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from core.models import Cliente, ProductoComercial
from core.precios_excel import leer_filas_excel


def _parse_fecha(val) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    parsed = parse_date(str(val).strip()[:10])
    return parsed


def _parse_precio(val) -> Decimal:
    if val is None or val == '':
        raise ValueError('precio vacío')
    try:
        return Decimal(str(val).replace(',', '.').strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'precio inválido: {val!r}') from exc


def _normalizar_producto(raw: dict, defaults: dict) -> dict:
    sku = (raw.get('sku') or raw.get('codigo') or '').strip()
    nombre = (raw.get('nombre') or raw.get('producto') or '').strip()
    if not sku:
        raise ValueError('falta sku/codigo')
    if not nombre:
        raise ValueError(f'falta nombre para sku={sku}')

    return {
        'sku': sku[:80],
        'nombre': nombre[:200],
        'presentacion': (raw.get('presentacion') or raw.get('presentación') or defaults.get('presentacion') or '')[:120],
        'unidad': (raw.get('unidad') or defaults.get('unidad') or '')[:40],
        'precio': _parse_precio(raw.get('precio') or raw.get('precio_cop')),
        'moneda': (raw.get('moneda') or defaults.get('moneda') or 'COP')[:8].upper(),
        'categoria': (raw.get('categoria') or raw.get('categoría') or defaults.get('categoria') or '')[:80],
        'notas': (raw.get('notas') or raw.get('observaciones') or '')[:2000],
        'vigencia_desde': _parse_fecha(raw.get('vigencia_desde') or defaults.get('vigencia_desde')),
        'vigencia_hasta': _parse_fecha(raw.get('vigencia_hasta') or defaults.get('vigencia_hasta')),
        'activo': bool(raw.get('activo', True)),
    }


def _leer_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data, list):
        return {'productos': data}
    if not isinstance(data, dict):
        raise CommandError('JSON inválido: se esperaba objeto o lista de productos')
    return data


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
        if not path.exists():
            raise CommandError(f'Archivo no encontrado: {path}')

        ext = path.suffix.lower()
        cliente_id = options.get('cliente_id')
        dry_run = bool(options.get('dry_run'))
        desactivar_ausentes = bool(options.get('desactivar_ausentes'))

        if ext == '.json':
            payload = _leer_json(path)
            if cliente_id is None and payload.get('cliente_id') is not None:
                cliente_id = int(payload['cliente_id'])
            if not desactivar_ausentes:
                desactivar_ausentes = bool(payload.get('desactivar_ausentes'))
            defaults = {
                'vigencia_desde': _parse_fecha(payload.get('vigencia_desde')),
                'vigencia_hasta': _parse_fecha(payload.get('vigencia_hasta')),
                'moneda': payload.get('moneda') or 'COP',
            }
            raw_productos = payload.get('productos') or []
        elif ext in {'.xlsx', '.xlsm', '.xls'}:
            try:
                raw_productos = leer_filas_excel(path)
            except ValueError as e:
                raise CommandError(str(e)) from e
            defaults = {}
        else:
            raise CommandError('Formato no soportado. Use .json, .xlsx o .xlsm')

        if not raw_productos:
            raise CommandError('No hay productos para cargar')

        cliente = None
        if cliente_id not in (None, 0):
            cliente = Cliente.objects.filter(pk=cliente_id).first()
            if not cliente:
                raise CommandError(f'Cliente id={cliente_id} no existe')

        normalizados = []
        errores = []
        for i, raw in enumerate(raw_productos, start=1):
            try:
                normalizados.append(_normalizar_producto(raw, defaults))
            except ValueError as e:
                errores.append(f'Fila {i}: {e}')

        if errores:
            raise CommandError('Errores de validación:\n' + '\n'.join(errores[:20]))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'[DRY-RUN] {len(normalizados)} productos válidos para '
                f'cliente={cliente.nombre if cliente else "General"}'
            ))
            return

        creados = actualizados = desactivados = 0
        skus_vistos = set()

        with transaction.atomic():
            for item in normalizados:
                skus_vistos.add(item['sku'])
                obj, created = ProductoComercial.objects.update_or_create(
                    cliente=cliente,
                    sku=item['sku'],
                    defaults={
                        'nombre': item['nombre'],
                        'presentacion': item['presentacion'],
                        'unidad': item['unidad'],
                        'precio': item['precio'],
                        'moneda': item['moneda'],
                        'categoria': item['categoria'],
                        'notas': item['notas'],
                        'vigencia_desde': item['vigencia_desde'],
                        'vigencia_hasta': item['vigencia_hasta'],
                        'activo': item['activo'],
                    },
                )
                if created:
                    creados += 1
                else:
                    actualizados += 1

            if desactivar_ausentes:
                qs_off = ProductoComercial.objects.filter(cliente=cliente, activo=True).exclude(sku__in=skus_vistos)
                desactivados = qs_off.update(activo=False)

        self.stdout.write(self.style.SUCCESS(
            f'Listo: creados={creados}, actualizados={actualizados}, '
            f'desactivados={desactivados}, cliente={cliente.nombre if cliente else "General"}'
        ))
