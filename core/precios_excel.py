"""
Lectura flexible de listas de precios en Excel → estructura JSON para Postgres/Nat.

Soporta encabezados en filas distintas a la 1, columnas en español variadas,
precios con formato $185.000 y SKU autogenerado si falta.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

COLUMN_ALIASES: dict[str, set[str]] = {
    'sku': {
        'sku', 'codigo', 'código', 'cod', 'ref', 'referencia', 'item', 'id',
        'cod producto', 'cod. producto', 'codigo producto',
    },
    'nombre': {
        'nombre', 'producto', 'descripcion', 'descripción', 'insumo',
        'nombre producto', 'nombre comercial', 'articulo', 'artículo',
    },
    'presentacion': {
        'presentacion', 'presentación', 'empaque', 'formato', 'presentacion comercial',
    },
    'unidad': {'unidad', 'und', 'uom', 'unidad venta', 'unidad de venta'},
    'precio': {
        'precio', 'precio_cop', 'valor', 'precio unitario', 'precio venta',
        'precio lista', 'pvp', 'costo', 'precio $', 'precio cop',
    },
    'moneda': {'moneda', 'divisa'},
    'categoria': {
        'categoria', 'categoría', 'linea', 'línea', 'familia', 'tipo', 'grupo',
    },
    'notas': {'notas', 'observaciones', 'comentario', 'comentarios', 'detalle'},
    'vigencia_desde': {'vigencia desde', 'vigente desde', 'desde', 'fecha desde'},
    'vigencia_hasta': {'vigencia hasta', 'vigente hasta', 'hasta', 'fecha hasta'},
}


def _norm_header(val: Any) -> str:
    txt = str(val or '').strip().lower()
    txt = unicodedata.normalize('NFKD', txt)
    txt = ''.join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r'\s+', ' ', txt)
    return txt


def _map_headers(headers: list[str]) -> dict[str, int | None]:
    idx: dict[str, int | None] = {k: None for k in COLUMN_ALIASES}
    for i, raw in enumerate(headers):
        h = _norm_header(raw)
        if not h:
            continue
        for canon, aliases in COLUMN_ALIASES.items():
            if idx[canon] is not None:
                continue
            if h in aliases or any(h.startswith(a + ' ') for a in aliases):
                idx[canon] = i
    return idx


def _score_header_row(headers: list[str]) -> int:
    idx = _map_headers(headers)
    score = 0
    if idx['nombre'] is not None:
        score += 2
    if idx['precio'] is not None:
        score += 3
    if idx['sku'] is not None:
        score += 1
    return score


def detect_header_row(rows: list[tuple], max_scan: int = 20) -> int:
    """Índice 0-based de la fila que parece encabezado de catálogo."""
    best_row = 0
    best_score = -1
    for i, row in enumerate(rows[:max_scan]):
        headers = [str(c or '') for c in row]
        score = _score_header_row(headers)
        if score > best_score:
            best_score = score
            best_row = i
    if best_score < 3:
        raise ValueError(
            'No se detectó fila de encabezados con al menos columnas nombre y precio'
        )
    return best_row


def parse_precio(val: Any) -> Decimal:
    if val is None or val == '':
        raise ValueError('precio vacío')
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))

    txt = str(val).strip()
    txt = txt.replace('$', '').replace('COP', '').replace('cop', '')
    txt = txt.replace('\u00a0', '').replace(' ', '')
    # 185.000,50 → 185000.50 | 185,000 → 185000
    if re.search(r',\d{1,2}$', txt):
        txt = txt.replace('.', '').replace(',', '.')
    else:
        txt = txt.replace('.', '').replace(',', '')
    try:
        return Decimal(txt)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'precio inválido: {val!r}') from exc


def slug_sku(nombre: str, presentacion: str = '', row_num: int | None = None) -> str:
    base = f"{nombre} {presentacion}".strip() or 'PRODUCTO'
    slug = unicodedata.normalize('NFKD', base)
    slug = ''.join(ch for ch in slug if not unicodedata.combining(ch))
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', slug).strip('-').upper()
    slug = slug[:70] or 'PRODUCTO'
    if row_num is not None:
        slug = f"{slug}-R{row_num}"
    return slug[:80]


def _cell(row: tuple, index: int | None):
    if index is None or index >= len(row):
        return None
    return row[index]


def leer_filas_excel(
    path: Path,
    *,
    hoja: str | int | None = None,
    fila_encabezado: int | None = None,
) -> list[dict]:
    import openpyxl

    path = Path(path).expanduser().resolve()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if hoja is None:
            ws = wb.active
        elif isinstance(hoja, int):
            ws = wb.worksheets[hoja]
        else:
            ws = wb[hoja]

        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    if not rows:
        return []

    header_idx = fila_encabezado if fila_encabezado is not None else detect_header_row(rows)
    headers = [str(c or '') for c in rows[header_idx]]
    col = _map_headers(headers)

    if col['nombre'] is None or col['precio'] is None:
        raise ValueError(
            f'Fila encabezado {header_idx + 1}: faltan columnas nombre/producto y precio. '
            f'Encabezados detectados: {headers}'
        )

    productos: list[dict] = []
    for excel_row_num, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not row or all(c is None or str(c).strip() == '' for c in row):
            continue

        nombre = str(_cell(row, col['nombre']) or '').strip()
        precio_raw = _cell(row, col['precio'])
        if not nombre:
            continue
        if precio_raw is None or str(precio_raw).strip() == '':
            continue

        sku_raw = _cell(row, col['sku'])
        sku = str(sku_raw or '').strip()
        presentacion = str(_cell(row, col['presentacion']) or '').strip()
        if not sku:
            sku = slug_sku(nombre, presentacion, excel_row_num)

        try:
            precio = parse_precio(precio_raw)
        except ValueError:
            continue

        productos.append({
            'sku': sku,
            'nombre': nombre,
            'presentacion': presentacion,
            'unidad': str(_cell(row, col['unidad']) or '').strip(),
            'precio': float(precio),
            'moneda': str(_cell(row, col['moneda']) or 'COP').strip().upper() or 'COP',
            'categoria': str(_cell(row, col['categoria']) or '').strip(),
            'notas': str(_cell(row, col['notas']) or '').strip(),
            'vigencia_desde': _cell(row, col['vigencia_desde']),
            'vigencia_hasta': _cell(row, col['vigencia_hasta']),
            '_fila_excel': excel_row_num,
        })

    return productos


def excel_a_payload_json(
    path: Path,
    *,
    cliente_id: int | None = None,
    vigencia_desde: date | str | None = None,
    vigencia_hasta: date | str | None = None,
    desactivar_ausentes: bool = False,
    hoja: str | int | None = None,
    fila_encabezado: int | None = None,
) -> dict:
    productos = leer_filas_excel(
        path,
        hoja=hoja,
        fila_encabezado=fila_encabezado,
    )
    limpios = []
    for p in productos:
        item = {k: v for k, v in p.items() if not k.startswith('_')}
        limpios.append(item)

    payload: dict[str, Any] = {
        'cliente_id': cliente_id,
        'vigencia_desde': _fecha_iso(vigencia_desde),
        'vigencia_hasta': _fecha_iso(vigencia_hasta),
        'desactivar_ausentes': desactivar_ausentes,
        'origen_excel': str(Path(path).name),
        'productos': limpios,
    }
    return payload


def _fecha_iso(val) -> str | None:
    if not val:
        return None
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.date().isoformat()
    return str(val).strip()[:10] or None


def resolver_ruta_excel_desde_documento_rag(
    *,
    documento_id: int | None = None,
    nombre: str | None = None,
    cliente_id: int | None = None,
    tipo: str = 'precio',
) -> tuple[Path, int | None, str]:
    """
    Descarga a /tmp un DocumentoRAGComercial (.xlsx) indexado en el admin.
    Retorna (ruta_temp, cliente_id_doc, nombre_doc).
    """
    import tempfile

    from core.models import DocumentoRAGComercial

    qs = DocumentoRAGComercial.objects.filter(estado='indexado')
    if documento_id:
        doc = qs.filter(pk=documento_id).first()
    else:
        qs = qs.filter(tipo=tipo)
        if nombre:
            qs = qs.filter(nombre__iexact=nombre.strip())
        if cliente_id not in (None, 0):
            qs = qs.filter(cliente_id=cliente_id)
        doc = qs.order_by('-fecha_indexado').first()

    if not doc or not doc.archivo:
        raise FileNotFoundError(
            'No se encontró documento RAG comercial Excel indexado con esos criterios'
        )

    ext = Path(doc.archivo.name).suffix.lower()
    if ext not in {'.xlsx', '.xlsm', '.xls'}:
        raise ValueError(f'El documento "{doc.nombre}" no es Excel ({ext})')

    ruta = doc.archivo.path
    if not Path(ruta).exists():
        ruta = doc._descargar_temp()
        if not ruta:
            raise FileNotFoundError(f'No se pudo descargar archivo de "{doc.nombre}"')

    return Path(ruta), doc.cliente_id, doc.nombre
