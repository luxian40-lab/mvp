"""Estado esperando_respuesta_pregunta_abierta_final. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from django.utils import timezone

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
            curso_obj = pregunta.curso if pregunta and pregunta.curso_id else (progreso.curso if progreso else None)
            modulos_eval = list(curso_obj.modulos.all().order_by('numero')) if curso_obj else []
            puntaje_final_10 = 7
            feedback_final = (
                "1. Gracias por su respuesta; usted sí propone una línea de acción.\n\n"
                "2. Para subir nivel, faltó precisión objetiva en dos partes: "
                "(a) diagnóstico: qué señales mediría, cuánto y en qué tiempo; "
                "(b) control: qué acción exacta aplicaría, con qué frecuencia y criterio de verificación.\n\n"
                "3. Puntaje total: 7/10\n"
                "4. Desglose: Enfoque 2/3 | Fundamentación 3/4 | Claridad 2/3\n\n"
                "Diagnóstico: parcial | Acción/Control: parcial."
            )
            try:
                from core.tutor_ia_modulo import evaluar_reto_facilitador
                from core.gamificacion_modo import (
                    get_modo_gamificacion,
                    modo_usa_calificacion,
                    gamificacion_otorga_puntos,
                    formatear_nota,
                    registrar_nota_gamificacion,
                    resumen_calificaciones_estudiante,
                )

                modo_gami = get_modo_gamificacion(
                    getattr(estudiante, 'cliente', None),
                )
                from core.sandbox_canal import poner_reaccion_espera

                poner_reaccion_espera(telefono_limpio, msg_sid)
                puntaje_final, feedback_final = evaluar_reto_facilitador(
                    modulos_eval,
                    msg_body,
                    pregunta.pregunta,
                    estudiante_nombre=estudiante.nombre or "Estudiante",
                    curso_nombre=(getattr(curso_obj, 'nombre', None) if curso_obj else None),
                    modo_gamificacion=modo_gami,
                )
            except Exception as e:
                logger.warning(f"⚠️ No se pudo evaluar pregunta abierta final con IA: {e}")

            respuesta_final.estado = 'calificada'
            if modo_usa_calificacion(getattr(estudiante, 'cliente', None)):
                nota = float(puntaje_final)
                respuesta_final.calificacion = int(round(nota * 10))
            else:
                respuesta_final.calificacion = int(
                    max(1, min(10, int(puntaje_final))) * 10,
                )
            respuesta_final.retroalimentacion = feedback_final
            respuesta_final.fecha_calificacion = timezone.now()
            respuesta_final.save(update_fields=['estado', 'calificacion', 'retroalimentacion', 'fecha_calificacion'])

            puntos_msg = ""
            try:
                if modo_usa_calificacion(getattr(estudiante, 'cliente', None)):
                    nota_f = float(puntaje_final)
                    registrar_nota_gamificacion(
                        estudiante,
                        nota_f,
                        'pregunta_abierta',
                        curso=curso_obj,
                        detalle='Pregunta abierta final',
                    )
                    res_n = resumen_calificaciones_estudiante(
                        estudiante,
                        curso_obj.id if curso_obj else None,
                    )
                    prom = res_n.get('promedio')
                    extra_prom = (
                        f"\n📊 *Promedio acumulado:* {formatear_nota(prom)}/5"
                        if prom is not None else ''
                    )
                    puntos_msg = (
                        f"\n\n*Nota:* {formatear_nota(nota_f)}/5{extra_prom}"
                    )
                elif gamificacion_otorga_puntos(
                    getattr(estudiante, 'cliente', None), curso_obj,
                ):
                    from core.gamificacion import PerfilGamificacion
                    from core.response_templates import _barra_progreso

                    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                    puntaje_10 = int(puntaje_final)
                    puntos_abierta = int(max(1, min(10, puntaje_10)) * 5)
                    perfil.agregar_puntos(
                        puntos_abierta,
                        f"Pregunta abierta final: {puntaje_10}/10",
                    )
                    perfil.refresh_from_db()

                    porcentaje = progreso.porcentaje_avance() if progreso else 100
                    barra = _barra_progreso(porcentaje)
                    puntos_msg = (
                        f"\n\n💰 *+{puntos_abierta} puntos* → Total: *{perfil.puntos_totales} pts*\n"
                        f"{barra} {porcentaje}%"
                    )
            except Exception as e:
                logger.warning(f"⚠️ No se pudieron aplicar puntos por pregunta abierta final: {e}")

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
                estudiante.contexto_temporal = {
                    'tipo': 'pregunta_abierta_final',
                    'curso_id': progreso.curso.id,
                    'progreso_id': progreso.id,
                    'pregunta_abierta_final_id': siguiente_pregunta.id,
                }
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
                # Mantener el flujo general: después de la última pregunta final,
                # se entrega certificado y se cierra el curso.
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

                # Radar/empleabilidad pausado: no envía Subachoque.
                radar_msg = _radar_msg_si_aplica(estudiante)

                estudiante.estado_onboarding = 'curso_finalizado'
                estudiante.contexto_temporal = None
                estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])

                partes_finales = [f"*Facilitadora*\n\n{feedback_final}{puntos_msg}"]
                if radar_msg:
                    partes_finales.append(radar_msg)
                if msg_cert_img:
                    partes_finales.append(msg_cert_img)
                texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes_finales)
        else:
            texto_respuesta = (
                "No encuentro una pregunta abierta final activa para tu curso en este momento. "
                "Escribe *ayuda* para soporte."
            )
    return Respuesta(texto=texto_respuesta)
