"""Modelos proxy — misma tabla core.*, sección propia en el admin."""
from core.models import (
    CampanaB2B as _CampanaB2B,
    ContextoAgroSession as _ContextoAgroSession,
    ConversacionRAGCandidata as _ConversacionRAGCandidata,
    DocumentoRAGComercial as _DocumentoRAGComercial,
    MetaMetricaNati as _MetaMetricaNati,
    ProspectoB2B as _ProspectoB2B,
)


class ProspectoB2B(_ProspectoB2B):
    class Meta:
        proxy = True
        app_label = 'agents_commercial'
        verbose_name = _ProspectoB2B._meta.verbose_name
        verbose_name_plural = _ProspectoB2B._meta.verbose_name_plural


class CampanaB2B(_CampanaB2B):
    class Meta:
        proxy = True
        app_label = 'agents_commercial'
        verbose_name = _CampanaB2B._meta.verbose_name
        verbose_name_plural = _CampanaB2B._meta.verbose_name_plural


class DocumentoRAGComercial(_DocumentoRAGComercial):
    class Meta:
        proxy = True
        app_label = 'agents_commercial'
        verbose_name = _DocumentoRAGComercial._meta.verbose_name
        verbose_name_plural = _DocumentoRAGComercial._meta.verbose_name_plural


class MetaMetricaNati(_MetaMetricaNati):
    class Meta:
        proxy = True
        app_label = 'agents_commercial'
        verbose_name = _MetaMetricaNati._meta.verbose_name
        verbose_name_plural = _MetaMetricaNati._meta.verbose_name_plural


class ContextoAgroSession(_ContextoAgroSession):
    class Meta:
        proxy = True
        app_label = 'agents_commercial'
        verbose_name = _ContextoAgroSession._meta.verbose_name
        verbose_name_plural = _ContextoAgroSession._meta.verbose_name_plural


class ConversacionRAGCandidata(_ConversacionRAGCandidata):
    class Meta:
        proxy = True
        app_label = 'agents_commercial'
        verbose_name = _ConversacionRAGCandidata._meta.verbose_name
        verbose_name_plural = _ConversacionRAGCandidata._meta.verbose_name_plural
