"""KPIs de empleabilidad territorial para el portal B2B."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from core.models import Estudiante, MisionEmpleabilidad, ProgresoEstudiante, WhatsappLog

DIAS_RETENCION_DEFAULT = 30


def _misiones_qs(org):
    return MisionEmpleabilidad.objects.filter(
        Q(cliente=org) | Q(estudiante__cliente=org),
    )


def _estudiantes_activos_ids(org, desde) -> set[int]:
    """Jóvenes con interacción reciente: WhatsApp, avance de curso o misión."""
    base = Estudiante.objects.filter(cliente=org, activo=True)
    activos: set[int] = set()

    activos.update(
        WhatsappLog.objects.filter(
            tipo='INCOMING',
            fecha__gte=desde,
            estudiante__cliente=org,
            estudiante__activo=True,
        ).values_list('estudiante_id', flat=True)
    )

    activos.update(
        ProgresoEstudiante.objects.filter(
            curso__cliente=org,
            estudiante__activo=True,
            fecha_ultimo_avance__gte=desde,
        ).values_list('estudiante_id', flat=True)
    )

    activos.update(
        _misiones_qs(org).filter(
            fecha_descubierta__gte=desde,
            estudiante__activo=True,
        ).values_list('estudiante_id', flat=True)
    )

    activos.discard(None)
    return activos


def resumen_empleabilidad_portal(
    org,
    *,
    dias_retencion: int = DIAS_RETENCION_DEFAULT,
) -> dict[str, Any]:
    """
    Tres KPIs fijos del módulo empleabilidad:
    - retención (% jóvenes activos en ventana)
    - misiones completadas
    - oportunidades georreferenciadas (misiones con coordenadas, no canceladas)
    """
    dias = max(1, int(dias_retencion or DIAS_RETENCION_DEFAULT))
    desde = timezone.now() - timedelta(days=dias)

    total_inscritos = Estudiante.objects.filter(cliente=org, activo=True).count()
    activos_ids = _estudiantes_activos_ids(org, desde)
    jovenes_activos = len(activos_ids)

    if total_inscritos:
        retencion_pct = round(100.0 * jovenes_activos / total_inscritos, 1)
    else:
        retencion_pct = 0.0

    misiones_qs = _misiones_qs(org)
    misiones_completadas = misiones_qs.filter(estado='completada').count()
    oportunidades_georef = (
        misiones_qs.filter(
            latitud__isnull=False,
            longitud__isnull=False,
        )
        .exclude(estado='cancelada')
        .count()
    )

    misiones_recientes = list(
        misiones_qs.select_related('estudiante', 'aliado')
        .order_by('-fecha_descubierta')[:15]
    )

    return {
        'dias_retencion': dias,
        'total_inscritos': total_inscritos,
        'jovenes_activos': jovenes_activos,
        'retencion_pct': retencion_pct,
        'misiones_completadas': misiones_completadas,
        'oportunidades_georef': oportunidades_georef,
        'misiones_recientes': misiones_recientes,
    }
