"""
Knowledge Studio — cola HITL y publicación de conocimiento validado (Parte 4).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)


def crear_candidata_hitl(
    *,
    cliente,
    sesion,
    telefono: str,
    pregunta: str,
    respuesta_nati: str,
    contexto_agro: dict | None = None,
    chunks_rag: list | None = None,
    trace_id=None,
) -> 'ConversacionRAGCandidata | None':
    """Registra una conversación como candidata a revisión agronómica."""
    from core.ai_capabilities import resolver_ai_capability
    from core.models import ConversacionRAGCandidata

    if not resolver_ai_capability('hitl_rag_publish', cliente=cliente):
        return None
    if not (pregunta or '').strip() or not (respuesta_nati or '').strip():
        return None
    # Evitar duplicados recientes misma pregunta
    dup = ConversacionRAGCandidata.objects.filter(
        telefono=telefono,
        pregunta__iexact=pregunta.strip()[:500],
        estado=ConversacionRAGCandidata.ESTADO_PENDIENTE,
    ).exists()
    if dup:
        return None

    return ConversacionRAGCandidata.objects.create(
        cliente=cliente,
        sesion=sesion,
        telefono=telefono,
        trace_id=trace_id,
        pregunta=pregunta.strip(),
        respuesta_nati=respuesta_nati.strip(),
        contexto_agro=contexto_agro or {},
        chunks_rag=chunks_rag or [],
        estado=ConversacionRAGCandidata.ESTADO_PENDIENTE,
    )


def revisar_candidata(candidata, *, usuario, accion: str, respuesta_revisada: str = '', notas: str = '') -> None:
    from core.models import ConversacionRAGCandidata

    candidata.revisado_por = usuario
    candidata.fecha_revision = timezone.now()
    candidata.notas_revisor = notas or ''
    if respuesta_revisada:
        candidata.respuesta_revisada = respuesta_revisada.strip()

    if accion == 'aprobar':
        candidata.estado = ConversacionRAGCandidata.ESTADO_APROBADA
        if not candidata.respuesta_revisada:
            candidata.respuesta_revisada = candidata.respuesta_nati
    elif accion == 'rechazar':
        candidata.estado = ConversacionRAGCandidata.ESTADO_RECHAZADA
    else:
        raise ValueError(f'Acción HITL desconocida: {accion}')
    candidata.save()


def publicar_candidata_en_rag(candidata, *, usuario) -> dict[str, Any]:
    """Indexa la respuesta revisada en RAG comercial del cliente."""
    from core.models import ConversacionRAGCandidata, DocumentoRAGComercial
    from core.rag_comercial_manager import rag_comercial_manager

    texto = (candidata.respuesta_revisada or candidata.respuesta_nati or '').strip()
    if not texto:
        return {'ok': False, 'error': 'Sin texto para publicar'}

    cliente_id = candidata.cliente_id or 0
    slug = re.sub(r'[^a-z0-9]+', '_', (candidata.pregunta or '')[:40].lower()).strip('_') or 'faq'
    nombre_doc = f'hitl_{candidata.id}_{slug}'[:180]

    ctx = candidata.contexto_agro or {}
    etiquetas = ', '.join(f'{k}={v}' for k, v in ctx.items() if v and k != 'completitud_pct')
    cuerpo = (
        f"PREGUNTA VALIDADA EN CAMPO:\n{candidata.pregunta}\n\n"
        f"RESPUESTA AGRONÓMICA VALIDADA:\n{texto}\n\n"
        f"CONTEXTO: {etiquetas or 'general'}\n"
        f"Publicado por revisión HITL eki."
    )

    chunks_indexados = 0
    if rag_comercial_manager.disponible:
        chunks_indexados = rag_comercial_manager.procesar_texto(
            cliente_id,
            'bot_comercial',
            cuerpo,
            nombre_doc,
            tipo='faq',
        )

    doc = DocumentoRAGComercial.objects.filter(
        cliente_id=candidata.cliente_id,
        canal='bot_comercial',
        nombre=nombre_doc,
    ).first()

    candidata.estado = ConversacionRAGCandidata.ESTADO_PUBLICADA
    candidata.revisado_por = usuario
    candidata.fecha_revision = timezone.now()
    if doc:
        candidata.documento_rag = doc
        if chunks_indexados == 0 and doc.estado != 'indexado':
            doc.estado = 'indexado'
            doc.save(update_fields=['estado'])
    candidata.save()

    return {'ok': True, 'nombre_doc': nombre_doc, 'chunks': chunks_indexados}


def calcular_salud_rag(cliente_id: int | None = None) -> dict[str, Any]:
    from core.models import ConversacionRAGCandidata, DocumentoRAGComercial
    from core.rag_comercial_manager import rag_comercial_manager

    docs_q = DocumentoRAGComercial.objects.all()
    if cliente_id:
        docs_q = docs_q.filter(cliente_id=cliente_id)
    total = docs_q.count()
    indexados = docs_q.filter(estado='indexado').count()
    errores = docs_q.filter(estado='error').count()
    pendientes = docs_q.filter(estado='pendiente').count()

    cand_q = ConversacionRAGCandidata.objects.all()
    if cliente_id:
        cand_q = cand_q.filter(cliente_id=cliente_id)

    chunks_total = 0
    if rag_comercial_manager.disponible and cliente_id is not None:
        try:
            chunks_total = rag_comercial_manager.contar_chunks(cliente_id, 'bot_comercial')
        except Exception:
            chunks_total = 0

    return {
        'documentos_total': total,
        'documentos_indexados': indexados,
        'documentos_error': errores,
        'documentos_pendientes': pendientes,
        'chunks_indexados': chunks_total,
        'candidatas_pendientes': cand_q.filter(estado=ConversacionRAGCandidata.ESTADO_PENDIENTE).count(),
        'candidatas_publicadas': cand_q.filter(estado=ConversacionRAGCandidata.ESTADO_PUBLICADA).count(),
        'rag_disponible': rag_comercial_manager.disponible,
    }
