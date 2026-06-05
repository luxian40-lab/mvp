"""Subida de documentos RAG comercial desde el portal."""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.db import transaction

from core.models import Cliente, DocumentoRAGComercial

logger = logging.getLogger(__name__)

EXTENSIONES_VALIDAS = frozenset({'.pdf', '.docx', '.txt', '.xlsx', '.xlsm'})


def slug_nombre_documento(nombre: str) -> str:
    base = re.sub(r'[^a-zA-Z0-9_-]+', '_', (nombre or '').strip().lower())
    return base[:180] or 'documento'


def encolar_indexacion_rag_comercial(doc_id: int) -> None:
    def _run():
        try:
            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                import threading

                def _bg():
                    try:
                        doc = DocumentoRAGComercial.objects.filter(pk=doc_id).first()
                        if doc and doc.archivo:
                            doc.indexar()
                    except Exception:
                        logger.exception('[portal] Indexación RAG Nat falló id=%s', doc_id)

                threading.Thread(target=_bg, daemon=True, name=f'portal-rag-{doc_id}').start()
            else:
                from core.tasks import indexar_documento_rag_por_id

                indexar_documento_rag_por_id.delay('core', 'DocumentoRAGComercial', doc_id)
        except Exception:
            logger.exception('[portal] Fallo encolando RAG Nat id=%s', doc_id)

    transaction.on_commit(_run)


def crear_documento_nat(
    org: Cliente,
    *,
    nombre: str,
    tipo: str,
    archivo,
    subido_por=None,
) -> DocumentoRAGComercial:
    ext = '.' + (archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else '')
    if ext not in EXTENSIONES_VALIDAS:
        raise ValueError(f'Formato no soportado ({ext}). Use PDF, DOCX, TXT o Excel.')

    slug = slug_nombre_documento(nombre)
    doc = DocumentoRAGComercial(
        cliente=org,
        canal='bot_comercial',
        nombre=slug,
        tipo=tipo,
        estado='pendiente',
        subido_por=subido_por,
    )
    doc.archivo = archivo
    doc.save()
    encolar_indexacion_rag_comercial(doc.pk)
    return doc


def listar_documentos_nat(org: Cliente, *, limite: int = 50):
    return (
        DocumentoRAGComercial.objects.filter(cliente_id=org.pk, canal='bot_comercial')
        .order_by('-fecha_subida', '-id')[:limite]
    )
