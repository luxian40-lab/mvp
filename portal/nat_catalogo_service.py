"""CRUD de catálogo de recomendaciones y lista de precios para Nat (portal)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError
from django.db.models import Q

from core.models import ProductoCatalogo, ProductoComercial


def _txt(data, key: str, default: str = '') -> str:
    return (data.get(key) or default).strip()


def _bool_activo(data) -> bool:
    return str(data.get('activo') or '').lower() in ('1', 'true', 'on', 'yes', 'si', 'sí')


def _decimal_or_none(raw, *, required: bool = False, label: str = 'Precio'):
    s = (raw or '').strip().replace(',', '.')
    if not s:
        if required:
            raise ValueError(f'{label} es obligatorio.')
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'{label} no es un número válido.') from exc


def _date_or_none(raw: str):
    from datetime import datetime

    s = (raw or '').strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError('Fecha inválida (use AAAA-MM-DD).') from exc


def listar_catalogo(org, *, q: str = '', solo_activos: bool = False):
    qs = ProductoCatalogo.objects.filter(cliente_id=org.pk)
    if solo_activos:
        qs = qs.filter(activo=True)
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(categoria__icontains=q))
    return qs.order_by('categoria', 'nombre')


def listar_precios(org, *, q: str = '', solo_activos: bool = False):
    """Solo SKUs de esta org (nunca el catálogo general cliente=null)."""
    qs = ProductoComercial.objects.filter(cliente_id=org.pk)
    if solo_activos:
        qs = qs.filter(activo=True)
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) | Q(sku__icontains=q) | Q(categoria__icontains=q)
        )
    return qs.order_by('nombre', 'sku')


def crear_catalogo(org, data) -> ProductoCatalogo:
    nombre = _txt(data, 'nombre')
    if not nombre:
        raise ValueError('El nombre es obligatorio.')
    descripcion = _txt(data, 'descripcion')
    problema = _txt(data, 'problema_que_resuelve')
    if not descripcion:
        raise ValueError('La descripción es obligatoria.')
    if not problema:
        raise ValueError('Indique qué problemas resuelve (Nat lo usa para recomendar).')

    obj = ProductoCatalogo(
        cliente=org,
        nombre=nombre,
        descripcion=descripcion,
        problema_que_resuelve=problema,
        ingrediente_activo=_txt(data, 'ingrediente_activo'),
        categoria=_txt(data, 'categoria'),
        cultivos_objetivo=_txt(data, 'cultivos_objetivo'),
        dosis=_txt(data, 'dosis'),
        precio_cop=_decimal_or_none(data.get('precio_cop'), label='Precio de referencia'),
        unidad=_txt(data, 'unidad'),
        url_producto=_txt(data, 'url_producto'),
        activo=_bool_activo(data),
    )
    try:
        obj.save()
    except IntegrityError as exc:
        raise ValueError(f'Ya existe un producto llamado «{nombre}» en su catálogo.') from exc
    return obj


def actualizar_catalogo(obj: ProductoCatalogo, data) -> ProductoCatalogo:
    nombre = _txt(data, 'nombre')
    if not nombre:
        raise ValueError('El nombre es obligatorio.')
    descripcion = _txt(data, 'descripcion')
    problema = _txt(data, 'problema_que_resuelve')
    if not descripcion:
        raise ValueError('La descripción es obligatoria.')
    if not problema:
        raise ValueError('Indique qué problemas resuelve.')

    obj.nombre = nombre
    obj.descripcion = descripcion
    obj.problema_que_resuelve = problema
    obj.ingrediente_activo = _txt(data, 'ingrediente_activo')
    obj.categoria = _txt(data, 'categoria')
    obj.cultivos_objetivo = _txt(data, 'cultivos_objetivo')
    obj.dosis = _txt(data, 'dosis')
    obj.precio_cop = _decimal_or_none(data.get('precio_cop'), label='Precio de referencia')
    obj.unidad = _txt(data, 'unidad')
    obj.url_producto = _txt(data, 'url_producto')
    obj.activo = _bool_activo(data)
    try:
        obj.save()
    except IntegrityError as exc:
        raise ValueError(f'Ya existe un producto llamado «{nombre}» en su catálogo.') from exc
    return obj


def crear_precio(org, data) -> ProductoComercial:
    sku = _txt(data, 'sku')
    nombre = _txt(data, 'nombre')
    if not sku:
        raise ValueError('El SKU / código es obligatorio.')
    if not nombre:
        raise ValueError('El nombre es obligatorio.')
    precio = _decimal_or_none(data.get('precio'), required=True, label='Precio')

    obj = ProductoComercial(
        cliente=org,
        sku=sku,
        nombre=nombre,
        presentacion=_txt(data, 'presentacion'),
        unidad=_txt(data, 'unidad'),
        precio=precio,
        moneda=_txt(data, 'moneda', 'COP') or 'COP',
        categoria=_txt(data, 'categoria'),
        notas=_txt(data, 'notas'),
        vigencia_desde=_date_or_none(_txt(data, 'vigencia_desde')),
        vigencia_hasta=_date_or_none(_txt(data, 'vigencia_hasta')),
        activo=_bool_activo(data),
    )
    try:
        obj.save()
    except IntegrityError as exc:
        raise ValueError(f'Ya existe el SKU «{sku}» en su lista de precios.') from exc
    return obj


def actualizar_precio(obj: ProductoComercial, data) -> ProductoComercial:
    sku = _txt(data, 'sku')
    nombre = _txt(data, 'nombre')
    if not sku:
        raise ValueError('El SKU / código es obligatorio.')
    if not nombre:
        raise ValueError('El nombre es obligatorio.')
    precio = _decimal_or_none(data.get('precio'), required=True, label='Precio')

    obj.sku = sku
    obj.nombre = nombre
    obj.presentacion = _txt(data, 'presentacion')
    obj.unidad = _txt(data, 'unidad')
    obj.precio = precio
    obj.moneda = _txt(data, 'moneda', 'COP') or 'COP'
    obj.categoria = _txt(data, 'categoria')
    obj.notas = _txt(data, 'notas')
    obj.vigencia_desde = _date_or_none(_txt(data, 'vigencia_desde'))
    obj.vigencia_hasta = _date_or_none(_txt(data, 'vigencia_hasta'))
    obj.activo = _bool_activo(data)
    try:
        obj.save()
    except IntegrityError as exc:
        raise ValueError(f'Ya existe el SKU «{sku}» en su lista de precios.') from exc
    return obj
