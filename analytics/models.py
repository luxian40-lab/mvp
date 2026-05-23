"""Modelos proxy de métricas — misma tabla core.*."""
from core.models import EventoIA as _EventoIA, MetaMetricaEmpresa as _MetaMetricaEmpresa


class MetaMetricaEmpresa(_MetaMetricaEmpresa):
    class Meta:
        proxy = True
        app_label = 'analytics'
        verbose_name = _MetaMetricaEmpresa._meta.verbose_name
        verbose_name_plural = _MetaMetricaEmpresa._meta.verbose_name_plural


class EventoIA(_EventoIA):
    class Meta:
        proxy = True
        app_label = 'analytics'
        verbose_name = _EventoIA._meta.verbose_name
        verbose_name_plural = _EventoIA._meta.verbose_name_plural
