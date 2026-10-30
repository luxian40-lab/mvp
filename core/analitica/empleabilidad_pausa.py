"""
PAUSA PRODUCTO (2026-09-21)
Radar de empleos / empleabilidad territorial (Subachoque, aliados, misiones)
fuera de WhatsApp, portal y APIs hasta nuevo aviso.

No borrar el módulo. Para reactivar: EKI_EMPLEABILIDAD_PAUSADA = False
y volver a desplegar.
"""

EKI_EMPLEABILIDAD_PAUSADA = True

# Copy histórico (no enviar mientras la pausa esté activa).
MENSAJE_RADAR_DESBLOQUEADO = (
    "📍 *¡Radar de Empleos desbloqueado!*\n\n"
    "Ve al parque principal de Subachoque y envíame tu *Ubicación* "
    "usando el clip de WhatsApp (📎)."
)


def empleabilidad_en_pausa() -> bool:
    return bool(EKI_EMPLEABILIDAD_PAUSADA)


def mensaje_radar_desbloqueado() -> str:
    if empleabilidad_en_pausa():
        return ''
    return MENSAJE_RADAR_DESBLOQUEADO


def liberar_estado_empleabilidad_si_pausada(estudiante) -> bool:
    """Si alguien quedó pidiendo código de aliado, suelta el estado al curso."""
    if not empleabilidad_en_pausa() or estudiante is None:
        return False
    if getattr(estudiante, 'estado_onboarding', None) != 'esperando_codigo_empleabilidad':
        return False

    from core.models import ProgresoEstudiante

    hay_abierto = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        completado=False,
        curso__activo=True,
    ).exists()
    estudiante.estado_onboarding = 'completado' if hay_abierto else 'curso_finalizado'
    ctx = dict(estudiante.contexto_temporal or {})
    for key in (
        'radar_empleabilidad_activo',
        'aliado_empleabilidad_objetivo_id',
        'mision_empleabilidad_id',
        'distancia_aliado_m',
        'empleabilidad_habilitado_en',
    ):
        ctx.pop(key, None)
    estudiante.contexto_temporal = ctx or None
    estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
    return True
