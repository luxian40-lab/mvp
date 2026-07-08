"""Pagos Studio (Wompi) y validación de acceso a cursos de pago."""

from __future__ import annotations

import secrets
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from core.models import Curso

from .catalogo_service import inscribir_estudiante_en_curso
from .models import AccesoCursoPagado, CuentaAula, PublicacionStudio


def publicacion_studio(curso: Curso) -> PublicacionStudio | None:
    return PublicacionStudio.objects.filter(curso=curso).select_related('creador').first()


def precio_curso_studio(curso: Curso) -> Decimal:
    pub = publicacion_studio(curso)
    if pub:
        return pub.precio_cop
    return Decimal('0')


def curso_requiere_pago(curso: Curso) -> bool:
    return precio_curso_studio(curso) > 0


def tiene_acceso_curso(cuenta: CuentaAula | None, curso: Curso) -> bool:
    if not curso_requiere_pago(curso):
        return True
    if cuenta is None:
        return False
    return AccesoCursoPagado.objects.filter(
        cuenta=cuenta,
        curso=curso,
        estado=AccesoCursoPagado.ESTADO_APROBADO,
    ).exists()


def _nueva_referencia() -> str:
    return f'eki-{secrets.token_hex(12)}'


def crear_intento_pago(cuenta: CuentaAula, curso: Curso) -> AccesoCursoPagado:
    monto = precio_curso_studio(curso)
    return AccesoCursoPagado.objects.create(
        cuenta=cuenta,
        curso=curso,
        monto_cop=monto,
        wompi_referencia=_nueva_referencia(),
        estado=AccesoCursoPagado.ESTADO_PENDIENTE,
    )


def marcar_pago_aprobado(
    acceso: AccesoCursoPagado,
    *,
    wompi_transaccion_id: str = '',
    metadata: dict | None = None,
) -> AccesoCursoPagado:
    acceso.estado = AccesoCursoPagado.ESTADO_APROBADO
    acceso.pagado_en = timezone.now()
    if wompi_transaccion_id:
        acceso.wompi_transaccion_id = wompi_transaccion_id
    if metadata:
        acceso.metadata = {**(acceso.metadata or {}), **metadata}
    acceso.save()

    est = acceso.cuenta.estudiante
    if est:
        inscribir_estudiante_en_curso(est, acceso.curso)
    return acceso


def url_checkout_wompi(acceso: AccesoCursoPagado, request) -> str:
    """
    URL de checkout. En producción: Widget/Link Wompi.
    MVP: página interna de confirmación simulada hasta integrar API.
    """
    return request.build_absolute_uri(
        f'/studio/pagar/{acceso.wompi_referencia}/',
    )


def wompi_llave_publica() -> str:
    return getattr(settings, 'WOMPI_PUBLIC_KEY', '') or ''


def wompi_integracion_activa() -> bool:
    return bool(getattr(settings, 'WOMPI_PUBLIC_KEY', ''))
