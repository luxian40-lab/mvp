"""Modelos proxy de evaluación, gamificación y certificados — misma tabla core.*."""
from core.models import (
    AliadoEmpleabilidad as _AliadoEmpleabilidad,
    Examen as _Examen,
    MisionEmpleabilidad as _MisionEmpleabilidad,
    PreguntaAbiertaFinalCurso as _PreguntaAbiertaFinalCurso,
    PreguntaExamen as _PreguntaExamen,
    RespuestaAbiertaFinal as _RespuestaAbiertaFinal,
    ResultadoExamen as _ResultadoExamen,
)
from core.models_audit import AuditLog as _AuditLog
from core.models_extras import PQRS as _PQRS
from core.gamificacion import (
    Badge as _Badge,
    BadgeEstudiante as _BadgeEstudiante,
    PerfilGamificacion as _PerfilGamificacion,
    TransaccionPuntos as _TransaccionPuntos,
)
from core.models_certificados import (
    Certificado as _Certificado,
    PlantillaCertificado as _PlantillaCertificado,
)
from core.recompensas import CanjeRecompensa as _CanjeRecompensa, Recompensa as _Recompensa


class Examen(_Examen):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _Examen._meta.verbose_name
        verbose_name_plural = _Examen._meta.verbose_name_plural


class PreguntaExamen(_PreguntaExamen):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _PreguntaExamen._meta.verbose_name
        verbose_name_plural = _PreguntaExamen._meta.verbose_name_plural


class ResultadoExamen(_ResultadoExamen):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _ResultadoExamen._meta.verbose_name
        verbose_name_plural = _ResultadoExamen._meta.verbose_name_plural


class PreguntaAbiertaFinalCurso(_PreguntaAbiertaFinalCurso):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _PreguntaAbiertaFinalCurso._meta.verbose_name
        verbose_name_plural = _PreguntaAbiertaFinalCurso._meta.verbose_name_plural


class RespuestaAbiertaFinal(_RespuestaAbiertaFinal):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _RespuestaAbiertaFinal._meta.verbose_name
        verbose_name_plural = _RespuestaAbiertaFinal._meta.verbose_name_plural


class PerfilGamificacion(_PerfilGamificacion):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _PerfilGamificacion._meta.verbose_name
        verbose_name_plural = _PerfilGamificacion._meta.verbose_name_plural


class Badge(_Badge):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _Badge._meta.verbose_name
        verbose_name_plural = _Badge._meta.verbose_name_plural


class BadgeEstudiante(_BadgeEstudiante):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _BadgeEstudiante._meta.verbose_name
        verbose_name_plural = _BadgeEstudiante._meta.verbose_name_plural


class TransaccionPuntos(_TransaccionPuntos):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _TransaccionPuntos._meta.verbose_name
        verbose_name_plural = _TransaccionPuntos._meta.verbose_name_plural


class Recompensa(_Recompensa):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _Recompensa._meta.verbose_name
        verbose_name_plural = _Recompensa._meta.verbose_name_plural


class CanjeRecompensa(_CanjeRecompensa):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _CanjeRecompensa._meta.verbose_name
        verbose_name_plural = _CanjeRecompensa._meta.verbose_name_plural


class AliadoEmpleabilidad(_AliadoEmpleabilidad):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _AliadoEmpleabilidad._meta.verbose_name
        verbose_name_plural = _AliadoEmpleabilidad._meta.verbose_name_plural


class MisionEmpleabilidad(_MisionEmpleabilidad):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _MisionEmpleabilidad._meta.verbose_name
        verbose_name_plural = _MisionEmpleabilidad._meta.verbose_name_plural


class Certificado(_Certificado):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _Certificado._meta.verbose_name
        verbose_name_plural = _Certificado._meta.verbose_name_plural


class PlantillaCertificado(_PlantillaCertificado):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _PlantillaCertificado._meta.verbose_name
        verbose_name_plural = _PlantillaCertificado._meta.verbose_name_plural


class AuditLog(_AuditLog):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _AuditLog._meta.verbose_name
        verbose_name_plural = _AuditLog._meta.verbose_name_plural


class PQRS(_PQRS):
    class Meta:
        proxy = True
        app_label = 'learning'
        verbose_name = _PQRS._meta.verbose_name
        verbose_name_plural = _PQRS._meta.verbose_name_plural
