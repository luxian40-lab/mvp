"""Carrito eki Studio: agregar ítems y checkout multi-curso."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from .catalogo_service import curso_disponible_en_studio, ids_cursos_inscritos, inscribir_estudiante_en_curso
from .models import (
    AccesoCursoPagado,
    CarritoStudio,
    CuentaAula,
    ItemCarritoStudio,
    OrdenItemStudio,
    OrdenStudio,
    PublicacionStudio,
)
from .pago_service import (
    marcar_pago_aprobado,
    nueva_referencia,
)


def obtener_o_crear_carrito(cuenta: CuentaAula) -> CarritoStudio:
    carrito, _ = CarritoStudio.objects.get_or_create(cuenta=cuenta)
    return carrito


def cantidad_items_carrito(cuenta: CuentaAula | None) -> int:
    if not cuenta:
        return 0
    carrito = CarritoStudio.objects.filter(cuenta=cuenta).first()
    if not carrito:
        return 0
    return carrito.items.count()


def agregar_al_carrito(cuenta: CuentaAula, publicacion_id: int) -> tuple[ItemCarritoStudio | None, str | None]:
    pub = (
        PublicacionStudio.objects.filter(pk=publicacion_id)
        .select_related('curso', 'creador')
        .first()
    )
    if not pub:
        return None, 'Publicación no encontrada.'
    curso = curso_disponible_en_studio(cuenta.estudiante, pub.curso_id)
    if not curso:
        return None, 'Ese curso no está disponible en el catálogo Studio.'
    if pub.precio_cop <= 0:
        return None, 'Los cursos gratis se inscriben directamente, no van al carrito.'

    est = cuenta.estudiante
    if est and curso.pk in ids_cursos_inscritos(est):
        return None, 'Ya estás inscrito en ese curso.'

    carrito = obtener_o_crear_carrito(cuenta)
    if ItemCarritoStudio.objects.filter(carrito=carrito, publicacion=pub).exists():
        return None, 'Ese curso ya está en tu carrito.'

    item = ItemCarritoStudio.objects.create(carrito=carrito, publicacion=pub)
    return item, None


def quitar_del_carrito(cuenta: CuentaAula, item_id: int) -> bool:
    carrito = CarritoStudio.objects.filter(cuenta=cuenta).first()
    if not carrito:
        return False
    deleted, _ = ItemCarritoStudio.objects.filter(pk=item_id, carrito=carrito).delete()
    return deleted > 0


def vaciar_carrito(carrito: CarritoStudio) -> None:
    carrito.items.all().delete()


@transaction.atomic
def crear_orden_desde_carrito(cuenta: CuentaAula) -> tuple[OrdenStudio | None, str | None]:
    carrito = obtener_o_crear_carrito(cuenta)
    items = list(carrito.items.select_related('publicacion', 'publicacion__curso'))
    if not items:
        return None, 'Tu carrito está vacío.'

    monto = Decimal('0')
    lineas = []
    for item in items:
        pub = item.publicacion
        curso = curso_disponible_en_studio(cuenta.estudiante, pub.curso_id)
        if not curso:
            return None, f'«{pub.curso.nombre}» ya no está disponible.'
        precio = pub.precio_cop
        if precio <= 0:
            return None, f'«{pub.curso.nombre}» es gratis; quítalo del carrito e inscríbete directo.'
        monto += precio
        lineas.append((pub, curso, precio))

    orden = OrdenStudio.objects.create(
        cuenta=cuenta,
        monto_cop=monto,
        wompi_referencia=nueva_referencia(),
        estado=OrdenStudio.ESTADO_PENDIENTE,
    )
    for pub, curso, precio in lineas:
        OrdenItemStudio.objects.create(
            orden=orden,
            publicacion=pub,
            curso=curso,
            precio_cop=precio,
        )
        # Acceso por curso vinculado a la misma referencia Wompi (metadata).
        AccesoCursoPagado.objects.create(
            cuenta=cuenta,
            curso=curso,
            monto_cop=precio,
            wompi_referencia=f'{orden.wompi_referencia}-{curso.id}',
            estado=AccesoCursoPagado.ESTADO_PENDIENTE,
            metadata={'orden_ref': orden.wompi_referencia, 'orden_id': orden.pk},
        )
    vaciar_carrito(carrito)
    return orden, None


@transaction.atomic
def marcar_orden_aprobada(
    orden: OrdenStudio,
    *,
    wompi_transaccion_id: str = '',
    metadata: dict | None = None,
) -> OrdenStudio:
    if orden.estado == OrdenStudio.ESTADO_APROBADO:
        return orden

    orden.estado = OrdenStudio.ESTADO_APROBADO
    from django.utils import timezone
    orden.pagado_en = timezone.now()
    if wompi_transaccion_id:
        orden.wompi_transaccion_id = wompi_transaccion_id
    if metadata:
        orden.metadata = {**(orden.metadata or {}), **metadata}
    orden.save()

    est = orden.cuenta.estudiante
    for item in orden.items.select_related('curso'):
        acceso = AccesoCursoPagado.objects.filter(
            cuenta=orden.cuenta,
            curso=item.curso,
            wompi_referencia=f'{orden.wompi_referencia}-{item.curso_id}',
        ).first()
        if acceso and acceso.estado != AccesoCursoPagado.ESTADO_APROBADO:
            marcar_pago_aprobado(
                acceso,
                wompi_transaccion_id=wompi_transaccion_id,
                metadata={'orden_ref': orden.wompi_referencia},
            )
        elif est:
            inscribir_estudiante_en_curso(est, item.curso)
            AccesoCursoPagado.objects.update_or_create(
                cuenta=orden.cuenta,
                curso=item.curso,
                wompi_referencia=f'{orden.wompi_referencia}-{item.curso_id}',
                defaults={
                    'estado': AccesoCursoPagado.ESTADO_APROBADO,
                    'monto_cop': item.precio_cop,
                    'wompi_transaccion_id': wompi_transaccion_id or '',
                    'metadata': {'orden_ref': orden.wompi_referencia},
                },
            )
    return orden


def marcar_orden_rechazada(orden: OrdenStudio, *, metadata: dict | None = None) -> OrdenStudio:
    orden.estado = OrdenStudio.ESTADO_RECHAZADO
    if metadata:
        orden.metadata = {**(orden.metadata or {}), **metadata}
    orden.save(update_fields=['estado', 'metadata'])
    AccesoCursoPagado.objects.filter(
        cuenta=orden.cuenta,
        wompi_referencia__startswith=f'{orden.wompi_referencia}-',
        estado=AccesoCursoPagado.ESTADO_PENDIENTE,
    ).update(estado=AccesoCursoPagado.ESTADO_RECHAZADO)
    return orden
