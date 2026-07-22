"""Métricas Nat / comercial para el portal B2B."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def checklist_preparacion_nat(org) -> list[dict]:
    """
    Semáforo operativo: qué falta para que Nat responda bien a esta org.
    Cada ítem: clave, ok, titulo, detalle, nivel (ok|warn|bad), url opcional.
    """
    from core.models import BibliotecaConocimiento, DocumentoRAGComercial, ProductoCatalogo, ProductoComercial

    linea = (getattr(org, 'numero_whatsapp_nat', '') or '').strip()
    catalogo_n = ProductoCatalogo.objects.filter(cliente_id=org.pk, activo=True).count()
    precios_n = ProductoComercial.objects.filter(cliente_id=org.pk, activo=True).count()
    bib_n = BibliotecaConocimiento.objects.filter(cliente_id=org.pk).count()
    bib_idx = BibliotecaConocimiento.objects.filter(
        cliente_id=org.pk, estado_rag='indexado'
    ).count()
    rag_legacy = DocumentoRAGComercial.objects.filter(
        cliente_id=org.pk, canal='bot_comercial'
    ).count()

    items = [
        {
            'clave': 'linea',
            'ok': bool(linea),
            'nivel': 'ok' if linea else 'bad',
            'titulo': 'Línea WhatsApp Nat',
            'detalle': (
                f'Configurada: {linea}. Debe coincidir con el To de Twilio.'
                if linea
                else 'Sin numero_whatsapp_nat: pida a eki configurarla en Admin → Cliente.'
            ),
            'url': '/portal/perfil/' if not linea else None,
        },
        {
            'clave': 'catalogo',
            'ok': catalogo_n > 0,
            'nivel': 'ok' if catalogo_n > 0 else 'warn',
            'titulo': 'Catálogo de recomendaciones',
            'detalle': (
                f'{catalogo_n} producto(s) activos (dosis, problemas, link).'
                if catalogo_n
                else 'Sin productos: Nat recomienda poco. Cargue su catálogo.'
            ),
            'url': '/portal/catalogo/nuevo/' if catalogo_n == 0 else '/portal/catalogo/',
        },
        {
            'clave': 'precios',
            'ok': precios_n > 0,
            'nivel': 'ok' if precios_n > 0 else 'warn',
            'titulo': 'Lista de precios (SKU)',
            'detalle': (
                f'{precios_n} ítem(s) de precio oficial.'
                if precios_n
                else 'Sin precios: las consultas de costo no tendrán lista oficial.'
            ),
            'url': '/portal/precios/nuevo/' if precios_n == 0 else '/portal/precios/',
        },
        {
            'clave': 'biblioteca',
            'ok': bib_idx > 0 or rag_legacy > 0,
            'nivel': 'ok' if (bib_idx > 0 or rag_legacy > 0) else 'warn',
            'titulo': 'Conocimiento (Biblioteca)',
            'detalle': (
                f'Biblioteca: {bib_idx}/{bib_n} indexados. '
                f'Documentos RAG legacy (admin): {rag_legacy}.'
            ),
            'url': '/portal/biblioteca/nuevo/' if bib_n == 0 else '/portal/biblioteca/',
        },
    ]
    return items


def analitica_nat(org) -> dict:
    from core.models import (
        BibliotecaConocimiento,
        ConversacionRAGCandidata,
        ProductoCatalogo,
        ProductoComercial,
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
    precios_total = ProductoComercial.objects.filter(cliente_id=org.pk, activo=True).count()
    bib_total = BibliotecaConocimiento.objects.filter(cliente_id=org.pk).count()
    bib_indexados = BibliotecaConocimiento.objects.filter(
        cliente_id=org.pk, estado_rag='indexado'
    ).count()
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

    checklist = checklist_preparacion_nat(org)
    checklist_ok = sum(1 for i in checklist if i.get('ok'))
    checklist_pendientes = [i for i in checklist if not i.get('ok')]

    return {
        'sesiones_total': sesiones_total,
        'sesiones_7d': sesiones_7d,
        'sesiones_30d': sesiones_30d,
        'catalogo_total': catalogo_total,
        'precios_total': precios_total,
        'bib_total': bib_total,
        'bib_indexados': bib_indexados,
        'catalogo_top': catalogo_top,
        'pqrs_total': pqrs_q.count(),
        'pqrs_pendientes': pqrs_q.filter(estado='pendiente').count(),
        'hitl_pendientes': hitl_pendientes,
        'hitl_recientes': hitl_recientes,
        'sesiones_recientes': sesiones_recientes,
        'linea_nat': (org.numero_whatsapp_nat or '').strip() or None,
        'checklist_nat': checklist,
        'checklist_ok': checklist_ok,
        'checklist_total': len(checklist),
        'checklist_pendientes': checklist_pendientes,
    }
