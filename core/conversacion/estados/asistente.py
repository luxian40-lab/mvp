"""Estado esperando_respuesta_asistente. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from core.conversacion.claves_contexto import contexto_limpio
from core.conversacion.contexto import Contexto, Respuesta
from core.intent_detector import mensaje_indica_listo as _mensaje_indica_listo

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    ctx = estudiante.contexto_temporal or {}
    preguntas_hechas = ctx.get('preguntas_hechas', 0)
    modulos_reto_ids = ctx.get('modulos_reto_ids', [])
    progreso_id = ctx.get('progreso_id')
    _cli = estudiante.cliente if getattr(estudiante, 'cliente_id', None) else None
    _na_cli = (
        (_cli.nombre_agente_asistente if _cli and getattr(_cli, 'nombre_agente_asistente', None) else '')
        or ''
    )
    _na_curso = ''
    if progreso_id:
        try:
            from core.models import ProgresoEstudiante
            _pp = ProgresoEstudiante.objects.select_related('curso').get(id=progreso_id)
            _na_curso = (_pp.curso.nombre_agente_asistente if _pp.curso else '') or ''
        except ProgresoEstudiante.DoesNotExist:
            pass
    nombre_asistente = 'Compañero'
    print(f"💬 Asistente ({nombre_asistente}): Esperando respuesta del compañero IA")

    msg_lower = msg_body.strip().lower()
    if msg_lower in ['ayuda', 'soporte', 'ticket']:
        from core.security_handler import procesar_solicitud_soporte
        texto_respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'asistente_ayuda')
    elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
        # Audio no pudo ser transcrito — NO contar como pregunta
        print(f"🎤 Audio no transcrito en asistente — pidiendo reintento")
        from core.agentes_whatsapp import mensaje_con_titular_agente

        preguntas_restantes = 2 - preguntas_hechas
        texto_respuesta = mensaje_con_titular_agente(
            nombre_asistente,
            (
                f"No pude escuchar su audio. Por favor intente de nuevo "
                f"o escríbame su pregunta.\n\n"
                f"Le quedan {preguntas_restantes} pregunta(s). "
                "Si no tiene preguntas, Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]"
            ),
        )
    elif _mensaje_indica_listo(msg_body) or preguntas_hechas >= 2:
        # Flujo exigido: Darío -> Facilitadora (reto) al escribir listo
        print("🎯 Asistente terminó → Activando Facilitadora con reto")
        from core.models import ProgresoEstudiante
        from core.tutor_ia_modulo import (
            cargar_modulos_reto,
            generar_reto_facilitador,
            listar_modulos_cobertura_reto,
        )
        from core.models import Modulo as ModuloRetoCtx
        try:
            progreso = ProgresoEstudiante.objects.get(id=progreso_id)
        except ProgresoEstudiante.DoesNotExist:
            progreso = None
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
            _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
            from core.facilitador_perfil import nombre_display_facilitador

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
                from core.facilitador_perfil import resolver_perfil_facilitador
                from core.telemetria import registrar_reto_planteado

                _curso_plan = progreso.curso if progreso else None
                registrar_reto_planteado(
                    estudiante,
                    curso=_curso_plan,
                    modulo=(modulos_reto[-1] if modulos_reto else None),
                    reto_texto=reto,
                    modulos_cubiertos=modulos_reto_ids,
                    perfil_facilitador=resolver_perfil_facilitador(_curso_plan),
                )
            except Exception:
                logger.debug('[reto] telemetría reto_planteado omitida', exc_info=True)
            from core.tutor_ia_modulo import bloque_reto_whatsapp

            texto_respuesta = bloque_reto_whatsapp(nombre_tutor, reto)
        else:
            logger.warning(
                "reto asistente vacío | progreso_id=%s modulo_ctx=%s ids_ctx=%s",
                progreso_id,
                (ctx or {}).get('modulo_id'),
                modulos_reto_ids,
            )
            estudiante.estado_onboarding = 'completado'
            estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal)
            estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
            # Si el progreso ya está completado, no pedir *listo* como si hubiera más módulos
            _prog_fin = None
            try:
                from core.models import ProgresoEstudiante
                if progreso_id:
                    _prog_fin = ProgresoEstudiante.objects.filter(id=progreso_id).first()
            except Exception:
                _prog_fin = None
            if _prog_fin and _prog_fin.completado:
                texto_respuesta = (
                    "🎉 Ya completaste este curso.\n\n"
                    "Si el certificado aún no llega, escribe *ayuda*. "
                    "Si tienes otro curso asignado, también puedes escribir *listo*."
                )
            else:
                texto_respuesta = (
                    "Seguimos con tu curso. Escribí *listo* para continuar "
                    "o *ayuda* si necesitás soporte."
                )
    else:
        # Student asked a question to Darío — answer from RAG (max 2)
        preguntas_hechas += 1
        from core.models import ProgresoEstudiante
        from core.tutor_ia_modulo import cargar_modulos_reto, generar_respuesta_asistente
        try:
            _pr_dario = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
        except ProgresoEstudiante.DoesNotExist:
            _pr_dario = None
        modulos_reto = cargar_modulos_reto(
            modulos_reto_ids, _pr_dario.curso_id if _pr_dario else None
        )

        respuesta_dario = generar_respuesta_asistente(
            modulos_reto,
            msg_body,
            estudiante_nombre=estudiante.nombre or "Estudiante",
            nombre_asistente=nombre_asistente,
        )

        ctx['preguntas_hechas'] = preguntas_hechas
        estudiante.contexto_temporal = ctx
        estudiante.save()

        from core.agentes_whatsapp import mensaje_con_titular_agente

        if preguntas_hechas >= 2:
            texto_respuesta = mensaje_con_titular_agente(
                nombre_asistente,
                (
                    f"{respuesta_dario}\n\n"
                    f"Ya respondí sus 2 preguntas. Ahora la facilitadora le tiene un reto. "
                    f"Escriba *listo* cuando esté preparado."
                ),
            )
        else:
            texto_respuesta = mensaje_con_titular_agente(
                nombre_asistente,
                (
                    f"{respuesta_dario}\n\n"
                    f"¿Tiene otra pregunta? Le queda {2 - preguntas_hechas} pregunta más. "
                    "Puede preguntar sobre el tema del curso. Si no, Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]"
                ),
            )
    return Respuesta(texto=texto_respuesta)
