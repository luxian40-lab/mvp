"""Único paso Compañero → Formador.

Lo llama el estado `esperando_respuesta_asistente` y el intent
`continuar_leccion` cuando el botón/drip entra por ahí. Misma transición,
mismo contexto, mismo texto. No marca el curso como completado.
"""
from __future__ import annotations

import logging

logger = logging.getLogger('core.views.webhook_twilio')


def lanzar_reto_tras_companero(estudiante, ctx, contexto_limpio, *, progreso_si_falta=None):
    """Abre el reto del Formador. Devuelve el texto a enviar."""
    print("🎯 Asistente terminó → Activando Facilitadora con reto")
    from core.models import ProgresoEstudiante
    from core.tutor_ia_modulo import (
        cargar_modulos_reto,
        generar_reto_facilitador,
        listar_modulos_cobertura_reto,
    )
    from core.models import Modulo as ModuloRetoCtx

    ctx = ctx or {}
    progreso_id = ctx.get('progreso_id') or getattr(progreso_si_falta, 'id', None)
    modulos_reto_ids = list(ctx.get('modulos_reto_ids') or [])
    try:
        progreso = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
    except ProgresoEstudiante.DoesNotExist:
        progreso = progreso_si_falta
    modulos_reto = cargar_modulos_reto(
        modulos_reto_ids, progreso.curso_id if progreso else None
    )
    if not modulos_reto and progreso and ctx.get('modulo_id'):
        _mchk = ModuloRetoCtx.objects.filter(
            id=ctx['modulo_id'], curso_id=progreso.curso_id
        ).first()
        if _mchk:
            modulos_reto = listar_modulos_cobertura_reto(_mchk, progreso.curso)
            modulos_reto_ids = [m.id for m in modulos_reto]

    if modulos_reto and progreso:
        from core.lineas.diploma_cierre import cerrar_limbo_reto_si_cert

        _cta_cert = cerrar_limbo_reto_si_cert(estudiante, progreso)
        if _cta_cert is not None:
            return _cta_cert

        from core.curso.facilitador_perfil import nombre_display_facilitador

        nombre_tutor = nombre_display_facilitador(progreso.curso)
        reto = generar_reto_facilitador(
            modulos_reto, progreso.curso.nombre,
            estudiante_nombre=estudiante.nombre or "Estudiante",
            curso=progreso.curso,
            modulo_checkpoint=modulos_reto[-1] if modulos_reto else None,
            estudiante=estudiante,
        )
        _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
        estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
            'tipo': 'reto_facilitador',
            'modulos_reto_ids': modulos_reto_ids,
            'reto_texto': reto,
            'progreso_id': progreso_id,
            'es_final': ctx.get('es_reto_final', False),
            '_ts_leccion': _prev_ts,
        })
        estudiante.estado_onboarding = 'esperando_respuesta_reto'
        estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
        try:
            from core.curso.facilitador_perfil import resolver_perfil_facilitador
            from core.analitica.telemetria import registrar_reto_planteado

            registrar_reto_planteado(
                estudiante,
                curso=progreso.curso,
                modulo=(modulos_reto[-1] if modulos_reto else None),
                reto_texto=reto,
                modulos_cubiertos=modulos_reto_ids,
                perfil_facilitador=resolver_perfil_facilitador(progreso.curso),
            )
        except Exception:
            logger.debug('[reto] telemetría reto_planteado omitida', exc_info=True)
        from core.tutor_ia_modulo import bloque_reto_whatsapp

        return bloque_reto_whatsapp(nombre_tutor, reto)

    logger.warning(
        "reto asistente vacío | progreso_id=%s modulo_ctx=%s ids_ctx=%s",
        progreso_id,
        ctx.get('modulo_id'),
        modulos_reto_ids,
    )
    estudiante.estado_onboarding = 'completado'
    estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal)
    estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
    _prog_fin = None
    try:
        if progreso_id:
            _prog_fin = ProgresoEstudiante.objects.filter(id=progreso_id).first()
    except Exception:
        _prog_fin = None
    if _prog_fin and _prog_fin.completado:
        return (
            "🎉 Ya completaste este curso.\n\n"
            "Si el certificado aún no llega, escribe *ayuda*. "
            "Si tienes otro curso asignado, también puedes escribir *listo*."
        )
    return (
        "Seguimos con tu curso. Escribí *listo* para continuar "
        "o *ayuda* si necesitás soporte."
    )
