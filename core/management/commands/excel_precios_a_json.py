"""
Convierte Excel de lista de precios (local o DocumentoRAGComercial) → JSON → Postgres.

Ejemplos:

  # Excel en disco → JSON
  python manage.py excel_precios_a_json --archivo lista_mayo.xlsx --salida lista_mayo.json

  # Excel → JSON + cargar a Postgres
  python manage.py excel_precios_a_json --archivo lista.xlsx --cliente-id 12 --cargar

  # Desde documento ya subido al RAG comercial (admin)
  python manage.py excel_precios_a_json --documento-rag-id 45 --cargar

  # Por nombre del documento en RAG
  python manage.py excel_precios_a_json --documento-rag-nombre catalogo_abril_2026 --cliente-id 12 --cargar
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core.precios_excel import (
    excel_a_payload_json,
    leer_filas_excel,
    resolver_ruta_excel_desde_documento_rag,
)


class Command(BaseCommand):
    help = 'Convierte Excel de precios (RAG o local) a JSON y opcionalmente carga Postgres'

    def add_arguments(self, parser):
        src = parser.add_mutually_exclusive_group(required=True)
        src.add_argument('--archivo', help='Ruta local .xlsx / .xlsm')
        src.add_argument('--documento-rag-id', type=int, help='ID DocumentoRAGComercial indexado')
        src.add_argument('--documento-rag-nombre', help='Nombre exacto del documento RAG comercial')

        parser.add_argument(
            '--salida',
            help='Ruta JSON de salida (default: mismo nombre que el Excel con .json)',
        )
        parser.add_argument('--cliente-id', type=int, default=None, help='ID cliente (vacío = general)')
        parser.add_argument('--vigencia-desde', default=None, help='YYYY-MM-DD')
        parser.add_argument('--vigencia-hasta', default=None, help='YYYY-MM-DD')
        parser.add_argument(
            '--desactivar-ausentes',
            action='store_true',
            help='Marca desactivar_ausentes=true en el JSON / carga',
        )
        parser.add_argument('--hoja', default=None, help='Nombre o índice 0-based de hoja Excel')
        parser.add_argument(
            '--fila-encabezado',
            type=int,
            default=None,
            help='Fila 1-based del encabezado (auto-detecta si se omite)',
        )
        parser.add_argument(
            '--cargar',
            action='store_true',
            help='Después de generar JSON, ejecutar cargar_precios_comercial',
        )
        parser.add_argument('--mostrar', action='store_true', help='Imprime JSON en consola')

    def handle(self, *args, **options):
        ruta_excel: Path | None = None
        nombre_origen = ''
        cliente_doc: int | None = None
        temp_cleanup: Path | None = None

        if options.get('archivo'):
            ruta_excel = Path(options['archivo']).expanduser().resolve()
            if not ruta_excel.exists():
                raise CommandError(f'Archivo no encontrado: {ruta_excel}')
            nombre_origen = ruta_excel.name
        else:
            try:
                doc_cliente = options.get('cliente_id')
                ruta_excel, cliente_doc, nombre_origen = resolver_ruta_excel_desde_documento_rag(
                    documento_id=options.get('documento_rag_id'),
                    nombre=options.get('documento_rag_nombre'),
                    cliente_id=doc_cliente,
                )
                temp_cleanup = ruta_excel
                self.stdout.write(
                    self.style.NOTICE(
                        f'Usando documento RAG: {nombre_origen} (cliente_id={cliente_doc})'
                    )
                )
            except (FileNotFoundError, ValueError) as e:
                raise CommandError(str(e)) from e

        hoja = options.get('hoja')
        if hoja is not None and str(hoja).isdigit():
            hoja = int(hoja)

        fila_enc = options.get('fila_encabezado')
        if fila_enc is not None and fila_enc > 0:
            fila_enc = fila_enc - 1  # usuario 1-based → interno 0-based

        cliente_id = options.get('cliente_id')
        if cliente_id is None and cliente_doc:
            cliente_id = cliente_doc

        try:
            preview = leer_filas_excel(
                ruta_excel,
                hoja=hoja,
                fila_encabezado=fila_enc,
            )
        except ValueError as e:
            raise CommandError(str(e)) from e

        if not preview:
            raise CommandError('No se extrajeron productos del Excel (revisa columnas y hoja)')

        skus_auto = sum(1 for p in preview if _sku_autogenerado(p.get('sku', '')))

        payload = excel_a_payload_json(
            ruta_excel,
            cliente_id=cliente_id,
            vigencia_desde=options.get('vigencia_desde'),
            vigencia_hasta=options.get('vigencia_hasta'),
            desactivar_ausentes=bool(options.get('desactivar_ausentes')),
            hoja=hoja,
            fila_encabezado=fila_enc,
        )

        salida = options.get('salida')
        if salida:
            out_path = Path(salida).expanduser().resolve()
        else:
            stem = Path(nombre_origen).stem or 'precios'
            out_path = Path(tempfile.gettempdir()) / f'{stem}_precios.json'
            if options.get('archivo'):
                out_path = ruta_excel.with_suffix('.json')

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        self.stdout.write(self.style.SUCCESS(
            f'JSON generado: {out_path} | productos={len(payload["productos"])} | '
            f'skus_autogenerados~{skus_auto}'
        ))

        if options.get('mostrar'):
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))

        if options.get('cargar'):
            cmd_kwargs = {'archivo': str(out_path)}
            if cliente_id is not None:
                cmd_kwargs['cliente_id'] = cliente_id
            if options.get('desactivar_ausentes'):
                cmd_kwargs['desactivar_ausentes'] = True
            call_command('cargar_precios_comercial', **cmd_kwargs)
            self.stdout.write(self.style.SUCCESS('Precios cargados en Postgres (Nat).'))

        if temp_cleanup and str(temp_cleanup).startswith(tempfile.gettempdir()):
            try:
                temp_cleanup.unlink(missing_ok=True)
            except OSError:
                pass


def _sku_autogenerado(sku: str) -> bool:
    import re
    return bool(re.search(r'-R\d+$', str(sku or '')))
