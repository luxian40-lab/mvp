"""Modelos proxy de IA educativa — misma tabla core.*."""
from core.models import DocumentoRAG as _DocumentoRAG


class DocumentoRAG(_DocumentoRAG):
    class Meta:
        proxy = True
        app_label = 'agents_edu'
        verbose_name = _DocumentoRAG._meta.verbose_name
        verbose_name_plural = _DocumentoRAG._meta.verbose_name_plural
