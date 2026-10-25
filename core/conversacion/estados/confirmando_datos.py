"""Estado CONFIRMANDO_DATOS. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.response_templates import parte_mensaje_con_media

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    telefono_limpio = contexto.telefono_limpio
    msg_lower = msg_body.strip().lower()
    keywords_si = ['sí', 'si', 'todo bien', 'correcto', 'bien', 'ok', 'yes', 'confirmo', 'confirmar']
    keywords_modificar = ['modificar', 'no', 'error', 'mal', 'incorrecto', 'hay un error', 'cambiar']

    if any(k in msg_lower for k in keywords_si):
        estudiante.estado_chat = 'ACTIVO'
        estudiante.estado_onboarding = 'completado'  # Legacy compat
        estudiante.save()

        # Enviar curso directamente (sin menú)
        org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
        try:
            from core.models import ProgresoEstudiante
            from core.response_templates import obtener_video_url
            from core.selector_curso import resolver_curso_post_confirmacion

            curso = resolver_curso_post_confirmacion(estudiante)
            if curso:
                progreso, creado = ProgresoEstudiante.objects.get_or_create(
                    estudiante=estudiante,
                    curso=curso,
                    defaults={'completado': False}
                )
                modulo = progreso.modulo_actual
                if not modulo:
                    modulo = curso.modulos.order_by('numero').first()
                    if modulo:
                        progreso.modulo_actual = modulo
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
                if modulo:
                    from core.inicio_curso import marcar_inicio_entregado
                    marcar_inicio_entregado(estudiante, curso.id)
                    # Get agent names: Cliente > Curso > defaults
                    cliente_obj = estudiante.cliente
                    nombre_tutor = (
                        (cliente_obj.nombre_agente_tutor if cliente_obj and hasattr(cliente_obj, 'nombre_agente_tutor') and cliente_obj.nombre_agente_tutor else '') or
                        curso.nombre_agente_tutor or 'Formador'
                    )
                    nombre_asistente = (
                        (cliente_obj.nombre_agente_asistente if cliente_obj and hasattr(cliente_obj, 'nombre_agente_asistente') and cliente_obj.nombre_agente_asistente else '') or
                        curso.nombre_agente_asistente or 'Compañero'
                    )

                    # Presentación de agentes
                    from core.tutor_ia_modulo import generar_presentacion_agentes
                    msg_tutor, msg_asistente = generar_presentacion_agentes(
                        curso_nombre=curso.nombre,
                        estudiante_nombre=estudiante.nombre or 'Estudiante',
                        nombre_tutor=nombre_tutor,
                        nombre_asistente=nombre_asistente,
                        curso=curso,
                    )

                    # Gamification explanation message
                    msg_gamificacion = ""
                    usar_gamificacion = (cliente_obj.usar_gamificacion if cliente_obj else True)
                    if usar_gamificacion:
                        msg_gamificacion = (
                            "*Nuestra experiencia de formación funciona a través de puntos*\n\n"
                            "A medida que avance en el curso, tendrá retos que evaluar.\n\n"
                            "¡Vamos a aprender y avanzar juntos!"
                        )

                    # --- Mensaje 1: Bienvenida + Gamificación + Agentes (TODO EN UNO) ---
                    partes_intro = [
                        f"*¡Datos confirmados, {estudiante.nombre}!*\n\nBienvenido al programa de *{org_nombre}*"
                    ]
                    partes_intro.append(msg_tutor)
                    partes_intro.append(msg_asistente)
                    if msg_gamificacion:
                        partes_intro.append(msg_gamificacion)
                    partes_intro.append("*Comenzamos con el primer módulo de su curso...*")
                    msg_intro = "\n\n".join(partes_intro)

                    from core.module_steps import (
                        modulo_usa_pasos,
                        pasos_activos_qs,
                        reset_progreso_pasos_modulo,
                        entregar_bloque_secciones_desde_paso,
                        log_y_mensaje_modo_pasos_sin_pasos,
                    )

                    if modulo_usa_pasos(modulo):
                        if not pasos_activos_qs(modulo).exists():
                            _fb_conf = log_y_mensaje_modo_pasos_sin_pasos(
                                modulo, 'confirmando_datos_primer_modulo'
                            )
                            texto_respuesta = '[MULTI_MSG]' + msg_intro + '[SEP]' + _fb_conf
                        else:
                            reset_progreso_pasos_modulo(progreso, save=True)
                            msg_pasos_conf = entregar_bloque_secciones_desde_paso(
                                progreso, modulo, 1
                            )
                            _inner_conf = msg_pasos_conf[len('[MULTI_MSG]') :]
                            _pieces = [
                                p for p in _inner_conf.split('[SEP]') if p
                            ]
                            texto_respuesta = '[MULTI_MSG]' + msg_intro + '[SEP]' + '[SEP]'.join(_pieces)
                    else:
                        video_url = obtener_video_url(modulo)
                        archivos_multimedia = modulo.archivos_multimedia.filter(activo=True)
                        archivos_msg = ""
                        primera_media_url = None
                        extra_media_urls = []
                        if archivos_multimedia.exists():
                            archivos_msg = ""
                            for idx, archivo in enumerate(archivos_multimedia):
                                icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                url = archivo.get_url_para_envio()
                                if url:
                                    if not primera_media_url:
                                        primera_media_url = url
                                        archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                    else:
                                        extra_media_urls.append((url, archivo.titulo, icono))
                                        archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                else:
                                    archivos_msg += f"\n{icono} {archivo.titulo}"
                        if not archivos_multimedia.exists() and video_url:
                            primera_media_url = video_url

                        # --- Mensaje 2: Contenido del módulo (con multimedia) ---
                        from core.response_templates import dividir_contenido_seguro
                        from core.module_steps import texto_legacy_whatsapp
                        contenido_modulo = texto_legacy_whatsapp(modulo)
                        chunks = dividir_contenido_seguro(contenido_modulo, max_chars=1300)
                        modulo_header = f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                        if chunks:
                            msg_modulo = modulo_header + chunks[0]
                            for chunk in chunks[1:]:
                                if len(msg_modulo) + len(chunk) + 4 < 1400:
                                    msg_modulo += "\n\n" + chunk
                                else:
                                    break
                        else:
                            msg_modulo = modulo_header + (modulo.descripcion or '')
                        # v1.9.8: No mostrar labels de archivos en texto (se envían como mensajes separados)

                        # Orden: intro (con agentes) → módulo TEXTO → video(s) → [DELAY] → "escribe listo"
                        texto_respuesta = "[MULTI_MSG]" + msg_intro + "[SEP]" + msg_modulo
                        # Video principal como mensaje separado después del texto
                        hay_media_conf = False
                        if primera_media_url:
                            texto_respuesta += f"[SEP]{parte_mensaje_con_media(primera_media_url)}"
                            hay_media_conf = True
                        for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
                            cap_extra = None  # el adjunto va solo, sin título
                            texto_respuesta += f"[SEP]{parte_mensaje_con_media(extra_url, cap_extra)}"
                            hay_media_conf = True
                        # "Escribe listo" AL FINAL — solo si hay más módulos
                        hay_mas_modulos = curso.modulos.filter(numero__gt=modulo.numero).exists()
                        if hay_mas_modulos:
                            if hay_media_conf:
                                texto_respuesta += "[SEP][DELAY:5]"
                            from core.avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo
                            texto_respuesta += "[SEP]" + resolver_cta_listo(
                                estudiante, curso, CTX_FIN_ENTREGA_MODULO
                            )
                else:
                    texto_respuesta = f"*¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nEl curso aún no tiene módulos configurados. Le notificaremos cuando estén listos."
            else:
                texto_respuesta = f"*¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nAún no hay cursos disponibles. Le notificaremos cuando estén listos."
        except Exception as e:
            logger.error(f"❌ Error enviando curso directo: {e}")
            import traceback; traceback.print_exc()
            texto_respuesta = f"*¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nSu organización le notificará cuando estén listos los cursos. Escriba *ayuda* si necesita asistencia."

        # MENÚ OCULTO (no eliminado del código):
        # from .whatsapp_service import enviar_menu_principal
        # resultado = enviar_menu_principal(msg_from, estudiante.nombre)
        # if resultado.get('success'):
        #     return
    elif any(k in msg_lower for k in keywords_modificar):
        # Botón "Modificar" presionado → crear ticket de soporte directamente
        from core.models import SolicitudSoporte
        SolicitudSoporte.objects.create(
            estudiante=estudiante,
            mensaje_original=f"Solicitud de corrección de datos desde verificación. Datos actuales: Nombre={estudiante.nombre}, Cédula={estudiante.cedula}, Municipio={estudiante.municipio}",
            keyword_usada='correccion_datos',
            asunto='Corrección de datos desde verificación',
            estado='pendiente'
        )
        texto_respuesta = (
            "📝 *Solicitud de Corrección Recibida*\n\n"
            f"Hola {estudiante.nombre}, hemos creado un ticket de soporte "
            "para la corrección de tus datos.\n\n"
            "📧 *Nuestro equipo te contactará pronto.*"
        )
        estudiante.estado_chat = 'ACTIVO'
        estudiante.estado_onboarding = 'completado'
        estudiante.save()
    else:
        # Re-enviar la plantilla de confirmación (tiene botones Confirmar/Modificar)
        from core.whatsapp_service import enviar_confirmacion_datos
        org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
        resultado_reenvio = enviar_confirmacion_datos(
            msg_from,
            estudiante.nombre,
            f"{estudiante.tipo_documento} {estudiante.cedula}",
            org_nombre,
            edad=estudiante.edad,
            municipio=estudiante.municipio,
        )
        if resultado_reenvio.get('success'):
            return CORTAR  # Template reenviado, no necesita texto
        texto_respuesta = (
            "Por favor revisa tus datos y toca *Confirmar* o *Modificar* en la plantilla."
        )

    try:
        from core.lineas.entrega import enviar_marcado

        enviar_marcado(msg_from, telefono_limpio, texto_respuesta, registro='segmentos')
    except Exception as e:
        logger.error(f"❌ Error enviando confirmación: {e}")
        import traceback; traceback.print_exc()
    return CORTAR  # CORTAR EJECUCIÓN
