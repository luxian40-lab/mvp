"""Helpers de nombres y extensiones para RAG comercial (Celery y admin)."""
from __future__ import annotations

import os

from core.models import DocumentoRAGComercial

_RAG_COMERCIAL_EXT_OK = frozenset({'.pdf', '.docx', '.txt', '.xlsx', '.xlsm', '.xls'})


def _extension_archivo_comercial_ok(nombre: str) -> bool:
    ext = os.path.splitext((nombre or '').lower())[1]
    return ext in _RAG_COMERCIAL_EXT_OK


def _nombre_documento_desde_nombre_archivo(filename: str) -> str:
    """Identificador a partir del archivo subido (sin extensión), máx. 200 caracteres."""
    base = os.path.basename((filename or '').strip())
    stem, _ext = os.path.splitext(base)
    stem = (stem or base or 'documento').strip()
    return stem[:200]


def _nombre_rag_comercial_unico(cliente, canal: str, nombre_base: str, exclude_pk=None):
    """Evita violar unique_together (cliente, canal, nombre)."""
    nombre = nombre_base[:200]
    q = DocumentoRAGComercial.objects.filter(canal=canal, nombre=nombre)
    q = q.filter(cliente__isnull=True) if cliente is None else q.filter(cliente=cliente)
    if exclude_pk:
        q = q.exclude(pk=exclude_pk)
    if not q.exists():
        return nombre
    for i in range(2, 200):
        suf = f'_{i}'
        candidato = (nombre_base[: 200 - len(suf)] + suf)[:200]
        q2 = DocumentoRAGComercial.objects.filter(canal=canal, nombre=candidato)
        q2 = q2.filter(cliente__isnull=True) if cliente is None else q2.filter(cliente=cliente)
        if exclude_pk:
            q2 = q2.exclude(pk=exclude_pk)
        if not q2.exists():
            return candidato
    return (nombre_base[:190] + '_dup')[:200]