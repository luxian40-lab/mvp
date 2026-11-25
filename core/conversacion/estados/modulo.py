"""Estado esperando_respuesta_modulo. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from django.utils import timezone

from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.avance_whatsapp import TEXTO_NO_ENTENDI as _TEXTO_NO_ENTENDI
from core.conversacion.claves_contexto import contexto_limpio
from core.conversacion.contexto import Contexto, Respuesta
from core.conversacion.multimsg import partes_multimsg
from core.intent_detector import mensaje_indica_listo as _mensaje_indica_listo
from core.models import ModuloCompletado
from core.response_templates import parte_mensaje_con_media
from core.views.empleabilidad import _radar_msg_si_aplica
from core.views.ventana_drip import _pregunta_abierta_final_pendiente

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    from core.pregunta_handler import (
        examen_modulo_sin_pregunta_pendiente,
        recuperar_examen_modulo_vacio,
    )

    # Mini-examen fantasma (rollback/recuperación sin pregunta):
    # *listo* debe entregar la lección, no el default «No entendí».
    if examen_modulo_sin_pregunta_pendiente(estudiante):
        logger.warning(
            'examen modulo vacio | estudiante_id=%s ctx_keys=%s',
            estudiante.id,
            sorted((estudiante.contexto_temporal or {}).keys()),
        )
        recuperar_examen_modulo_vacio(estudiante)
        estudiante.refresh_from_db()
        if _mensaje_indica_listo(msg_body):
            from core.response_templates import get_response_for_intent

            texto_respuesta = get_response_for_intent(
                'continuar_leccion',
                estudiante.nombre,
                estudiante_id=estudiante.id,
                mensaje_original=msg_body,
            )
        else:
            texto_respuesta = (
                "No hay una pregunta pendiente. "
                "Si quiere avanzar, Pulse continuar, para seguir aprendiendo.\n\n" + _MARCADOR_CONTINUEMOS
            )
    elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
        texto_respuesta = (
            "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
            "o escríbeme tu respuesta."
        )
    elif msg_body.strip().lower() in ['menu', 'menú']:
        estudiante.estado_onboarding = 'completado'
        estudiante.save()
        from core.conversacion.flujo_whatsapp_b2b import respuesta_tras_keyword_menu
        texto_respuesta = respuesta_tras_keyword_menu(
            estudiante, estudiante.nombre, msg_body
        )
    else:
        # Validar respuesta a pregunta de módulo
        from core.pregunta_handler import validar_respuesta, procesar_respuesta_abierta_ia
        logger.info(f"📝 Validando respuesta a pregunta de módulo")

        # Verificar si la pregunta es abierta (IA) o de opciones
        ctx = estudiante.contexto_temporal or {}
        es_pregunta_ia = ctx.get('tipo') == 'pregunta_tutor_ia'

        # Fallback: verificar ultima_pregunta_data si contexto no tiene tipo IA
        if not es_pregunta_ia:
            pregunta_data = None
            if hasattr(estudiante, 'ultima_pregunta_data') and estudiante.ultima_pregunta_data:
                import ast
                try:
                    pregunta_data = ast.literal_eval(estudiante.ultima_pregunta_data)
                except Exception:
                    pregunta_data = None
            if pregunta_data and (not pregunta_data.get('opciones')):
                es_pregunta_ia = True

        if es_pregunta_ia:
            # Pregunta IA abierta — evaluar con IA
            es_correcta, mensaje_respuesta = procesar_respuesta_abierta_ia(estudiante, msg_body)
            modulo_completado = None
        else:
            es_correcta, mensaje_respuesta, modulo_completado = validar_respuesta(estudiante, msg_body)

        # Obtener progreso para avanzar al siguiente módulo
        if modulo_completado or es_pregunta_ia:
            from core.curso.helpers_examenes import puede_avanzar_modulo, es_modulo_checkpoint_reto_ia

            if modulo_completado:
                progreso = modulo_completado.progreso
                modulo_actual = modulo_completado.modulo
            else:
                # Para preguntas IA abierta, obtener progreso desde contexto
                from core.models import ProgresoEstudiante, Modulo
                modulo_id = ctx.get('modulo_id')
                progreso_id = ctx.get('progreso_id')
                try:
                    modulo_actual = Modulo.objects.get(id=modulo_id) if modulo_id else None
                    progreso = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
                except Exception:
                    modulo_actual = None
                    progreso = None

                if progreso and modulo_actual:
                    # Crear ModuloCompletado para la pregunta IA abierta
                    modulo_abierto, created_abierto = ModuloCompletado.objects.get_or_create(
                        progreso=progreso,
                        modulo=modulo_actual
                    )
                    if created_abierto:
                        progreso.fecha_ultimo_avance = timezone.now()
                        progreso.save(update_fields=['fecha_ultimo_avance'])

            _skip_avance = False
            if not (progreso and modulo_actual):
                texto_respuesta = mensaje_respuesta
                _skip_avance = True

            if not _skip_avance:
                # VERIFICAR EXAMEN OBLIGATORIO ANTES DE AVANZAR
                puede_avanzar, mensaje_examen, detalles = puede_avanzar_modulo(estudiante, modulo_actual)

                if not puede_avanzar:
                    # NO puede avanzar - examen obligatorio no aprobado
                    mensaje_respuesta += f"""


