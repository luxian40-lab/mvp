"""KPIs operativos y comparativa de períodos para el dashboard del portal."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from core.drip_schedule import max_modulo_alcanzado
from core.metricas_empresa import calcular_metricas_empresa
from core.models import Estudiante, ProgresoEstudiante, SolicitudSoporte
from core.models_certificados import Certificado


def _mes_rango(offset_meses: int = 0):
    hoy = timezone.localdate()
    primer = hoy.replace(day=1)
    for _ in range(abs(offset_meses)):
        if offset_meses < 0:
            primer = (primer - timedelta(days=1)).replace(day=1)
        else:
            sig = primer.replace(day=28) + timedelta(days=4)
            primer = sig.replace(day=1)
    if offset_meses > 0:
        sig = primer.replace(day=28) + timedelta(days=4)
        ultimo = sig.replace(day=1) - timedelta(days=1)
    else:
        sig = primer.replace(day=28) + timedelta(days=4)
        ultimo = (sig.replace(day=1) - timedelta(days=1)) if offset_meses < 0 else hoy
    return primer, ultimo


def _delta_pct(actual: int, anterior: int) -> int | None:
    if anterior == 0:
        return None if actual == 0 else 100
    return round((actual - anterior) / anterior * 100)


def comparativa_periodos(org) -> dict:
    """Mes actual vs mes anterior (certificados, PQRS nuevas, inscripciones completadas)."""
    ini_act, fin_act = _mes_rango(0)
    ini_ant, fin_ant = _mes_rango(-1)

    cert_act = Certificado.objects.filter(
        estudiante__cliente=org, emitido=True,
        fecha_emision__date__gte=ini_act, fecha_emision__date__lte=fin_act,
    ).count()
    cert_ant = Certificado.objects.filter(
        estudiante__cliente=org, emitido=True,
        fecha_emision__date__gte=ini_ant, fecha_emision__date__lte=fin_ant,
    ).count()

    pqrs_act = SolicitudSoporte.objects.filter(
        estudiante__cliente=org,
        fecha_solicitud__date__gte=ini_act, fecha_solicitud__date__lte=fin_act,
    ).count()
    pqrs_ant = SolicitudSoporte.objects.filter(
        estudiante__cliente=org,
        fecha_solicitud__date__gte=ini_ant, fecha_solicitud__date__lte=fin_ant,
    ).count()

    comp_act = ProgresoEstudiante.objects.filter(
        curso__cliente=org, completado=True,
        fecha_completado__date__gte=ini_act, fecha_completado__date__lte=fin_act,
    ).count()
    comp_ant = ProgresoEstudiante.objects.filter(
        curso__cliente=org, completado=True,
        fecha_completado__date__gte=ini_ant, fecha_completado__date__lte=fin_ant,
    ).count()

    return {
        'mes_actual': ini_act.strftime('%B %Y'),
        'mes_anterior': ini_ant.strftime('%B %Y'),
        'certificados': {'actual': cert_act, 'anterior': cert_ant, 'delta_pct': _delta_pct(cert_act, cert_ant)},
        'pqrs': {'actual': pqrs_act, 'anterior': pqrs_ant, 'delta_pct': _delta_pct(pqrs_act, pqrs_ant)},
        'completados': {'actual': comp_act, 'anterior': comp_ant, 'delta_pct': _delta_pct(comp_act, comp_ant)},
    }


def operacion_del_dia(org, *, categorias_pqrs=None) -> dict:
    """Acciones pendientes y actividad reciente."""
    from core.models import WhatsappLog

    hoy = timezone.localdate()
    semana = hoy - timedelta(days=7)
    hace_30 = hoy - timedelta(days=30)

    pqrs_q = SolicitudSoporte.objects.filter(estudiante__cliente=org, estado='pendiente')
    if categorias_pqrs is not None:
        pqrs_q = pqrs_q.filter(categoria__in=categorias_pqrs)

    sin_avance = 0
    inactivos_30 = 0
    progresos = ProgresoEstudiante.objects.filter(
        curso__cliente=org, completado=False,
    ).select_related('estudiante')
    for p in progresos:
        if max_modulo_alcanzado(p) <= 0:
            sin_avance += 1
        elif p.fecha_ultimo_avance and p.fecha_ultimo_avance.date() < hace_30:
            inactivos_30 += 1
        elif not p.fecha_ultimo_avance:
            inactivos_30 += 1

    telefonos = list(
        Estudiante.objects.filter(cliente=org, activo=True)
        .exclude(telefono='')
        .values_list('telefono', flat=True)[:2000]
    )
    ultimos_msgs = []
    if telefonos:
        for log in WhatsappLog.objects.filter(telefono__in=telefonos).order_by('-fecha')[:8]:
            ultimos_msgs.append({
                'telefono': log.telefono,
                'mensaje': (log.mensaje or '')[:120],
                'fecha': log.fecha,
                'tipo': log.tipo,
            })

    return {
        'pqrs_pendientes': pqrs_q.count(),
        'certificados_semana': Certificado.objects.filter(
            estudiante__cliente=org, emitido=True,
            fecha_emision__date__gte=semana,
        ).count(),
        'sin_avance': sin_avance,
        'inactivos_30_dias': inactivos_30,
        'ultimos_mensajes': ultimos_msgs,
        'resumen': calcular_metricas_empresa(cliente_id=org.pk).get('resumen', {}),
    }
