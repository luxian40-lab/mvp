"""Métricas Nat / comercial para el portal B2B."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone


def analitica_nat(org) -> dict:
    from core.models import (
        ConversacionRAGCandidata,
        ProductoCatalogo,
        SesionComercial,
        SolicitudSoporte,
    )

    from .capabilities import categorias_pqrs_portal

    hace_7 = timezone.now() - timedelta(days=7)
    hace_30 = timezone.now() - timedelta(days=30)

    sesiones = SesionComercial.objects.filter(cliente_id=org.pk)
    sesiones_total = sesiones.count()
    sesiones_7d = sesiones.filter(fecha_ultimo_mensaje__gte=hace_7).count()
    sesiones_30d = sesiones.filter(fecha_ultimo_mensaje__gte=hace_30).count()

    catalogo_total = ProductoCatalogo.objects.filter(cliente_id=org.pk, activo=True).count()
    catalogo_top = list(
        ProductoCatalogo.objects.filter(cliente_id=org.pk, activo=True)
        .order_by('categoria', 'nombre')[:12]
        .values('nombre', 'categoria', 'precio_cop')
    )

    pqrs_q = SolicitudSoporte.objects.filter(estudiante__cliente=org)
    cats = categorias_pqrs_portal(org)
    if cats is not None:
        pqrs_q = pqrs_q.filter(categoria__in=cats)

    hitl_q = ConversacionRAGCandidata.objects.filter(cliente_id=org.pk)
    hitl_pendientes = hitl_q.filter(estado=ConversacionRAGCandidata.ESTADO_PENDIENTE).count()
    hitl_recientes = list(
        hitl_q.select_related('sesion').order_by('-fecha_creacion')[:15]
    )

    sesiones_recientes = list(
        sesiones.order_by('-fecha_ultimo_mensaje')[:15]
    )

    return {
        'sesiones_total': sesiones_total,
        'sesiones_7d': sesiones_7d,
        'sesiones_30d': sesiones_30d,
        'catalogo_total': catalogo_total,
        'catalogo_top': catalogo_top,
        'pqrs_total': pqrs_q.count(),
        'pqrs_pendientes': pqrs_q.filter(estado='pendiente').count(),
        'hitl_pendientes': hitl_pendientes,
        'hitl_recientes': hitl_recientes,
        'sesiones_recientes': sesiones_recientes,
        'linea_nat': (org.numero_whatsapp_nat or '').strip() or None,
    }
