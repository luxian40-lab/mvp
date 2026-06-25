"""Subida de documentos RAG educativos (facilitadora) desde el portal."""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.db import transaction

from core.models import Curso, DocumentoRAG

logger = logging.getLogger(__name__)

EXTENSIONES_VALIDAS = frozenset({'.pdf', '.docx', '.txt', '.xlsx', '.xlsm'})


def slug_nombre_documento(nombre: str) -> str:
    base = re.sub(r'[^a-zA-Z0-9_-]+', '_', (nombre or '').strip().lower())
    return base[:180] or 'documento'


def encolar_indexacion_rag_curso(doc_id: int) -> None:
    def _run():
        try:
            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                import threading

                def _bg():
                    try:
                        doc = DocumentoRAG.objects.filter(pk=doc_id).first()
                        if doc and doc.archivo:
                            doc.indexar()
                    except Exception:
                        logger.exception('[portal] Indexación RAG curso falló id=%s', doc_id)

                threading.Thread(target=_bg, daemon=True, name=f'portal-rag-curso-{doc_id}').start()
            else:
                from core.tasks import indexar_documento_rag_por_id

                indexar_documento_rag_por_id.delay('core', 'DocumentoRAG', doc_id)
        except Exception:
            logger.exception('[portal] Fallo encolando RAG curso id=%s', doc_id)

    transaction.on_commit(_run)


def crear_documento_curso(
    curso: Curso,
    *,
    nombre: str,
    tipo: str,
    archivo,
    descripcion: str = '',
    subido_por=None,
) -> DocumentoRAG:
    ext = '.' + (archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else '')
    if ext not in EXTENSIONES_VALIDAS:
        raise ValueError(f'Formato no soportado ({ext}). Use PDF, DOCX, TXT o Excel.')

    slug = slug_nombre_documento(nombre)
    doc = DocumentoRAG(
        curso=curso,
        nombre=slug,
        tipo=tipo,
        estado='pendiente',
        descripcion=descripcion or '',
        subido_por=subido_por,
    )
    doc.archivo = archivo
    doc.save()
    encolar_indexacion_rag_curso(doc.pk)
    return doc


def listar_documentos_curso_org(org, *, limite: int = 80):
    return (
        DocumentoRAG.objects.filter(curso__cliente=org)
        .select_related('curso')
        .order_by('-fecha_subida', '-id')[:limite]
    )
