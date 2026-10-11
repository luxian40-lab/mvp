# 02f — Webhook Twilio educativo, parte 3 de 3

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

> Parte 3 de 3. Cierre del envío, safety net y `finally`.

### Continuación de `_procesar_twilio_webhook_cuerpo` (cierre y safety net)

```python
                                )

                                total_modulos = total_modulos_publicados_wa(progreso.curso)
                                usar_agentes_ia_curso = bool(
                                    getattr(progreso.curso, 'usar_agentes_ia', True)
                                )
                                decision_cp = evaluar_checkpoint_reto_ia(
                                    modulo_actual,
                                    total_modulos,
                                    usar_agentes_ia_curso,
                                )
                                es_modulo_reto = decision_cp.es_reto
                                try:
                                    from core.eventos_ia import emit_checkpoint_evaluado

                                    emit_checkpoint_evaluado(
                                        decision_cp,
                                        estudiante=estudiante,
                                        curso=progreso.curso,
                                        modulo=modulo_actual,
                                        origen='pregunta_modulo',
                                    )
                                except Exception:
                                    pass

                                drip_bloqueado = False
                                _blk_pub_v = mensaje_bloqueo_sin_siguiente_publicado(
                                    estudiante, progreso, modulo_actual
                                )# core/views/webhook_twilio.py:3001
                                if _blk_pub_v:
                                    # El siguiente módulo en borrador no tapa el checkpoint:
                                    # primero el reto, el bloqueo llega al cerrarlo.
                                    if es_modulo_reto:
                                        _dario_blk = activar_checkpoint_facilitador(
                                            estudiante, progreso, modulo_actual
                                        )
                                        texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(
                                            [mensaje_respuesta, _dario_blk]
                                        )
                                    else:
                                        texto_respuesta = f"{mensaje_respuesta}\n\n{_blk_pub_v}"
                                    drip_bloqueado = True
                                    siguiente_modulo = None
                                else:
                                    siguiente_modulo = siguiente_modulo_publicado_wa(
                                        progreso.curso, modulo_actual
                                    )

                                if siguiente_modulo:
                                    from ..drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

                                    _blk_v = mensaje_bloqueo_avance_siguiente_modulo(
                                        estudiante, progreso, modulo_actual
                                    )
                                    # Igual que en continuar_leccion: el drip no debe tapar el checkpoint IA.
                                    if _blk_v and not es_modulo_reto:
                                        texto_respuesta = f"{mensaje_respuesta}\n\n{_blk_v}"
                                        drip_bloqueado = True
                                        siguiente_modulo = None

                                if siguiente_modulo:
                                    _fcp = getattr(modulo_actual, 'facilitador_checkpoint', None)
                                    logger.info(
                                        '🎯 [checkpoint-pregunta-modulo] curso=%s mod_num=%s total_mod=%s '
                                        'usar_ia=%s facilitador_checkpoint=%s regla=%s -> es_reto=%s | est=%s',
                                        progreso.curso_id,
                                        getattr(modulo_actual, 'numero', None),
                                        total_modulos,
                                        usar_agentes_ia_curso,
                                        _fcp,
                                        decision_cp.regla_aplicada,
                                        es_modulo_reto,
                                        estudiante.id,
                                    )
                                    
                                    if not es_modulo_reto:
                                        # Normal: advance pointer
                                        progreso.modulo_actual = siguiente_modulo
                                        from ..module_steps import reset_progreso_pasos_modulo
                                        reset_progreso_pasos_modulo(progreso, save=False)
                                        progreso.save(
                                            update_fields=[
                                                'modulo_actual',
                                                'paso_actual_modulo',
                                                'esperando_respuesta_evaluacion_paso',
                                                'paso_evaluacion_paso_id',
                                            ]
                                        )
                                    # else: pointer stays — will advance after reto
                                
                                    estudiante.preguntas_ia_restantes = 3
                                    estudiante.save()
                                
                                    porcentaje = progreso.porcentaje_avance()
                                    from ..response_templates import obtener_video_url
                                    video_url = obtener_video_url(siguiente_modulo)
                                
                                    archivos_multimedia = siguiente_modulo.archivos_multimedia.filter(activo=True)
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
                                
                                    msg_completado = mensaje_respuesta

                                    if es_modulo_reto:
                                        dario_msg = activar_checkpoint_facilitador(
                                            estudiante, progreso, modulo_actual
                                        )
                                        texto_respuesta = "[MULTI_MSG]" + "[SEP]".join([msg_completado, dario_msg])
                                    else:
                                        # v1.9.8i: Normal module — exam result + next module (no completado msg)
                                        estudiante.estado_onboarding = 'completado'
                                        estudiante.save()

                                        from ..module_steps import (
                                            entregar_bloque_secciones_desde_paso,
                                            modulo_usa_pasos,
                                            pasos_activos_qs,
                                            texto_legacy_whatsapp,
                                        )
                                        from ..avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo

                                        if modulo_usa_pasos(siguiente_modulo) and pasos_activos_qs(siguiente_modulo).exists():
                                            msg_pasos_n = entregar_bloque_secciones_desde_paso(
                                                progreso, siguiente_modulo, 1
                                            )
                                            inner_n = (
                                                msg_pasos_n[len('[MULTI_MSG]'):]
                                                if (msg_pasos_n or '').startswith('[MULTI_MSG]')
                                                else (msg_pasos_n or '')
                                            )
                                            partes = [msg_completado] + [p for p in inner_n.split('[SEP]') if p]
                                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)
                                        else:
                                            _leg = texto_legacy_whatsapp(siguiente_modulo)
                                            msg_modulo = (
                                                f"📖 *Módulo {siguiente_modulo.numero}: {siguiente_modulo.titulo}*\n\n"
                                                f"{siguiente_modulo.descripcion}\n\n{_leg}"
                                            )
                                            if siguiente_modulo.examen_obligatorio:
                                                msg_modulo += (
                                                    f"\n\n⚠️ *Este módulo tiene examen obligatorio "
                                                    f"({siguiente_modulo.puntaje_minimo_aprobacion}% para aprobar)*"
                                                )
                                            partes = [msg_completado, msg_modulo]
                                            hay_media_exam = False
                                            if primera_media_url:
                                                partes.append(parte_mensaje_con_media(primera_media_url))
                                                hay_media_exam = True
                                            for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
                                                partes.append(parte_mensaje_con_media(extra_url))
                                                hay_media_exam = True
                                            if hay_media_exam:
                                                partes.append("[DELAY:5]")
                                            partes.append(
                                                resolver_cta_listo(
                                                    estudiante, progreso.curso, CTX_FIN_ENTREGA_MODULO
                                                )
                                            )
                                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)

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
                                            nombre_tutor_final = progreso.curso.nombre_agente_tutor or 'Claudia'
                                            nombre_asist_final = progreso.curso.nombre_agente_asistente or 'Darío'
                                            modulos_all = list(progreso.curso.modulos.filter(numero__gte=4).order_by('numero'))
                                            if not modulos_all:
                                                modulos_all = list(progreso.curso.modulos.all().order_by('numero'))
                                            modulos_final_range = "los módulos finales del curso"
                                            if len(modulos_all) >= 2:
                                                modulos_final_range = f"los módulos {modulos_all[0].numero} a {modulos_all[-1].numero}"

                                            _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                                            estudiante.contexto_temporal = {
                                                'tipo': 'asistente_dario',
                                                'curso_activo_id': progreso.curso_id,
                                                'curso_id': progreso.curso.id,
                                                'modulo_id': modulo_actual.id,
                                                'progreso_id': progreso.id,
                                                'modulos_reto_ids': [m.id for m in modulos_all],
                                                'preguntas_hechas': 0,
                                                'es_reto_final': True,
                                                '_ts_leccion': _prev_ts,
                                            }
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
                                                        "Si no tienes dudas, escribe *listo* para pasar con la facilitadora."
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
                                            estudiante.contexto_temporal = {
                                                'tipo': 'pregunta_abierta_final',
                                                'curso_id': progreso.curso.id,
                                                'progreso_id': progreso.id,
                                                'pregunta_abierta_final_id': pregunta_abierta.id,
                                            }
                                            estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
                                            estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                                            texto_respuesta = (
                                                f"{mensaje_respuesta}\n\n"
                                                "📝 *Antes del cierre final*, responde esta pregunta abierta:\n\n"
                                                f"{pregunta_abierta.pregunta}\n\n"
                                                "✍️ Tu facilitadora revisará y calificará tu respuesta."
                                            )
                                        else:
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
                                                from ..certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
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
                                                    from ..certificado_service import generar_y_guardar_certificado
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
                                                import traceback; traceback.print_exc()
                                                msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."

                                            # Radar/empleabilidad pausado: no envía Subachoque.
                                            radar_msg = _radar_msg_si_aplica(estudiante)

                                            partes = [msg_final]
                                            if radar_msg:
                                                partes.append(radar_msg)
                                            partes.append(msg_cert_img)
                                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)
                    
                    # El default «No entendí» se asigna antes de esta rama.
                    # Opción inválida / error de contexto deben ganar.
                    if (
                        not texto_respuesta
                        or texto_respuesta.startswith('No entendí. Si quieres avanzar')
                    ):
                        texto_respuesta = mensaje_respuesta
                    print(f"✅ Respuesta validada: {'Correcta' if es_correcta else 'Incorrecta'}")
            
            # 3.5c PRIORIDAD: Si está seleccionando un curso de la lista
            # (B2B con 2+ cursos también elige por número aquí)
            elif estudiante.estado_onboarding == 'esperando_seleccion_curso':
                msg_sel = msg_body.strip().lower()
                if msg_sel in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    from ..response_templates import get_response_for_intent
                    texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                else:
                    import re as re_curso_sel
                    indice_sel = None
                    match_tomar_sel = re_curso_sel.match(r'^tomar\s*(\d+)$', msg_sel)
                    if match_tomar_sel:
                        indice_sel = int(match_tomar_sel.group(1))
                    elif msg_body.strip().isdigit():
                        indice_sel = int(msg_body.strip())
                    if indice_sel is not None:
                        from ..selector_curso import continuar_curso_seleccionado
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save(update_fields=['estado_onboarding'])
                        texto_respuesta = continuar_curso_seleccionado(estudiante.id, indice_sel, msg_body)
                        print(f"✅ Curso seleccionado: {indice_sel}")
                    else:
                        # Si no es número/tomar ni menú, resetear estado y procesar normalmente
                        estudiante.estado_onboarding = 'completado'
                        estudiante.contexto_temporal = None
                        estudiante.save()
                        from core.eventos_ia import detectar_intent_con_evento
                        from ..response_templates import get_response_for_intent
                        _p0 = estudiante.progresos.order_by('-fecha_inicio').first()
                        intent = detectar_intent_con_evento(
                            msg_body,
                            estudiante=estudiante,
                            curso=_p0.curso if _p0 else None,
                            modulo=_p0.modulo_actual if _p0 else None,
                        )
                        if intent != 'desconocido':
                            texto_respuesta = get_response_for_intent(intent, estudiante.nombre, estudiante_id=estudiante.id, mensaje_original=msg_body)
                        else:
                            texto_respuesta = "No entendí tu selección. Escribe *menú* para ver las opciones."
            
            # 4. Detectar intent y usar templates primero
            else:
                from core.eventos_ia import detectar_intent_con_evento
                from ..response_templates import get_response_for_intent

                _prog = None
                try:
                    _prog = estudiante.progresos.order_by('-fecha_inicio').first()
                except Exception:
                    pass
                intent = detectar_intent_con_evento(
                    msg_body,
                    estudiante=estudiante,
                    curso=_prog.curso if _prog else None,
                    modulo=_prog.modulo_actual if _prog else None,
                )
                print(f"🎯 Intent detectado: {intent}")
            
                # Intent especial: corregir datos → redirigir al flujo de corrección
                if intent == 'corregir_datos':
                    estudiante.estado_chat = 'ESPERANDO_CORRECCION_DATOS'
                    estudiante.save()
                    texto_respuesta = (
                        "📝 *Corrección de Datos*\n\n"
                        "Puedes corregir cualquiera de tus datos.\n\n"
                        "Escribe el campo que deseas cambiar seguido del nuevo valor:\n\n"
                        "1️⃣ *nombre:* Tu nombre completo\n"
                        "2️⃣ *municipio:* Tu municipio\n"
                        "3️⃣ *departamento:* Tu departamento\n"
                        "4️⃣ *documento:* Tipo y número (CC, TI, CE, PP)\n"
                        "5️⃣ *edad:* Tu edad\n"
                        "6️⃣ *genero:* M, F, Otro, NR\n\n"
                        "📝 _Ejemplos:_\n"
                        "_nombre: María García López_\n"
                        "_municipio: Bogotá_\n"
                        "_edad: 35_\n\n"
                        "👉 Escribe *menú* cuando termines"
                    )
                # Si hay un intent conocido, usar template
                elif intent != 'desconocido':
                    texto_respuesta = get_response_for_intent(
                        intent, 
                        estudiante.nombre,
                        estudiante_id=estudiante.id,
                        mensaje_original=msg_body
                    )
                    print(f"✅ Respuesta desde template: {texto_respuesta[:50]}...")
                    if texto_respuesta == LECCION_EN_CURSO:
                        from core.sandbox_canal import descartar_reaccion_espera

                        descartar_reaccion_espera(telefono_limpio)
                        return
                else:
                    # Solo si no hay intent, usar IA para preguntas sobre agricultura
                    # 🛑 ANTI-ABUSO IA: Verificar preguntas restantes
                    print(f"🤖 Usando IA para pregunta sobre agricultura")
                    if estudiante.preguntas_ia_restantes <= 0:
                        # Freno de mano: IA pausada
                        from ..avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo
                        _prog_ia = estudiante.progresos.order_by('-fecha_inicio').first()
                        _curso_ia = _prog_ia.curso if _prog_ia else None
                        texto_respuesta = (
                            "[MULTI_MSG]⚠️ *Has agotado tus preguntas libres a la IA para este modulo.*\n\n"
                            "Para desbloquear mas preguntas, necesitas responder "
                            "la pregunta de evaluacion del modulo actual."
                            "[SEP]"
                            + resolver_cta_listo(estudiante, _curso_ia, CTX_FIN_ENTREGA_MODULO)
                        )
                    else:
                        try:
                            from core.sandbox_canal import poner_reaccion_espera
                            from ..ai_assistant import responder_con_ia

                            poner_reaccion_espera(telefono_limpio, msg_sid)
                            texto_respuesta = responder_con_ia(msg_body, telefono_limpio)
                            # Restar pregunta usada (anti-abuso silencioso)
                            estudiante.preguntas_ia_restantes = max(0, estudiante.preguntas_ia_restantes - 1)
                            estudiante.save()
                            print(f"✅ IA generó respuesta: {texto_respuesta[:50]}...")
                        except Exception as e:
                            print(f"❌ Error IA: {e}, usando respuesta genérica")
                            texto_respuesta = "Disculpa, tengo problemas técnicos. Vuelve a escribir tu mensaje para continuar."
        
        # 3. Enviar respuesta via Twilio
        print(f"📤 ENVIANDO RESPUESTA: '{texto_respuesta[:80]}...' (len={len(texto_respuesta)})", flush=True)
        if (
            'Pregunta abierta final de la Facilitadora' in texto_respuesta
            or 'Siguiente pregunta abierta final' in texto_respuesta
        ):
            logger.info(
                "📨 Respuesta de pregunta abierta final enviada | estudiante_id=%s | preview=%s",
                estudiante.id,
                texto_respuesta[:500],
            )
        # Detectar si hay media_url en la respuesta (marcado con [MEDIA:url])
        # NOTA: Solo extraer [MEDIA:] para mensajes simples (no MULTI_MSG)
        # MULTI_MSG maneja su propio [MEDIA:] por cada parte del split
        media_url_to_send = None
        if not texto_respuesta.startswith('[MULTI_MSG]') and '[MEDIA:' in texto_respuesta:
            import re
            media_match = re.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
            if media_match:
                media_url_to_send = media_match.group(1)
                texto_respuesta = texto_respuesta.replace(media_match.group(0), '').strip()
                print(f"🖼️ Media URL detectada: {media_url_to_send}")
        
        try:
            from twilio.rest import Client
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '[REDACTADO]')
            twilio_number = str(twilio_number).strip()
            print(f"DEBUG TWILIO FROM (views.py): '{twilio_number}'")
            
            if not account_sid or not auth_token:
                print("❌ Credenciales Twilio faltantes")
                return
            
            client = Client(account_sid, auth_token)

            # Usar el teléfono original (con +) para enviar por Twilio
            destino_formateado = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
            destino_formateado = str(destino_formateado).strip()
            
            # Check if response is a standalone template send
            if texto_respuesta.strip().startswith('[SEND_TEMPLATE:'):
                import re
                tmpl_match = re.match(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]', texto_respuesta.strip())
                if tmpl_match:
                    template_sid = tmpl_match.group(1)
                    print(f"📋 Enviando Content Template standalone: {template_sid}")
                    try:
                        from ..whatsapp_service import enviar_template_twilio
                        tel_limpio = msg_from.replace('whatsapp:', '').replace('+', '')
                        enviar_template_twilio(tel_limpio, template_sid)
                        print(f"✅ Template {template_sid} enviado OK")
                    except Exception as tmpl_err:
                        print(f"⚠️ Error enviando template standalone: {tmpl_err}")
                    return
            
            # Check if response is a multi-message (marked with [MULTI_MSG])
            if texto_respuesta.startswith('[MULTI_MSG]'):
                # Extract and send multiple messages
                partes = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                
                for idx, parte in enumerate(partes):
                    if not parte.strip():
                        continue
                    
                    parte_texto = parte.strip()
                    parte_media = None
                    
                    # [DELAY:N] — pausa intencional para que WhatsApp entregue videos antes del texto siguiente
                    import re as re_delay
                    delay_match = re_delay.match(r'^\[DELAY:(\d+)\]$', parte_texto)
                    if delay_match:
                        delay_secs = int(delay_match.group(1))
                        print(f"⏳ Pausa de {delay_secs}s para entrega de videos...")
                        import time
                        time.sleep(delay_secs)
                        continue
                    
                    # Detectar si esta parte es un Content Template de Twilio
                    if parte_texto.startswith('[SEND_TEMPLATE:'):
                        import re
                        tmpl_match = re.match(r'\[SEND_TEMPLATE:(HX[a-f0-9]+)\]', parte_texto)
                        if tmpl_match:
                            template_sid = tmpl_match.group(1)
                            print(f"📋 Enviando Content Template {template_sid} como parte {idx+1}")
                            try:
                                from ..whatsapp_service import enviar_template_twilio
                                tel_limpio = msg_from.replace('whatsapp:', '').replace('+', '')
                                enviar_template_twilio(tel_limpio, template_sid)
                                print(f"✅ Template {template_sid} enviado OK")
                            except Exception as tmpl_err:
                                print(f"⚠️ Error enviando template: {tmpl_err}")
                            import time
                            time.sleep(0.5)
                            continue
                    
                    # Extraer [MEDIA:url] de esta parte
                    if '[MEDIA:' in parte_texto:
                        import re
                        media_match_p = re.search(r'\[MEDIA:(.*?)\]', parte_texto)
                        if media_match_p:
                            parte_media = (media_match_p.group(1) or '').strip()
                            parte_texto = parte_texto.replace(media_match_p.group(0), '').strip()
                            logger.info(
                                '📎 [MEDIA] parte %s url=%s',
                                idx + 1,
                                parte_media[:500] + ('…' if len(parte_media) > 500 else ''),
                            )
                            if parte_media and youtube_hace_solo_enlace_en_texto(parte_media):
                                logger.warning(
                                    '📎 [MEDIA] URL parece página de YouTube (no MP4 directo); '
                                    'Twilio suele necesitar enlace al archivo. parte=%s',
                                    idx + 1,
                                )

                    mensajes_enviados = _enviar_mensaje_twilio_segmentado(
                        client=client,
                        from_number=twilio_number,
                        to_number=destino_formateado,
                        body=parte_texto,
                        media_url=parte_media,
                    )

                    for seg_idx, (mensaje, texto_enviado) in enumerate(mensajes_enviados, start=1):
                        print(f"✅ Mensaje {idx+1}.{seg_idx} enviado via Twilio: {mensaje.sid}")
                        from ..twilio_media import mensaje_log_con_media

                        texto_log = mensaje_log_con_media(
                            texto_enviado or parte_texto,
                            parte_media if seg_idx == 1 else None,
                        )
                        WhatsappLog.objects.create(
                            telefono=telefono_limpio,
                            mensaje=texto_log[:1500],
                            mensaje_id=mensaje.sid,
                            tipo='SENT'
                        )
                        print(f"✅ Guardado SENT")
                    
                    # Small delay between messages to avoid rate limiting
                    import time
                    time.sleep(0.5)
            else:
                # Single message (original behavior)
                mensajes_enviados = _enviar_mensaje_twilio_segmentado(
                    client=client,
                    from_number=twilio_number,
                    to_number=destino_formateado,
                    body=texto_respuesta,
                    media_url=media_url_to_send,
                )

                for seg_idx, (mensaje, texto_enviado) in enumerate(mensajes_enviados, start=1):
                    if len(mensajes_enviados) == 1:
                        print(f"✅ Mensaje enviado via Twilio: {mensaje.sid}")
                    else:
                        print(f"✅ Mensaje segmento {seg_idx}/{len(mensajes_enviados)} enviado via Twilio: {mensaje.sid}")

                    from ..twilio_media import mensaje_log_con_media

                    texto_log = mensaje_log_con_media(
                        texto_enviado or texto_respuesta,
                        media_url_to_send if seg_idx == 1 else None,
                    )
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=texto_log[:1500],
                        mensaje_id=mensaje.sid,
                        tipo='SENT'
                    )
                    print(f"✅ Guardado SENT")
            
        except Exception as e:
            print(f"❌ Error enviando respuesta Twilio: {str(e)}")
            import traceback
            traceback.print_exc()
    
    except Exception as e:
        print(f"❌ Error en _procesar_twilio_webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # ============================================================
        # SAFETY NET: Siempre enviar ALGO al usuario, nunca quedar mudo
        # ============================================================
        try:
            msg_from_fallback = post_data.get('From', '')
            if msg_from_fallback:
                from twilio.rest import Client
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '[REDACTADO]')
                twilio_number = str(twilio_number).strip()
                
                if account_sid and auth_token:
                    client = Client(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from_fallback}' if not msg_from_fallback.startswith('whatsapp:') else msg_from_fallback
                    destino = str(destino).strip()
                    client.messages.create(
                        body="⚠️ Tuvimos un problema técnico momentáneo. Por favor vuelve a escribir tu mensaje para continuar.",
                        from_=twilio_number,
                        to=destino
                    )
                    print(f"✅ Safety net: mensaje de error enviado a {destino}")
        except Exception as fallback_err:
            print(f"❌ Safety net también falló: {fallback_err}")
    finally:
        soltar_turno_entrega_actual()
        cerrar_retencion_turno(_turno_token)
```

**Contrato** de `_procesar_twilio_webhook_cuerpo` (`core/views/webhook_twilio.py:32`; el cuerpo está partido en 02d, 02e y 02f)
- Entradas: `post_data` estilo Twilio (form o dict).
- Salidas: None. El HTTP que llama responde 200 aparte.
- Efectos: si es status callback, solo `_registrar_estado_twilio_callback`. Si el `MessageSid` ya tiene `WhatsappLog` INCOMING, return. Crea INCOMING hacia la línea 143 del fuente. Resuelve onboarding, drip y pasos, y envía con `messages.create`, `_enviar_mensaje_twilio_segmentado`, `enviar_template_twilio` o `enviar_whatsapp_twilio`. El `from` del cierre usa `TWILIO_PHONE_NUMBER` con fallback fijo (redactado). Hay `time.sleep` entre partes. El safety net de esta parte manda un texto genérico si el `except` exterior dispara.
- Excepciones: el `except` exterior imprime traceback y dispara el safety net. Si ese create también falla, el segundo `except` solo imprime. Errores de envío intermedios se capturan y el flujo sigue.

