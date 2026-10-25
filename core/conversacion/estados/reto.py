"""Estado esperando_respuesta_reto. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import Contexto, Respuesta
from core.intent_detector import mensaje_indica_listo as _mensaje_indica_listo
from core.views.empleabilidad import _radar_msg_si_aplica
from core.views.ventana_drip import _pregunta_abierta_final_pendiente

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_sid = contexto.msg_sid
    telefono_limpio = contexto.telefono_limpio
    evidencia_imagen_url = contexto.evidencia_imagen_url
    evidencia_imagen_type = contexto.evidencia_imagen_type
    texto_respuesta = contexto.texto_respuesta
    print(f"📋 Facilitadora: Evaluando respuesta al reto")
    ctx = estudiante.contexto_temporal or {}
    modulos_reto_ids = ctx.get('modulos_reto_ids', [])
    reto_texto = ctx.get('reto_texto', '')
    progreso_id = ctx.get('progreso_id')

    # 📸 Foto como evidencia del reto: guardar y calificar con visión.
    evidencia_bytes = None
    evidencia_type = ''
    evidencia_url_guardada = ''
    resultado_foto = None
    if evidencia_imagen_url:
        from core.gamificacion_modo import get_modo_gamificacion
        from core.models import ProgresoEstudiante
        from core.reto_evidencia import (
            descargar_media_twilio,
            evaluar_evidencia_foto,
            guardar_evidencia,
        )
        from core.tutor_ia_modulo import cargar_modulos_reto

        progreso_foto = ProgresoEstudiante.objects.filter(id=progreso_id).first()
        evidencia_bytes, evidencia_type = descargar_media_twilio(evidencia_imagen_url)
        evidencia_type = evidencia_type or evidencia_imagen_type
        if evidencia_bytes:
            evidencia_url_guardada = guardar_evidencia(
                evidencia_bytes,
                evidencia_type,
                estudiante_id=estudiante.id,
                curso_id=(progreso_foto.curso_id if progreso_foto else None),
            )
            if _mensaje_indica_listo(msg_body):
                # El webhook convierte media sin texto en "listo"; aquí es una foto.
                msg_body = ''
            resultado_foto = evaluar_evidencia_foto(
                evidencia_bytes,
                evidencia_type,
                reto_original=reto_texto,
                modulos_cubiertos=cargar_modulos_reto(
                    modulos_reto_ids,
                    progreso_foto.curso_id if progreso_foto else None,
                ),
                curso=(progreso_foto.curso if progreso_foto else None),
                estudiante_nombre=estudiante.nombre or 'Estudiante',
                texto_acompanante=msg_body,
                modo_gamificacion=get_modo_gamificacion(
                    getattr(estudiante, 'cliente', None)
                ),
            )
        logger.info(
            "[reto] evidencia foto estudiante=%s bytes=%s guardada=%s evaluada=%s",
            estudiante.id,
            len(evidencia_bytes or b''),
            bool(evidencia_url_guardada),
            resultado_foto is not None,
        )

    msg_lower = msg_body.strip().lower()
    if msg_lower in ['ayuda', 'soporte', 'ticket']:
        from core.security_handler import procesar_solicitud_soporte
        texto_respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'reto_ayuda')
    elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
        # Audio no pudo ser transcrito — pedir reintento sin evaluar
        print(f"🎤 Audio no transcrito en reto — pidiendo reintento")
        texto_respuesta = (
            "No pude escuchar tu audio. Por favor intenta de nuevo "
            "o escríbeme tu respuesta al reto.\n\n"
            "_Escriba, envíe un audio o mande la foto de su evidencia._"
        )
    elif evidencia_bytes and resultado_foto is None:
        # Foto recibida pero sin visión disponible: no castigar con 1/10.
        from core.reto_evidencia import mensaje_evidencia_no_evaluable

        texto_respuesta = mensaje_evidencia_no_evaluable()
    elif _mensaje_indica_listo(msg_body):
        # *listo* no es respuesta al reto (antes se "evaluaba" o se saltaba el avance).
        texto_respuesta = (
            "Para el reto necesito su respuesta en texto, audio o la foto "
            "de su evidencia. Cuando la envíe, la facilitadora la revisa.\n\n"
            "_Escriba, envíe un audio o mande la foto de su evidencia._"
        )
    else:
        from core.models import ProgresoEstudiante
        from core.tutor_ia_modulo import cargar_modulos_reto, evaluar_reto_facilitador
        progreso = (
            ProgresoEstudiante.objects.filter(id=progreso_id).first()
            if progreso_id
            else None
        )
        modulos_reto = cargar_modulos_reto(
            modulos_reto_ids, progreso.curso_id if progreso else None
        )

        from core.gamificacion_modo import get_modo_gamificacion, construir_mensaje_evaluacion_reto

        _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
        modo_gami = get_modo_gamificacion(_cliente)
        if resultado_foto is not None:
            puntaje, feedback = resultado_foto
        else:
            from core.sandbox_canal import poner_reaccion_espera

            poner_reaccion_espera(telefono_limpio, msg_sid)
            puntaje, feedback = evaluar_reto_facilitador(
                modulos_reto, msg_body, reto_texto,
                estudiante_nombre=estudiante.nombre or "Estudiante",
                curso_nombre=(progreso.curso.nombre if progreso else None),
                modo_gamificacion=modo_gami,
            )

        _curso_reto = progreso.curso if progreso else None
        try:
            from core.facilitador_perfil import resolver_perfil_facilitador
            from core.telemetria import registrar_reto_respondido

            registrar_reto_respondido(
                estudiante,
                curso=_curso_reto,
                modulo=(modulos_reto[-1] if modulos_reto else None),
                puntaje=puntaje,
                feedback=feedback,
                tipo_respuesta=('foto' if resultado_foto is not None else 'texto'),
                evidencia_url=evidencia_url_guardada,
                reto_texto=reto_texto,
                respuesta_texto=msg_body,
                perfil_facilitador=resolver_perfil_facilitador(_curso_reto),
            )
        except Exception:
            logger.debug('[reto] telemetría reto_respondido omitida', exc_info=True)

        from core.facilitador_perfil import nombre_display_facilitador

        nombre_tutor = nombre_display_facilitador(
            progreso.curso if progreso is not None else _curso_reto
        )

        msg_eval = construir_mensaje_evaluacion_reto(
            estudiante, progreso, puntaje, feedback, nombre_tutor,
        )

        es_final = ctx.get('es_final', False)

        if es_final and progreso:
            pregunta_abierta = None
            pregunta_abierta_ctx_id = ctx.get('pregunta_abierta_final_id')
            if pregunta_abierta_ctx_id:
                from core.models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal
                pregunta_ctx = PreguntaAbiertaFinalCurso.objects.filter(
                    id=pregunta_abierta_ctx_id,
                    curso=progreso.curso,
                    activa=True,
                ).first()
                if pregunta_ctx:
                    ya_respondio_ctx = RespuestaAbiertaFinal.objects.filter(
                        pregunta=pregunta_ctx,
                        estudiante=estudiante,
                    ).exists()
                    if not ya_respondio_ctx:
                        pregunta_abierta = pregunta_ctx

            if not pregunta_abierta:
                pregunta_abierta = _pregunta_abierta_final_pendiente(estudiante, progreso)

            if pregunta_abierta:
                logger.info(
                    "🧭 Pregunta abierta final seleccionada post-reto | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                    estudiante.id,
                    progreso.curso.id,
                    pregunta_abierta.id,
                    getattr(pregunta_abierta, 'orden', None),
                    (pregunta_abierta.pregunta or '')[:180],
                )
                estudiante.contexto_temporal = {
                    'tipo': 'pregunta_abierta_final',
                    'curso_id': progreso.curso.id,
                    'progreso_id': progreso.id,
                    'pregunta_abierta_final_id': pregunta_abierta.id,
                }
                estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                texto_respuesta = (
                    f"{msg_eval}\n\n"
                    "📝 *Antes del cierre final*, responde esta pregunta abierta:\n\n"
                    f"{pregunta_abierta.pregunta}\n\n"
                    "✍️ Tu facilitadora revisará y calificará tu respuesta."
                )
            else:
                logger.info(
                    "⚠️ Post-reto final sin pregunta abierta final | estudiante_id=%s | curso_id=%s | ctx_pregunta_id=%s",
                    estudiante.id,
                    progreso.curso.id,
                    pregunta_abierta_ctx_id,
                )
                # v1.9.8h: Final reto — issue certificate
                estudiante.estado_onboarding = 'curso_finalizado'
                estudiante.contexto_temporal = None
                estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])

                msg_cert_img = ""
                try:
                    from core.certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
                    cert = crear_certificado_automatico(estudiante, progreso.curso)
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
                    logger.error(f"❌ Error certificado post-reto final: {e}", exc_info=True)
                    msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."

                # Radar/empleabilidad pausado: no envía Subachoque.
                radar_msg = _radar_msg_si_aplica(estudiante)

                msg_final = (
                    f"{msg_eval}\n\n"
                    f"🎓 *¡FELICITACIONES!*\n\n"
                    f"Ha completado el curso: *{progreso.curso.nombre}*"
                )
                partes_finales = [msg_final]
                if radar_msg:
                    partes_finales.append(radar_msg)
                partes_finales.append(msg_cert_img)
                texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes_finales)
        else:
            _prev_ctx = estudiante.contexto_temporal or {}
            from core.helpers_examenes import contexto_temporal_tras_cerrar_agente
            from core.drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

            _base_ctx = contexto_temporal_tras_cerrar_agente(progreso, _prev_ctx) or {}
            estudiante.estado_onboarding = 'completado'
            # Tras Darío + facilitadora: el drip/calendario aplica igual que sin agentes.
            # No adelantar modulo_actual hasta que desbloquee el siguiente módulo.
            if progreso:
                modulo_cerrado = progreso.modulo_actual
                from core.modulo_publicacion import (
                    mensaje_bloqueo_sin_siguiente_publicado,
                    siguiente_modulo_publicado_wa,
                )

                _blk_pub_reto = mensaje_bloqueo_sin_siguiente_publicado(
                    estudiante, progreso, modulo_cerrado
                )
                _blk_tras_reto = mensaje_bloqueo_avance_siguiente_modulo(
                    estudiante, progreso, modulo_cerrado
                )
                if _blk_pub_reto:
                    estudiante.contexto_temporal = _base_ctx
                    estudiante.save(
                        update_fields=['contexto_temporal', 'estado_onboarding']
                    )
                    texto_respuesta = f"{msg_eval}\n\n{_blk_pub_reto}"
                elif _blk_tras_reto:
                    estudiante.contexto_temporal = _base_ctx
                    estudiante.save(
                        update_fields=['contexto_temporal', 'estado_onboarding']
                    )
                    texto_respuesta = f"{msg_eval}\n\n{_blk_tras_reto}"
                else:
                    siguiente = siguiente_modulo_publicado_wa(
                        progreso.curso, progreso.modulo_actual
                    )
                    if siguiente:
                        progreso.modulo_actual = siguiente
                        from core.module_steps import reset_progreso_pasos_modulo
                        reset_progreso_pasos_modulo(progreso, save=False)
                        progreso.save(
                            update_fields=[
                                'modulo_actual',
                                'paso_actual_modulo',
                                'esperando_respuesta_evaluacion_paso',
                                'paso_evaluacion_paso_id',
                            ]
                        )
                        _base_ctx['post_reto_entregar_modulo_id'] = siguiente.id
                    estudiante.contexto_temporal = _base_ctx
                    estudiante.save(
                        update_fields=['contexto_temporal', 'estado_onboarding']
                    )
                    texto_respuesta = (
                        f"{msg_eval}\n\n"
                        "Pulse continuar, para seguir aprendiendo.\n\n"
                        + _MARCADOR_CONTINUEMOS
                    )
            else:
                estudiante.contexto_temporal = _base_ctx
                estudiante.save(
                    update_fields=['contexto_temporal', 'estado_onboarding']
                )
                texto_respuesta = (
                    f"{msg_eval}\n\n"
                    "Pulse continuar, para seguir aprendiendo.\n\n"
                    + _MARCADOR_CONTINUEMOS
                )
        print(f"✅ Facilitadora reto evaluado | modo={modo_gami} | valor={puntaje}", flush=True)
    return Respuesta(texto=texto_respuesta)
