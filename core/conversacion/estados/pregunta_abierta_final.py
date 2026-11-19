"""Estado esperando_respuesta_pregunta_abierta_final. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from django.utils import timezone

from core.conversacion.claves_contexto import contexto_limpio
from core.conversacion.contexto import Contexto, Respuesta
from core.views.empleabilidad import _radar_msg_si_aplica
from core.views.ventana_drip import _pregunta_abierta_final_pendiente

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_sid = contexto.msg_sid
    telefono_limpio = contexto.telefono_limpio
    texto_respuesta = contexto.texto_respuesta
    from core.models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal, ProgresoEstudiante
    if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
        texto_respuesta = (
            "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
            "o escríbeme tu respuesta abierta final."
        )
    elif _abierta_agricapital_no_califica(estudiante, msg_body):
        from core.lineas.agricapital_experiencia import texto_reintento_reto_agricapital

        texto_respuesta = (
            texto_reintento_reto_agricapital()
            + '\n\n_Sigue siendo la pregunta abierta final; aún no tiene nota._'
        )
    else:
        ctx_open = estudiante.contexto_temporal or {}
        pregunta_id = ctx_open.get('pregunta_abierta_final_id')
        progreso_id = ctx_open.get('progreso_id')
        pregunta = PreguntaAbiertaFinalCurso.objects.filter(id=pregunta_id, activa=True).first()
        progreso = ProgresoEstudiante.objects.filter(id=progreso_id).first() if progreso_id else None

        if pregunta:
            logger.info(
                "🧾 Pregunta abierta final en contexto | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                estudiante.id,
                getattr(pregunta.curso, 'id', None),
                pregunta.id,
                getattr(pregunta, 'orden', None),
                (pregunta.pregunta or '')[:180],
            )
            respuesta_final, _ = RespuestaAbiertaFinal.objects.update_or_create(
                pregunta=pregunta,
                estudiante=estudiante,
                defaults={
                    'curso': pregunta.curso,
                    'progreso': progreso,
                    'respuesta_texto': msg_body,
                    'fecha_respuesta': timezone.now(),
                    'estado': 'pendiente',
                }
            )
            logger.info(
                "📝 Respuesta abierta final registrada | estudiante_id=%s | curso_id=%s | progreso_id=%s",
                estudiante.id,
                getattr(pregunta.curso, 'id', None),
                getattr(progreso, 'id', None),
            )

            # Evaluar con la misma rúbrica de facilitadora para dar feedback
            # inmediato y mantener coherencia de gamificación.
            _salida = _calificar_pregunta_abierta(pregunta, progreso, estudiante, telefono_limpio, msg_sid, msg_body, logger, timezone, respuesta_final)
            if not isinstance(_salida, tuple):
                return _salida
            curso_obj, feedback_final, puntos_msg = _salida

            # Si hay más preguntas abiertas pendientes (máximo 3),
            # continuar en secuencia antes de emitir certificado.
            siguiente_pregunta = _pregunta_abierta_final_pendiente(estudiante, progreso) if progreso else None
            if siguiente_pregunta:
                logger.info(
                    "🔁 Siguiente pregunta abierta final | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                    estudiante.id,
                    progreso.curso.id,
                    siguiente_pregunta.id,
                    getattr(siguiente_pregunta, 'orden', None),
                    (siguiente_pregunta.pregunta or '')[:180],
                )
                estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
                    'tipo': 'pregunta_abierta_final',
                    'curso_id': progreso.curso.id,
                    'progreso_id': progreso.id,
                    'pregunta_abierta_final_id': siguiente_pregunta.id,
                })
                estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

                texto_respuesta = (
                    "[MULTI_MSG]"
                    f"*Facilitadora*\n\n{feedback_final}{puntos_msg}"
                    "[SEP]"
                    "📝 *Siguiente pregunta abierta final*\n\n"
                    f"{siguiente_pregunta.pregunta}\n\n"
                    "✍️ Responde con tus propias palabras (texto o audio)."
                )
            else:
                from core.conversacion.estados.reto import pregunta_si_falta

                pregunta_nota = pregunta_si_falta(estudiante, curso_obj, progreso)
                if pregunta_nota:
                    texto_respuesta = (
                        f'*Facilitadora*\n\n{feedback_final}{puntos_msg}\n\n{pregunta_nota}'
                    )
                else:
                    texto_respuesta = _texto_certificado_abierta(
                        estudiante, curso_obj, feedback_final, puntos_msg,
                    )
        else:
            texto_respuesta = (
                "No encuentro una pregunta abierta final activa para tu curso en este momento. "
                "Escribe *ayuda* para soporte."
            )
    return Respuesta(texto=texto_respuesta)


def _texto_certificado_abierta(estudiante, curso_obj, feedback_final, puntos_msg) -> str:
    msg_cert_img = ""
    if curso_obj:
        try:
            from core.certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
            cert = crear_certificado_automatico(estudiante, curso_obj)
            if cert and cert.archivo_imagen:
                cert_url = obtener_url_certificado_twilio(cert)
                if cert_url:
                    msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                else:
                    s3_key = str(cert.archivo_imagen.name)
                    cert_url = f"https://eki-produccion.s3.us-east-2.amazonaws.com/{s3_key}"
                    msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
            elif cert and cert.archivo_pdf:
                msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert.archivo_pdf.url}"
            else:
                msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
        except Exception as e:
            logger.error(f"❌ Error certificado tras pregunta abierta final: {e}", exc_info=True)
            msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."

    radar_msg = _radar_msg_si_aplica(estudiante)
    estudiante.estado_onboarding = 'curso_finalizado'
    estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal)
    estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])

    partes_finales = [f"*Facilitadora*\n\n{feedback_final}{puntos_msg}"]
    if radar_msg:
        partes_finales.append(radar_msg)
    if msg_cert_img:
        partes_finales.append(msg_cert_img)
    return "[MULTI_MSG]" + "[SEP]".join(partes_finales)
