"""Vistas admin — eventos IA y conversation replay (Parte 2A)."""

from __future__ import annotations

import uuid

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from core.eventos_ia import serializar_evento
from core.models import EventoIA


def _queryset_eventos(request):
    qs = EventoIA.objects.select_related('estudiante', 'curso', 'modulo', 'cliente')
    tipo = (request.GET.get('tipo') or '').strip()
    trace = (request.GET.get('trace_id') or '').strip()
    estudiante_id = (request.GET.get('estudiante_id') or '').strip()
    if tipo:
        qs = qs.filter(tipo=tipo)
    if trace:
        try:
            qs = qs.filter(trace_id=uuid.UUID(trace))
        except ValueError:
            qs = qs.none()
    if estudiante_id.isdigit():
        qs = qs.filter(estudiante_id=int(estudiante_id))
    return qs


@staff_member_required
def ai_ops_eventos_view(request):
    """Listado de eventos IA — hub de observabilidad."""
    qs = _queryset_eventos(request).order_by('-created_at')[:200]
    context = {
        'eventos': qs,
        'tipos': EventoIA.TIPO_CHOICES,
        'filtro_tipo': request.GET.get('tipo', ''),
        'filtro_trace': request.GET.get('trace_id', ''),
        'filtro_estudiante': request.GET.get('estudiante_id', ''),
    }
    return render(request, 'admin/ai_ops_eventos.html', context)


@staff_member_required
def ai_ops_replay_view(request, trace_id):
    """Timeline de un trace_id — conversation replay."""
    try:
        uid = uuid.UUID(str(trace_id))
    except ValueError:
        uid = None
    eventos = []
    if uid:
        eventos = list(
            EventoIA.objects.filter(trace_id=uid)
            .select_related('estudiante', 'curso', 'modulo', 'cliente')
            .order_by('created_at')
        )
    context = {
        'trace_id': trace_id,
        'eventos': eventos,
        'trace_valido': bool(uid and eventos),
    }
    return render(request, 'admin/ai_ops_replay.html', context)


@staff_member_required
@require_GET
def api_eventos_ia_json(request):
    """API JSON para tab AI Operations del dashboard unificado."""
    limit = request.GET.get('limit', '50')
    try:
        limit_n = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        limit_n = 50
    qs = _queryset_eventos(request).order_by('-created_at')[:limit_n]
    return JsonResponse({
        'schema': 'eventos_ia_v1',
        'total': qs.count() if hasattr(qs, 'count') else len(qs),
        'eventos': [serializar_evento(e) for e in qs],
    })
