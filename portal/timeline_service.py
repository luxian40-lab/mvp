"""Línea de tiempo unificada por organización (portal clientes)."""

from __future__ import annotations

from django.utils import timezone

from core.models import ProgresoEstudiante, SolicitudSoporte
from core.models_certificados import Certificado


def timeline_organizacion(org, *, limite: int = 40) -> list[dict]:
    eventos: list[dict] = []

    for cert in (
        Certificado.objects.filter(estudiante__cliente=org, emitido=True)
        .select_related('estudiante', 'curso')
        .order_by('-fecha_emision')[:limite]
    ):
        if cert.fecha_emision:
            eventos.append({
                'fecha': cert.fecha_emision,
                'tipo': 'certificado',
                'titulo': f'Certificado — {cert.estudiante.nombre}',
                'detalle': cert.curso.nombre if cert.curso_id else '',
                'url': f'/portal/estudiantes/{cert.estudiante_id}/',
            })

    for p in (
        ProgresoEstudiante.objects.filter(curso__cliente=org, completado=True)
        .select_related('estudiante', 'curso')
        .order_by('-fecha_completado')[:limite]
    ):
        if p.fecha_completado:
            eventos.append({
                'fecha': p.fecha_completado,
                'tipo': 'completado',
                'titulo': f'Curso completado — {p.estudiante.nombre}',
                'detalle': p.curso.nombre,
                'url': f'/portal/estudiantes/{p.estudiante_id}/',
            })

    for s in (
        SolicitudSoporte.objects.filter(estudiante__cliente=org)
        .select_related('estudiante')
        .order_by('-fecha_solicitud')[:limite]
    ):
        eventos.append({
            'fecha': s.fecha_solicitud,
            'tipo': 'pqrs',
            'titulo': f'PQRS — {s.estudiante.nombre}',
            'detalle': s.get_categoria_display() if hasattr(s, 'get_categoria_display') else s.categoria,
            'url': f'/portal/pqrs/{s.pk}/',
        })

    try:
        from core.models import CampanaUnica, RespuestaCampanaUnica

        for r in (
            RespuestaCampanaUnica.objects.filter(
                campana__cliente=org,
            ).select_related('estudiante', 'campana')
            .order_by('-fecha_respuesta')[:limite]
        ):
            nombre = r.estudiante.nombre if r.estudiante_id else r.numero_telefono
            eventos.append({
                'fecha': r.fecha_respuesta,
                'tipo': 'campana',
                'titulo': f'Campaña — {nombre}',
                'detalle': f'{r.campana.nombre}: {r.get_respuesta_display()}',
                'url': f'/portal/campanas/{r.campana_id}/',
            })
    except Exception:
        pass

    eventos.sort(key=lambda e: e['fecha'] or timezone.now(), reverse=True)
    return eventos[:limite]
