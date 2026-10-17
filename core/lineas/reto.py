"""Reto de la facilitadora después de la revisión de María."""
import logging

logger = logging.getLogger(__name__)


def activar_reto_despues_de_maria(
    estudiante,
    prefijo,
    progreso_id,
    modulos_reto_ids,
    es_reto_final,
) -> str:
    from core.facilitador_perfil import nombre_display_facilitador
    from core.models import Modulo, ProgresoEstudiante
    from core.tutor_ia_modulo import (
        bloque_reto_whatsapp,
        cargar_modulos_reto,
        generar_reto_facilitador,
        listar_modulos_cobertura_reto,
    )

    progreso_r = (
        ProgresoEstudiante.objects.filter(id=progreso_id)
        .select_related('curso', 'modulo_actual')
        .first()
        if progreso_id
        else None
    )
    mids = list(modulos_reto_ids) if modulos_reto_ids else []
    modulos_reto = (
        cargar_modulos_reto(mids, progreso_r.curso_id if progreso_r else None)
        if mids
        else []
    )
    if not modulos_reto and progreso_r:
        modulo = None
        outer = estudiante.contexto_temporal or {}
        mid = outer.get('modulo_id')
        if mid:
            modulo = Modulo.objects.filter(id=mid, curso_id=progreso_r.curso_id).first()
        if not modulo and getattr(progreso_r, 'modulo_actual_id', None):
            modulo = progreso_r.modulo_actual
        if modulo:
            modulos_reto = listar_modulos_cobertura_reto(modulo, progreso_r.curso)
            mids = [m.id for m in modulos_reto]
    if not (progreso_r and modulos_reto):
        logger.warning(
            'reto post-María vacío | progreso_id=%s modulo_ctx=%s ids_ctx=%s',
            progreso_id,
            (estudiante.contexto_temporal or {}).get('modulo_id'),
            modulos_reto_ids,
        )
        estudiante.contexto_temporal = None
        estudiante.estado_onboarding = 'completado'
        estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
        if progreso_r and progreso_r.completado:
            return (
                f'{prefijo}\n\n'
                '🎉 Ya completaste este curso.\n\n'
                'Si el certificado aún no llega, escribe *ayuda*. '
                'Si tienes otro curso asignado, también puedes escribir *listo*.'
            ).strip()
        return (
            f'{prefijo}\n\n'
            'Seguimos con tu curso. Escribí *listo* para continuar '
            'o *ayuda* si necesitás soporte.'
        ).strip()
    nombre_tutor = nombre_display_facilitador(progreso_r.curso)
    reto = generar_reto_facilitador(
        modulos_reto,
        progreso_r.curso.nombre,
        estudiante_nombre=estudiante.nombre or 'Estudiante',
        curso=progreso_r.curso,
        modulo_checkpoint=modulos_reto[-1] if modulos_reto else None,
    )
    prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
    estudiante.contexto_temporal = {
        'tipo': 'reto_facilitador',
        'modulos_reto_ids': mids,
        'reto_texto': reto,
        'progreso_id': progreso_id,
        'es_final': es_reto_final,
        '_ts_leccion': prev_ts,
    }
    estudiante.estado_onboarding = 'esperando_respuesta_reto'
    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
    bloque = bloque_reto_whatsapp(nombre_tutor, reto)
    return f'{prefijo}\n\n{bloque}'.strip()
