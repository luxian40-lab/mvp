"""Contexto RAG empresa/curso para alimentar el Course Engine."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def obtener_contexto_rag_empresa(
    cliente_id: int,
    curso_id: int,
    consulta: str,
    *,
    max_chars: int = 4000,
) -> tuple[str, bool]:
    """
    RAG multi-tenant (DocumentoRAG del curso).

    Returns:
        (contexto_texto, rag_disponible)
    """
    try:
        from core.rag_manager import rag_manager

        if not rag_manager.disponible:
            logger.warning('Course Engine: Chroma/RAG no disponible en este entorno')
            return '', False

        ctx = rag_manager.obtener_contexto_para_ia(
            cliente_id=cliente_id,
            curso_id=curso_id,
            pregunta=consulta,
            max_chars=max_chars,
        )
        return (ctx or '').strip(), bool(ctx and ctx.strip())
    except Exception as exc:
        logger.exception('Course Engine RAG falló: %s', exc)
        return '', False


def resumen_documentos_curso(curso_id: int) -> str:
    """Lista documentos RAG indexados (fallback si Chroma no está)."""
    try:
        from core.models import DocumentoRAG

        docs = DocumentoRAG.objects.filter(curso_id=curso_id, estado='indexado').order_by('-fecha_indexado')[:10]
        if not docs:
            return ''
        lineas = [f'- {d.nombre} ({d.get_tipo_display()})' for d in docs]
        return 'Documentos RAG del curso:\n' + '\n'.join(lineas)
    except Exception as exc:
        logger.warning('No se pudo listar DocumentoRAG: %s', exc)
        return ''
