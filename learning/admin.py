from django.contrib import admin

from core.admin_mixins import register_core_proxy_admin
from core.admin import (
    AliadoEmpleabilidadAdmin,
    AuditLogAdmin,
    BadgeAdmin,
    BadgeEstudianteAdmin,
    CanjeRecompensaAdmin,
    CertificadoAdmin,
    ExamenAdmin,
    MisionEmpleabilidadAdmin,
    PerfilGamificacionAdmin,
    PlantillaCertificadoAdmin,
    PQRSAdmin,
    PreguntaAbiertaFinalCursoAdmin,
    PreguntaExamenAdmin,
    RecompensaAdmin,
    RespuestaAbiertaFinalAdmin,
    ResultadoExamenAdmin,
    TransaccionPuntosAdmin,
)

from .models import (
    AliadoEmpleabilidad,
    AuditLog,
    Badge,
    BadgeEstudiante,
    CanjeRecompensa,
    Certificado,
    Examen,
    MisionEmpleabilidad,
    PerfilGamificacion,
    PlantillaCertificado,
    PQRS,
    PreguntaAbiertaFinalCurso,
    PreguntaExamen,
    Recompensa,
    RespuestaAbiertaFinal,
    ResultadoExamen,
    TransaccionPuntos,
)

register_core_proxy_admin(admin.site, Examen, ExamenAdmin)
register_core_proxy_admin(admin.site, PreguntaExamen, PreguntaExamenAdmin)
register_core_proxy_admin(admin.site, ResultadoExamen, ResultadoExamenAdmin)
register_core_proxy_admin(admin.site, PreguntaAbiertaFinalCurso, PreguntaAbiertaFinalCursoAdmin)
register_core_proxy_admin(admin.site, RespuestaAbiertaFinal, RespuestaAbiertaFinalAdmin)
register_core_proxy_admin(admin.site, PerfilGamificacion, PerfilGamificacionAdmin)
register_core_proxy_admin(admin.site, Badge, BadgeAdmin)
register_core_proxy_admin(admin.site, BadgeEstudiante, BadgeEstudianteAdmin)
register_core_proxy_admin(admin.site, TransaccionPuntos, TransaccionPuntosAdmin)
register_core_proxy_admin(admin.site, Recompensa, RecompensaAdmin)
register_core_proxy_admin(admin.site, CanjeRecompensa, CanjeRecompensaAdmin)
register_core_proxy_admin(admin.site, AliadoEmpleabilidad, AliadoEmpleabilidadAdmin)
register_core_proxy_admin(admin.site, MisionEmpleabilidad, MisionEmpleabilidadAdmin)
register_core_proxy_admin(admin.site, Certificado, CertificadoAdmin)
register_core_proxy_admin(admin.site, PlantillaCertificado, PlantillaCertificadoAdmin)
register_core_proxy_admin(admin.site, AuditLog, AuditLogAdmin)
register_core_proxy_admin(admin.site, PQRS, PQRSAdmin)
