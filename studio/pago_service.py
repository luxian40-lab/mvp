"""Pagos Studio (Wompi) y validación de acceso a cursos de pago."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from core.models import Curso

from .catalogo_service import inscribir_estudiante_en_curso
from .models import AccesoCursoPagado, CuentaAula, PublicacionStudio

logger = logging.getLogger(__name__)


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


nueva_referencia = _nueva_referencia


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
    if acceso.estado == AccesoCursoPagado.ESTADO_APROBADO:
        return acceso

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


def marcar_pago_rechazado(acceso: AccesoCursoPagado, *, metadata: dict | None = None) -> AccesoCursoPagado:
    acceso.estado = AccesoCursoPagado.ESTADO_RECHAZADO
    if metadata:
        acceso.metadata = {**(acceso.metadata or {}), **metadata}
    acceso.save(update_fields=['estado', 'metadata'])
    return acceso


def monto_en_centavos(monto_cop: Decimal | int | str) -> int:
    """Wompi cobra en centavos: $99.000 COP → 9900000."""
    return int(Decimal(monto_cop)) * 100


def wompi_llave_publica() -> str:
    return (getattr(settings, 'WOMPI_PUBLIC_KEY', '') or '').strip()


def wompi_llave_privada() -> str:
    return (getattr(settings, 'WOMPI_PRIVATE_KEY', '') or '').strip()


def wompi_integrity_secret() -> str:
    return (getattr(settings, 'WOMPI_INTEGRITY_SECRET', '') or '').strip()


def wompi_integracion_activa() -> bool:
    return bool(wompi_llave_publica() and wompi_integrity_secret())


def wompi_permite_simulacion() -> bool:
    """Solo sin llaves reales, o DEBUG explícito."""
    if wompi_integracion_activa() and not getattr(settings, 'DEBUG', False):
        return False
    return not wompi_integracion_activa() or getattr(settings, 'DEBUG', False)


def firma_integridad_checkout(referencia: str, monto_cop: Decimal | int) -> str:
    """
    SHA256(reference + amountInCents + currency + integrity_secret).
    https://docs.wompi.co/docs/colombia/widget-checkout-web/
    """
    secret = wompi_integrity_secret()
    if not secret:
        return ''
    raw = f'{referencia}{monto_en_centavos(monto_cop)}COP{secret}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def contexto_widget_wompi_monto(
    *,
    referencia: str,
    monto_cop: Decimal | int,
    customer_email: str = '',
    customer_name: str = '',
    redirect_url: str,
) -> dict:
    return {
        'public_key': wompi_llave_publica(),
        'currency': 'COP',
        'amount_in_cents': monto_en_centavos(monto_cop),
        'reference': referencia,
        'integrity': firma_integridad_checkout(referencia, monto_cop),
        'redirect_url': redirect_url,
        'customer_email': customer_email or '',
        'customer_name': customer_name or '',
    }


def contexto_widget_wompi(acceso: AccesoCursoPagado, *, redirect_url: str) -> dict:
    return contexto_widget_wompi_monto(
        referencia=acceso.wompi_referencia,
        monto_cop=acceso.monto_cop,
        customer_email=acceso.cuenta.email or '',
        customer_name=acceso.cuenta.nombre_visible or '',
        redirect_url=redirect_url,
    )


def validar_checksum_webhook(payload: dict, checksum_header: str) -> bool:
    """
    Valida X-Event-Checksum de Wompi cuando hay secreto de eventos.
    Si no hay secreto configurado, acepta en DEBUG; en prod exige secreto.
    """
    secret = wompi_integrity_secret()
    if not secret:
        return bool(getattr(settings, 'DEBUG', False))
    if not checksum_header:
        return False

    # Formato documentado: concatenar propiedades del event + timestamp + secret
    data = payload.get('data') or {}
    transaction = data.get('transaction') or data
    props = transaction.get('properties') if isinstance(transaction, dict) else None
    timestamp = str(payload.get('timestamp') or '')
    if isinstance(props, dict):
        pieces = ''.join(str(props[k]) for k in sorted(props.keys()))
    else:
        # Fallback: reference + amount_in_cents + status + timestamp
        pieces = ''.join([
            str(transaction.get('reference') or ''),
            str(transaction.get('amount_in_cents') or ''),
            str(transaction.get('status') or ''),
            timestamp,
        ])
    expected = hashlib.sha256(f'{pieces}{timestamp}{secret}'.encode('utf-8')).hexdigest()
    # Algunos entornos usan HMAC; aceptar igualdad o hmac.compare
    if hmac.compare_digest(expected.lower(), checksum_header.lower()):
        return True
    alt = hashlib.sha256(f'{pieces}{secret}'.encode('utf-8')).hexdigest()
    return hmac.compare_digest(alt.lower(), checksum_header.lower())


def procesar_evento_wompi(payload: dict):
    """Procesa webhook: AccesoCursoPagado (1 curso) u OrdenStudio (carrito)."""
    from .carrito_service import marcar_orden_aprobada, marcar_orden_rechazada
    from .models import OrdenStudio

    data = payload.get('data', payload)
    transaction = data.get('transaction') if isinstance(data, dict) else None
    if not isinstance(transaction, dict):
        transaction = data if isinstance(data, dict) else {}

    referencia = (
        transaction.get('reference')
        or data.get('reference')
        or data.get('referencia')
        or ''
    )
    estado_wompi = str(
        transaction.get('status') or data.get('status') or ''
    ).upper()
    txn_id = str(transaction.get('id') or data.get('id') or '')

    if not referencia:
        return None

    orden = OrdenStudio.objects.filter(wompi_referencia=referencia).first()
    if orden:
        if estado_wompi in ('APPROVED', 'APROBADA', 'APROBADO'):
            return marcar_orden_aprobada(
                orden,
                wompi_transaccion_id=txn_id,
                metadata={'webhook': payload},
            )
        if estado_wompi in ('DECLINED', 'REJECTED', 'ERROR', 'VOIDED'):
            return marcar_orden_rechazada(orden, metadata={'webhook': payload})
        return orden

    acceso = AccesoCursoPagado.objects.filter(wompi_referencia=referencia).first()
    if not acceso:
        logger.warning('Webhook Wompi: referencia desconocida %s', referencia)
        return None

    if estado_wompi in ('APPROVED', 'APROBADA', 'APROBADO'):
        return marcar_pago_aprobado(
            acceso,
            wompi_transaccion_id=txn_id,
            metadata={'webhook': payload},
        )
    if estado_wompi in ('DECLINED', 'REJECTED', 'ERROR', 'VOIDED'):
        return marcar_pago_rechazado(acceso, metadata={'webhook': payload})
    return acceso