🔒 *Examen Obligatorio*

{mensaje_examen}

Para continuar al siguiente módulo debes aprobar el examen de este módulo.

Escribe *"examen"* cuando estés listo para intentarlo."""

                    texto_respuesta = mensaje_respuesta
                    # Fall through to Twilio API send

                else:
                    _salida = _preparar_avance_modulo(texto_respuesta, progreso, modulo_actual, estudiante, mensaje_respuesta)
                    if not isinstance(_salida, tuple):
                        return _salida
                    texto_respuesta, siguiente_modulo, activar_checkpoint_facilitador, total_modulos, usar_agentes_ia_curso, decision_cp, es_modulo_reto, drip_bloqueado = _salida

                    if siguiente_modulo:
                        texto_respuesta = _texto_siguiente_modulo(modulo_actual, logger, progreso, total_modulos, usar_agentes_ia_curso, decision_cp, es_modulo_reto, estudiante, siguiente_modulo, mensaje_respuesta, activar_checkpoint_facilitador, partes_multimsg, parte_mensaje_con_media)

                    elif not drip_bloqueado:
                        # Completó todos los módulos
                        progreso.completado = True
                        progreso.fecha_completado = timezone.now()
                        progreso.save()

                        # === v1.9.8h: RETO FINAL en lugar de pregunta de recuperación ===
                        _skip_cert = False
                        pregunta_abierta = _pregunta_abierta_final_pendiente(estudiante, progreso)
                        usar_gamificacion_final = bool(
                            progreso.curso.usar_gamificacion or
                            (estudiante.cliente.usar_gamificacion if getattr(estudiante, 'cliente', None) else False)
                        )
                        usar_agentes_ia_final = bool(getattr(progreso.curso, 'usar_agentes_ia', True))
                        # Reto final solo si el curso usa gamificación Y agentes IA.
                        activar_reto_final = usar_gamificacion_final and usar_agentes_ia_final

                        if activar_reto_final:
                            try:
                                nombre_tutor_final = 'Formador'
                                nombre_asist_final = 'Compañero'
                                modulos_all = list(progreso.curso.modulos.filter(numero__gte=4).order_by('numero'))
                                if not modulos_all:
                                    modulos_all = list(progreso.curso.modulos.all().order_by('numero'))
                                modulos_final_range = "los módulos finales del curso"
                                if len(modulos_all) >= 2:
                                    modulos_final_range = f"los módulos {modulos_all[0].numero} a {modulos_all[-1].numero}"

                                _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                                estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
                                    'tipo': 'asistente_dario',
                                    'curso_activo_id': progreso.curso_id,
                                    'curso_id': progreso.curso.id,
                                    'modulo_id': modulo_actual.id,
                                    'progreso_id': progreso.id,
                                    'modulos_reto_ids': [m.id for m in modulos_all],
                                    'preguntas_hechas': 0,
                                    'es_reto_final': True,
                                    '_ts_leccion': _prev_ts,
                                })
                                if pregunta_abierta:
                                    estudiante.contexto_temporal['pregunta_abierta_final_id'] = pregunta_abierta.id
                                estudiante.estado_onboarding = 'esperando_respuesta_asistente'
                                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

                                from core.agentes_whatsapp import mensaje_con_titular_agente

                                texto_respuesta = (
                                    f"{mensaje_respuesta}\n\n"
                                    f"🎉 *¡Completaste todos los módulos del curso!*\n\n"
                                    + mensaje_con_titular_agente(
                                        nombre_asist_final,
                                        (
                                            f"Antes de tu certificado, {nombre_tutor_final} te planteará un reto final sobre {modulos_final_range}.\n\n"
                                            "¿Tienes dudas antes del reto?\n"
                                            "Ejemplos:\n"
                                            "• ¿Cómo diferencio un daño leve de uno económico?\n"
                                            "• ¿Qué paso práctico recomienda para validar en campo?\n"
                                            "• ¿Qué indicador debo monitorear cada semana?\n\n"
                                            "Envíame tu pregunta (texto o audio).\n"
                                            "Si no tiene dudas, pulse continuar, para seguir aprendiendo.\n\n"
                                            "[SEND_BUTTON:continuemos]"
                                        ),
                                    )
                                )
                                logger.info(
                                    f"🎯 Reto final activado | estudiante_id={estudiante.id} | curso_id={progreso.curso.id} | "
                                    f"curso_usar_gamificacion={bool(progreso.curso.usar_gamificacion)} | "
                                    f"cliente_usar_gamificacion={bool(estudiante.cliente.usar_gamificacion) if getattr(estudiante, 'cliente', None) else False} | "
                                    f"pregunta_abierta_id={getattr(pregunta_abierta, 'id', None)}"
                                )
                                _skip_cert = True
                            except Exception as e:
                                logger.warning(f"⚠️ Reto final exam: {e}")

                        if not _skip_cert:
                            if pregunta_abierta:
                                estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
                                    'tipo': 'pregunta_abierta_final',
                                    'curso_id': progreso.curso.id,
                                    'progreso_id': progreso.id,
                                    'pregunta_abierta_final_id': pregunta_abierta.id,
                                })
                                estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
                                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                                texto_respuesta = (
                                    f"{mensaje_respuesta}\n\n"
                                    "📝 *Antes del cierre final*, responde esta pregunta abierta:\n\n"
                                    f"{pregunta_abierta.pregunta}\n\n"
                                    "✍️ Tu facilitadora revisará y calificará tu respuesta."
                                )
                            else:
                                from core.conversacion.estados.reto import pregunta_si_falta

                                pregunta_nota = pregunta_si_falta(estudiante, progreso.curso, progreso)
                                if pregunta_nota:
                                    texto_respuesta = f'{mensaje_respuesta}\n\n{pregunta_nota}'
                                else:
                                    texto_respuesta = _texto_certificado_modulo(
                                        estudiante, progreso, mensaje_respuesta,
                                    )

        # El default «No entendí» se asigna antes de esta rama.
        # Opción inválida / error de contexto deben ganar.
        if not texto_respuesta or texto_respuesta == _TEXTO_NO_ENTENDI:
            texto_respuesta = mensaje_respuesta
        logger.info(f"✅ Respuesta validada: {'Correcta' if es_correcta else 'Incorrecta'}")
    return Respuesta(texto=texto_respuesta)


def _texto_certificado_modulo(estudiante, progreso, mensaje_respuesta) -> str:
    estudiante.estado_onboarding = 'curso_finalizado'
    estudiante.save(update_fields=['estado_onboarding'])

    msg_final = (
        f"{mensaje_respuesta}\n\n"
        f"🎓 *¡FELICITACIONES!*\n\n"
        f"Ha completado el curso: *{progreso.curso.nombre}*\n\n"
        f"🏆 Su certificado se está generando..."
    )
    msg_cert_img = ""
    try:
        from core.certificados.certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
        logger.info(f"🎓 Iniciando generación de certificado para {estudiante.nombre} - {progreso.curso.nombre}")
        cert = crear_certificado_automatico(estudiante, progreso.curso)
        logger.info(f"🎓 Certificado resultado: cert={cert}, imagen={cert.archivo_imagen if cert else 'N/A'}, pdf={cert.archivo_pdf if cert else 'N/A'}")

        if cert and cert.archivo_imagen:
            cert_url = obtener_url_certificado_twilio(cert)
            if cert_url:
                msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                logger.info(f"✅ Certificado URL para Twilio: {cert_url}")
            else:
                s3_key = str(cert.archivo_imagen.name)
                cert_url = f"https://eki-produccion.s3.us-east-2.amazonaws.com/{s3_key}"
                msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                logger.info(f"✅ Certificado URL fallback: {cert_url}")
        elif cert and cert.archivo_pdf:
            cert_url = cert.archivo_pdf.url
            msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert_url}"
            logger.info(f"📄 Certificado PDF URL: {cert_url}")
        elif cert:
            logger.warning(f"⚠️ Cert creado sin archivo, forzando regeneración...")
            from core.certificados.certificado_service import generar_y_guardar_certificado
            generar_y_guardar_certificado(cert, force=True)
            cert.refresh_from_db()
            if cert.archivo_imagen:
                cert_url = obtener_url_certificado_twilio(cert)
                if cert_url:
                    msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                    logger.info(f"✅ Certificado PRESIGNED URL (retry): {cert_url[:100]}...")
                else:
                    msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
            else:
                msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
        else:
            msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
            logger.warning(f"❌ crear_certificado_automatico retornó None para {estudiante.nombre}")
    except Exception as e:
        logger.error(f"❌ Error generando certificado: {e}", exc_info=True)
        logger.exception('fallo en %s', __name__)
        msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."

    radar_msg = _radar_msg_si_aplica(estudiante)
    partes = [msg_final]
    if radar_msg:
        partes.append(radar_msg)
    partes.append(msg_cert_img)
    return "[MULTI_MSG]" + "[SEP]".join(partes)
