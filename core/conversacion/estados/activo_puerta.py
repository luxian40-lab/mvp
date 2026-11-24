"""Puerta de *listo* del bloque ACTIVO: con agente activo deja pasar; si no, PQRS, reenvío de media, evaluación de paso, corrección y «No entendí». Después, el menú legado. Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.intent_detector import mensaje_indica_listo as _mensaje_indica_listo
from core.models import WhatsappLog

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta | None:
    estado_chat = contexto.estado_chat
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    msg_lower = contexto.locales['msg_lower']
    telefono_limpio = contexto.telefono_limpio
    # ============================================================
    # PRIORIDAD: Si el estudiante está interactuando con un AGENTE
    # (Darío, Facilitadora, Tutor IA, etc.), NO interceptar con
    # el gate de "solo listo" — dejar que el flujo caiga al handler
    # del agente más abajo en el código.
    # ============================================================
    estados_agente = [
        'esperando_respuesta_asistente',     # Darío
        'esperando_respuesta_reto',          # Facilitadora
        'esperando_respuesta_modulo',         # Evaluación módulo
        'esperando_respuesta_pregunta_abierta_final',  # Respuesta final calificada por facilitadora
        'esperando_nota_cierre',                     # Nota 1 a 10 antes del certificado
    ]
    from core.empleabilidad_pausa import empleabilidad_en_pausa as _emp_pausa_gate
    # Radar: código de aliado (no gate *listo*) — pausado no intercepta.
    if not _emp_pausa_gate():
        estados_agente.append('esperando_codigo_empleabilidad')
    if estudiante.estado_onboarding in estados_agente:
        logger.info(f"🤖 Agente activo ({estudiante.estado_onboarding}) — bypassing gate listo")
        # No interceptar — caerá al flujo EXISTENTE más abajo (handlers de agente)

    else:
        from core.lineas.pqrs_linea import respuesta_en_puerta
        if respuesta_en_puerta(estudiante, msg_body, msg_from, telefono_limpio):
            return CORTAR

        # 🎥 Reenvío de video/material (sin avanzar curso) — antes de eval/listo
        if estado_chat == 'ACTIVO':
            try:
                from core.media_recuperacion import intentar_reenvio_media_curso
                from core.lineas.salida_turno import entregar_en_turno
                from core.canal.twilio_media import mensaje_log_con_media

                _resp_reenvio = intentar_reenvio_media_curso(estudiante, msg_body)
                if _resp_reenvio:
                    logger.info('🎥 Reenvío media curso | est=%s', estudiante.id)
                    # Sin time.sleep: DELAY va a Celery vía entrega_delays.
                    entregar_en_turno(
                        msg_from,
                        telefono_limpio,
                        _resp_reenvio,
                        agente='REENVIAR_MEDIA',
                        registro='segmentos',
                    )
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=mensaje_log_con_media((_resp_reenvio or '')[:500], None),
                        tipo='SENT',
                        estado='SENT',
                        agente_usado='REENVIAR_MEDIA',
                    )
                    return CORTAR
            except Exception:
                logger.exception('Reenvío media curso omitido')
        from core.lineas.paso import responder_evaluacion_paso
        if responder_evaluacion_paso(
            estudiante, msg_body, msg_from, telefono_limpio, estado_chat,
        ):
            return CORTAR

        from core.lineas.pqrs_linea import corregir_datos_si_pide
        if corregir_datos_si_pide(estudiante, msg_lower, msg_from, telefono_limpio):
            return CORTAR

        if not _mensaje_indica_listo(msg_body):
            if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                texto_respuesta = (
                    "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo o escríbeme. "
                    "Para avanzar, Pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
                )
            else:
                from core.avance_whatsapp import texto_cuando_no_es_listo

                texto_respuesta = texto_cuando_no_es_listo(estudiante, msg_body)
            try:
                from core.lineas.salida_turno import enviar_respuesta_turno

                enviar_respuesta_turno(
                    msg_from,
                    texto_respuesta,
                    agente='puerta_leccion',
                )
            except Exception as e:
                logger.error(f"❌ Error enviando respuesta no entendida: {e}")
            return CORTAR

    from core.conversacion.estados import activo_menu

    if activo_menu.manejar(Contexto(
        estudiante,
        msg_body,
        msg_from,
        telefono_limpio,
        locales={'estados_agente': estados_agente, 'msg_lower': msg_lower},
    )) is not None:
        return CORTAR
    return None
