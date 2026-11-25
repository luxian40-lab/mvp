"""Estado esperando_respuesta_asistente. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from core.conversacion.claves_contexto import contexto_limpio
from core.conversacion.contexto import Contexto, Respuesta
from core.intent_detector import mensaje_cierre_corto_companero as _mensaje_cierre_corto
from core.intent_detector import mensaje_declina_preguntas as _mensaje_declina_preguntas
from core.intent_detector import mensaje_indica_listo_o_confirma_handoff as _mensaje_indica_listo
from core.intent_detector import mensaje_parece_pregunta_companero as _mensaje_parece_pregunta

logger = logging.getLogger('core.views.webhook_twilio')

_REPREGUNTA_COMPANERO = (
    'Si tiene una pregunta sobre el curso, escríbala o envíe un audio. '
    'Si no, pulse continuar, para seguir aprendiendo.\n\n'
    '[SEND_BUTTON:continuemos]'
)


def _debe_abrir_reto(msg_body: str, preguntas_hechas: int) -> bool:
    return (
        _mensaje_indica_listo(msg_body)
        or _mensaje_declina_preguntas(msg_body)
        or _mensaje_cierre_corto(msg_body)
        or preguntas_hechas >= 2
    )


def _responder_pregunta_companero(
    estudiante, msg_body, ctx, progreso_id, modulos_reto_ids, nombre_asistente, preguntas_hechas,
) -> str:
    """Una pregunta clara al Compañero (máx. 2). Suma cupo y responde con RAG/LLM."""
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
    ctx.pop('repregunta_companero', None)
    estudiante.contexto_temporal = ctx
    estudiante.save()

    from core.agentes_whatsapp import mensaje_con_titular_agente

    if preguntas_hechas >= 2:
        return mensaje_con_titular_agente(
            nombre_asistente,
            (
                f"{respuesta_dario}\n\n"
                f"Ya respondí sus 2 preguntas. Ahora la facilitadora le tiene un reto. "
                f"Escriba *listo* cuando esté preparado."
            ),
        )
    return mensaje_con_titular_agente(
        nombre_asistente,
        (
            f"{respuesta_dario}\n\n"
            f"¿Tiene otra pregunta? Le queda {2 - preguntas_hechas} pregunta más. "
            "Puede preguntar sobre el tema del curso. Si no, Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]"
        ),
    )


def _repregunta_sin_cupo(estudiante, ctx, nombre_asistente) -> str:
    """Ambiguo: no LLM, no cupo. Una sola repregunta."""
    from core.agentes_whatsapp import mensaje_con_titular_agente

    ctx['repregunta_companero'] = True
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['contexto_temporal'])
    return mensaje_con_titular_agente(nombre_asistente, _REPREGUNTA_COMPANERO)


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    ctx = estudiante.contexto_temporal or {}
    preguntas_hechas = ctx.get('preguntas_hechas', 0)
    modulos_reto_ids = ctx.get('modulos_reto_ids', [])
    progreso_id = ctx.get('progreso_id')
    nombre_asistente = 'Compañero'
    logger.info(f"💬 Asistente ({nombre_asistente}): Esperando respuesta del compañero IA")

    msg_lower = msg_body.strip().lower()
    if msg_lower in ['ayuda', 'soporte', 'ticket']:
        from core.conversacion.security_handler import procesar_solicitud_soporte
        texto_respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'asistente_ayuda')
    elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
        logger.info(f"🎤 Audio no transcrito en asistente — pidiendo reintento")
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
    elif _debe_abrir_reto(msg_body, preguntas_hechas):
        # listo / Ok / declina / cierre corto / cupo agotado → Formador
        texto_respuesta = _reto_tras_asistente(
            texto_respuesta, progreso_id, modulos_reto_ids, ctx, estudiante, contexto_limpio, logger,
        )
    elif _mensaje_parece_pregunta(msg_body):
        texto_respuesta = _responder_pregunta_companero(
            estudiante, msg_body, ctx, progreso_id, modulos_reto_ids,
            nombre_asistente, preguntas_hechas,
        )
    elif ctx.get('repregunta_companero'):
        # Segunda ambigüedad: no ciclar; avanzar al Formador
        texto_respuesta = _reto_tras_asistente(
            texto_respuesta, progreso_id, modulos_reto_ids, ctx, estudiante, contexto_limpio, logger,
        )
    else:
        texto_respuesta = _repregunta_sin_cupo(estudiante, ctx, nombre_asistente)
    return Respuesta(texto=texto_respuesta)


def _reto_tras_asistente(texto_respuesta, progreso_id, modulos_reto_ids, ctx, estudiante, contexto_limpio, logger):
    del texto_respuesta, progreso_id, modulos_reto_ids, logger
    from core.conversacion.checkpoint_handoff import lanzar_reto_tras_companero

    return lanzar_reto_tras_companero(estudiante, ctx, contexto_limpio)
