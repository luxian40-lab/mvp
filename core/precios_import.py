"""
Importación de listas de precios (Excel / JSON) → ProductoComercial (Postgres / Nat).
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.utils.dateparse import parse_date

from core.models import Cliente, ProductoComercial
from core.precios_excel import excel_a_payload_json, leer_filas_excel


@dataclass
class ImportPreciosResult:
    creados: int = 0
    actualizados: int = 0
    desactivados: int = 0
    total_validos: int = 0
    errores: list[str] = field(default_factory=list)
    cliente_nombre: str = 'General'
    dry_run: bool = False
    json_path: str | None = None


def _parse_fecha(val) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    return parse_date(str(val).strip()[:10])


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
        raise ValueError('JSON inválido: se esperaba objeto o lista de productos')
    return data


def _resolver_cliente(cliente_id: int | None) -> Cliente | None:
    if cliente_id in (None, 0):
        return None
    cliente = Cliente.objects.filter(pk=cliente_id).first()
    if not cliente:
        raise ValueError(f'Cliente id={cliente_id} no existe')
    return cliente


def _parse_archivo(
    path: Path,
    *,
    cliente_id: int | None = None,
    desactivar_ausentes: bool = False,
    vigencia_desde: date | str | None = None,
    vigencia_hasta: date | str | None = None,
    guardar_json_en: Path | None = None,
) -> tuple[list[dict], dict, int | None, bool]:
    ext = path.suffix.lower()
    cid = cliente_id
    desactivar = desactivar_ausentes
    defaults: dict = {}

    if ext == '.json':
        payload = _leer_json(path)
        if cid is None and payload.get('cliente_id') is not None:
            cid = int(payload['cliente_id'])
        if not desactivar:
            desactivar = bool(payload.get('desactivar_ausentes'))
        defaults = {
            'vigencia_desde': _parse_fecha(payload.get('vigencia_desde') or vigencia_desde),
            'vigencia_hasta': _parse_fecha(payload.get('vigencia_hasta') or vigencia_hasta),
            'moneda': payload.get('moneda') or 'COP',
        }
        raw_productos = payload.get('productos') or []
    elif ext in {'.xlsx', '.xlsm', '.xls'}:
        payload = excel_a_payload_json(
            path,
            cliente_id=cid,
            vigencia_desde=vigencia_desde,
            vigencia_hasta=vigencia_hasta,
            desactivar_ausentes=desactivar,
        )
        if cid is None and payload.get('cliente_id') is not None:
            cid = int(payload['cliente_id'])
        if not desactivar:
            desactivar = bool(payload.get('desactivar_ausentes'))
        defaults = {
            'vigencia_desde': _parse_fecha(payload.get('vigencia_desde')),
            'vigencia_hasta': _parse_fecha(payload.get('vigencia_hasta')),
            'moneda': payload.get('moneda') or 'COP',
        }
        raw_productos = payload.get('productos') or leer_filas_excel(path)
        if guardar_json_en:
            guardar_json_en.parent.mkdir(parents=True, exist_ok=True)
            guardar_json_en.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
    else:
        raise ValueError('Formato no soportado. Use .json, .xlsx, .xlsm o .xls')

    if not raw_productos:
        raise ValueError('No hay productos para cargar')

    return raw_productos, defaults, cid, desactivar


def importar_precios_desde_archivo(
    path: Path | str,
    *,
    cliente_id: int | None = None,
    desactivar_ausentes: bool = False,
    dry_run: bool = False,
    vigencia_desde: date | str | None = None,
    vigencia_hasta: date | str | None = None,
    guardar_json_en: Path | None = None,
) -> ImportPreciosResult:
    """Lee Excel/JSON, valida filas y upserta en ProductoComercial."""
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f'Archivo no encontrado: {path}')

    raw_productos, defaults, cid, desactivar = _parse_archivo(
        path,
        cliente_id=cliente_id,
        desactivar_ausentes=desactivar_ausentes,
        vigencia_desde=vigencia_desde,
        vigencia_hasta=vigencia_hasta,
        guardar_json_en=guardar_json_en,
    )
    cliente = _resolver_cliente(cid)

    normalizados: list[dict] = []
    errores: list[str] = []
    for i, raw in enumerate(raw_productos, start=1):
        try:
            normalizados.append(_normalizar_producto(raw, defaults))
        except ValueError as e:
            errores.append(f'Fila {i}: {e}')

    result = ImportPreciosResult(
        total_validos=len(normalizados),
        errores=errores,
        cliente_nombre=cliente.nombre if cliente else 'General',
        dry_run=dry_run,
        json_path=str(guardar_json_en) if guardar_json_en else None,
    )
    if errores:
        return result

    if dry_run:
        return result

    creados = actualizados = desactivados = 0
    skus_vistos: set[str] = set()

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

        if desactivar:
            qs_off = ProductoComercial.objects.filter(cliente=cliente, activo=True).exclude(
                sku__in=skus_vistos
            )
            desactivados = qs_off.update(activo=False)

    result.creados = creados
    result.actualizados = actualizados
    result.desactivados = desactivados
    return result


def _ruta_excel_desde_documento_rag(doc) -> Path:
    from core.models import DocumentoRAGComercial

    if not isinstance(doc, DocumentoRAGComercial) or not doc.archivo:
        raise ValueError('Documento sin archivo')

    ext = Path(doc.archivo.name).suffix.lower()
    if ext not in {'.xlsx', '.xlsm', '.xls'}:
        raise ValueError(f'«{doc.nombre}» no es Excel ({ext or "sin extensión"})')

    try:
        ruta = Path(doc.archivo.path)
        if ruta.exists():
            return ruta
    except (ValueError, NotImplementedError):
        pass

    ruta_tmp = doc._descargar_temp()
    if not ruta_tmp:
        raise FileNotFoundError(f'No se pudo leer el archivo de «{doc.nombre}»')
    return Path(ruta_tmp)


def importar_precios_desde_documento_rag(
    documento,
    *,
    cliente_id: int | None = None,
    desactivar_ausentes: bool = False,
    dry_run: bool = False,
    vigencia_desde: date | str | None = None,
    vigencia_hasta: date | str | None = None,
) -> ImportPreciosResult:
    """Importa precios desde un DocumentoRAGComercial (.xlsx)."""
    ruta = _ruta_excel_desde_documento_rag(documento)
    cid = cliente_id if cliente_id not in (None, 0) else documento.cliente_id
    json_out = None
    if not dry_run:
        stem = Path(documento.nombre or 'precios').stem
        json_out = Path(tempfile.gettempdir()) / f'{stem}_precios_import.json'

    try:
        return importar_precios_desde_archivo(
            ruta,
            cliente_id=cid,
            desactivar_ausentes=desactivar_ausentes,
            dry_run=dry_run,
            vigencia_desde=vigencia_desde,
            vigencia_hasta=vigencia_hasta,
            guardar_json_en=json_out,
        )
    finally:
        if str(ruta).startswith(tempfile.gettempdir()):
            try:
                ruta.unlink(missing_ok=True)
            except OSError:
                pass
