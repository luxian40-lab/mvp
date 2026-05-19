"""Knowledge Studio — panel admin HITL + biblioteca RAG (Parte 4)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.knowledge_studio import calcular_salud_rag, publicar_candidata_en_rag, revisar_candidata
from core.models import Cliente, ConversacionRAGCandidata, DocumentoRAGComercial


@staff_member_required
def knowledge_studio_view(request):
    """Panel principal: biblioteca, cola HITL y salud RAG."""
    cliente_id = request.GET.get('cliente_id')
    tab = (request.GET.get('tab') or 'hitl').strip().lower()
    cid = int(cliente_id) if cliente_id and str(cliente_id).isdigit() else None

    cand_q = ConversacionRAGCandidata.objects.select_related('cliente', 'revisado_por')
    docs_q = DocumentoRAGComercial.objects.select_related('cliente')
    if cid:
        cand_q = cand_q.filter(cliente_id=cid)
        docs_q = docs_q.filter(cliente_id=cid)

    context = {
        'tab': tab,
        'cliente_id': cid,
        'clientes': Cliente.objects.all().order_by('nombre'),
        'candidatas_pendientes': cand_q.filter(
            estado=ConversacionRAGCandidata.ESTADO_PENDIENTE
        ).order_by('-fecha_creacion')[:50],
        'candidatas_recientes': cand_q.exclude(
            estado=ConversacionRAGCandidata.ESTADO_PENDIENTE
        ).order_by('-fecha_revision', '-fecha_creacion')[:30],
        'biblioteca': docs_q.order_by('-fecha_subida')[:80],
        'salud': calcular_salud_rag(cid),
    }
    return render(request, 'admin/knowledge_studio.html', context)


@staff_member_required
@require_POST
def knowledge_studio_revisar(request, candidata_id):
    candidata = get_object_or_404(ConversacionRAGCandidata, pk=candidata_id)
    accion = (request.POST.get('accion') or '').strip().lower()
    respuesta = (request.POST.get('respuesta_revisada') or '').strip()
    notas = (request.POST.get('notas') or '').strip()

    if accion == 'publicar':
        if respuesta:
            candidata.respuesta_revisada = respuesta
            candidata.save(update_fields=['respuesta_revisada'])
        result = publicar_candidata_en_rag(candidata, usuario=request.user)
        if result.get('ok'):
            messages.success(request, f'Publicado en RAG como {result.get("nombre_doc")}')
        else:
            messages.error(request, result.get('error', 'Error al publicar'))
    elif accion in ('aprobar', 'rechazar'):
        revisar_candidata(candidata, usuario=request.user, accion=accion, respuesta_revisada=respuesta, notas=notas)
        messages.success(request, f'Candidata marcada como {accion}')
    else:
        messages.error(request, 'Acción no válida')

    cid = request.POST.get('cliente_id') or ''
    return redirect(f'/admin/knowledge-studio/?tab=hitl&cliente_id={cid}')
