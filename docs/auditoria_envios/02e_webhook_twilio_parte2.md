# 02e — Webhook Twilio educativo, parte 2 de 3

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

> Parte 2 de 3. Continuación literal de `_procesar_twilio_webhook_cuerpo`.

### Continuación de `_procesar_twilio_webhook_cuerpo`

```python
            if msg_lower in ['2', 'mis puntos', 'puntos', '🏆 mis puntos']:
                from ..whatsapp_service import enviar_gamificacion_visual
                enviar_gamificacion_visual(msg_from, estudiante)
                return
            
            # Detectar "Necesito ayuda" / PQRS / Soporte (todo unificado)
            elif msg_lower in ['3', 'necesito ayuda', 'ayuda', '🙋‍♂️ necesito ayuda', 'pqrs', 'soporte', 'queja', 'reclamo', 'solicitud']:
                from ..security_handler import procesar_solicitud_soporte
                respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'menu_ayuda')
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '[REDACTADO]')
                    client_tw = TwilioClient(account_sid, auth_token)# core/views/webhook_twilio.py:1501
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=respuesta, tipo='SENT')
                except Exception:
                    pass
                return
            
            # Detectar "corregir datos" / "me equivoqué" -> iniciar autocorreccion guiada
            elif msg_lower in ['4', 'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
                               'me equivoqué', 'me equivoque', 'editar datos', 'modificar datos',
                               'datos incorrectos', 'mis datos', 'actualizar datos']:
                from ..correccion_datos import iniciar_flujo_correccion
                texto_respuesta = iniciar_flujo_correccion(estudiante)
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '[REDACTADO]')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
                except Exception as e:
                    logger.error(f"❌ Error enviando corrección datos: {e}")
                return
            
            # Detectar "menú" → enviar directamente al curso asignado (sin lista)
            elif msg_lower in ['menu', 'menú', 'inicio', 'hola']:
                if estudiante.estado_onboarding in estados_agente:
                    logger.info(
                        "menu/inicio/hola durante agente pedagógico (%s) — omitir reenvío de módulo",
                        estudiante.estado_onboarding,
                    )
                else:
                    from ..models import Curso, ProgresoEstudiante
                    from ..response_templates import obtener_video_url
                    org = estudiante.cliente
                    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre') if org else Curso.objects.filter(activo=True).order_by('orden', 'nombre')
                    progreso_existente = ProgresoEstudiante.objects.filter(
                        estudiante=estudiante, completado=False, curso__activo=True
                    ).first()
                    curso = progreso_existente.curso if progreso_existente else cursos.first()
                    if curso:
                        progreso, _ = ProgresoEstudiante.objects.get_or_create(
                            estudiante=estudiante, curso=curso, defaults={'completado': False}
                        )
                        modulo = progreso.modulo_actual
                        if not modulo:
                            modulo = curso.modulos.order_by('numero').first()
                            if modulo:
                                progreso.modulo_actual = modulo
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
                        if modulo:
                            from ..module_steps import (
                                modulo_usa_pasos,
                                mensaje_recordatorio_paso_actual,
                                pasos_activos_qs,
                                log_y_mensaje_modo_pasos_sin_pasos,
                            )
                            if modulo_usa_pasos(modulo):
                                if not pasos_activos_qs(modulo).exists():
                                    texto_respuesta = log_y_mensaje_modo_pasos_sin_pasos(
                                        modulo, 'views_menu_inicio'
                                    )
                                else:
                                    _np_m = pasos_activos_qs(modulo).count()
                                    if (
                                        progreso.paso_actual_modulo > _np_m
                                        and not progreso.esperando_respuesta_evaluacion_paso
                                    ):
                                        texto_respuesta = (
                                            "✅ Ya recibiste todo el material de esta unidad.\n\n"
                                            "Escribe *listo* para registrar tu avance y seguir 👇"
                                        )
                                    else:
                                        _rem_m = mensaje_recordatorio_paso_actual(progreso, modulo)
                                        texto_respuesta = _rem_m or (
                                            f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                                            "Escribe *continuar* o *listo* cuando quieras seguir."
                                        )
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
                                from ..module_steps import texto_legacy_whatsapp
                                msg_texto_menu = (
                                    f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                                    f"{texto_legacy_whatsapp(modulo)}"
                                )
                                partes_menu = [msg_texto_menu]
                                if primera_media_url:
                                    partes_menu.append(parte_mensaje_con_media(primera_media_url))
                                for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
                                    partes_menu.append(parte_mensaje_con_media(extra_url))
                                if len(partes_menu) > 1:
                                    texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes_menu)
                                else:
                                    texto_respuesta = msg_texto_menu
                        else:
                            texto_respuesta = f"📚 Tu curso *{curso.nombre}* aún no tiene módulos configurados."
                    else:
                        texto_respuesta = (
                            "📚 Aún no tienes un curso asignado. "
                            "Tu coordinador te lo asignará pronto.\n\n"
                            "Si acabas de reportar un problema, cuando quieras retomar escribe *listo* o *menú*."
                        )
                    try:
                        from twilio.rest import Client as TwilioClient
                        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                        twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '[REDACTADO]')
                        client_tw = TwilioClient(account_sid, auth_token)
                        destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                        twilio_from = str(twilio_number).strip()

                        if texto_respuesta.startswith('[MULTI_MSG]'):
                            import re as re_menu_m
                            partes_mm = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                            for parte_mm in partes_mm:
                                if not parte_mm.strip():
                                    continue
                                parte_txt = parte_mm.strip()
                                delay_mm = re_menu_m.match(r'^\[DELAY:(\d+)\]$', parte_txt)
                                if delay_mm:
                                    import time
                                    time.sleep(int(delay_mm.group(1)))
                                    continue
                                media_mm = re_menu_m.search(r'\[MEDIA:(.*?)\]', parte_txt)
                                parte_media_mm = None
                                if media_mm:
                                    parte_media_mm = media_mm.group(1).strip()
                                    parte_txt = parte_txt.replace(media_mm.group(0), '').strip()
                                cuerpo_mm = parte_txt.strip() if parte_txt else ''
                                enviados_mm = _enviar_mensaje_twilio_segmentado(
                                    client=client_tw,
                                    from_number=twilio_from,
                                    to_number=str(destino).strip(),
                                    body=cuerpo_mm if cuerpo_mm else ' ',
                                    media_url=parte_media_mm,
                                )
                                import time
                                time.sleep(0.5)
                                from ..twilio_media import mensaje_log_con_media
                                for seg_i, (msg_mm, texto_env) in enumerate(enviados_mm, start=1):
                                    WhatsappLog.objects.create(
                                        telefono=telefono_limpio,
                                        mensaje=mensaje_log_con_media(
                                            texto_env or cuerpo_mm or parte_txt,
                                            parte_media_mm if seg_i == 1 else None,
                                        )[:1500],
                                        mensaje_id=getattr(msg_mm, 'sid', None),
                                        tipo='SENT',
                                    )
                        else:
                            media_url_menu = None
                            import re as re_menu
                            media_m = re_menu.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
                            if media_m:
                                media_url_menu = media_m.group(1).strip()
                                texto_respuesta = texto_respuesta.replace(media_m.group(0), '').strip()
                            enviados_menu = _enviar_mensaje_twilio_segmentado(
                                client=client_tw,
                                from_number=twilio_from,
                                to_number=str(destino).strip(),
                                body=texto_respuesta,
                                media_url=media_url_menu,
                            )
                            from ..twilio_media import mensaje_log_con_media
                            for seg_i, (msg_menu, texto_env) in enumerate(enviados_menu, start=1):
                                WhatsappLog.objects.create(
                                    telefono=telefono_limpio,
                                    mensaje=mensaje_log_con_media(
                                        texto_env or texto_respuesta,
                                        media_url_menu if seg_i == 1 else None,
                                    )[:1500],
                                    mensaje_id=getattr(msg_menu, 'sid', None),
                                    tipo='SENT',
                                )
                    except Exception as e:
                        logger.error(f"❌ Error enviando curso: {e}")
                    return
        
        # ============================================================
        # PQRS: seguimiento de ticket abierto (cede a pedagogía / agentes)
        # ============================================================
        pqrs_atendido = False
        respuesta_pqrs = None
        try:
            from ..pqrs_agent import (
                intentar_procesar_seguimiento_pqrs_whatsapp,
                pedagogia_tiene_prioridad,
            )

            if not pedagogia_tiene_prioridad(estudiante):
                respuesta_pqrs = intentar_procesar_seguimiento_pqrs_whatsapp(
                    estudiante, msg_body,
                )
                if respuesta_pqrs:
                    pqrs_atendido = True
                    logger.info(
                        '🆘 PQRS seguimiento — respuesta automática estudiante_id=%s',
                        estudiante.id,
                    )
        except Exception as e:
            logger.exception('PQRS seguimiento omitido: %s', e)

        # ============================================================
        # FLUJO EXISTENTE: Procesamiento normal (IA tutors, módulos, etc.)
        # ============================================================
        
        # 3. 🛡️ PRIORIDAD 1: Verificar seguridad (Habeas Data) - Legacy
        from ..security_handler import verificar_seguridad_completa
        if pqrs_atendido:
            bloqueado = True
            respuesta_seguridad = respuesta_pqrs
        else:
            bloqueado, respuesta_seguridad, estudiante = verificar_seguridad_completa(
                estudiante,
                msg_body,
                telefono_limpio,
                numero_destino=msg_to,
            )
        print(f"🛡️ Seguridad: bloqueado={bloqueado} | estudiante={estudiante} | estado={getattr(estudiante, 'estado_onboarding', 'N/A')}", flush=True)
        
        # Default safety - will be overwritten by any branch below
        texto_respuesta = "No entendí. Si quieres avanzar de módulo escribe *listo*. Si necesitas ayuda, escribe *ayuda*."
        
        if bloqueado:
            print(f"🛡️ Bloqueado por seguridad/habeas data", flush=True)
            texto_respuesta = respuesta_seguridad
        else:
            # Si el contexto de agente quedó y el estado se desincronizó, no caer
            # en continuar_leccion (saltaría Darío / facilitadora).
            try:
                _ctx_agente_sync = estudiante.contexto_temporal or {}
                _tipo_ctx = _ctx_agente_sync.get('tipo')
                if _tipo_ctx == 'asistente_dario' and estudiante.estado_onboarding != 'esperando_respuesta_asistente':
                    _ob_prev = estudiante.estado_onboarding
                    estudiante.estado_onboarding = 'esperando_respuesta_asistente'
                    estudiante.save(update_fields=['estado_onboarding'])
                    logger.warning(
                        "🔄 Darío: estado resincronizado %s → esperando_respuesta_asistente "
                        "(ctx=asistente_dario) estudiante_id=%s",
                        _ob_prev,
                        estudiante.id,
                    )
                elif _tipo_ctx == 'reto_facilitador' and estudiante.estado_onboarding != 'esperando_respuesta_reto':
                    _ob_prev = estudiante.estado_onboarding
                    estudiante.estado_onboarding = 'esperando_respuesta_reto'
                    estudiante.save(update_fields=['estado_onboarding'])
                    logger.warning(
                        "🔄 Facilitadora: estado resincronizado %s → esperando_respuesta_reto "
                        "(ctx=reto_facilitador) estudiante_id=%s",
                        _ob_prev,
                        estudiante.id,
                    )
            except Exception as e:
                logger.warning("⚠️ Sync agente pedagógico omitido: %s", e)

            from core.empleabilidad_pausa import empleabilidad_en_pausa as _emp_pausa_codigo

            if (
                estudiante.estado_onboarding == 'esperando_codigo_empleabilidad'
                and not _emp_pausa_codigo()
            ):
                from ..models import AliadoEmpleabilidad, MisionEmpleabilidad
                from ..gamificacion import PerfilGamificacion, Badge, BadgeEstudiante
                ctx_emp = estudiante.contexto_temporal or {}
                aliado_id = ctx_emp.get('aliado_empleabilidad_objetivo_id')
                mision_id = ctx_emp.get('mision_empleabilidad_id')
                aliado = None
                if aliado_id:
                    aliado = AliadoEmpleabilidad.objects.filter(id=aliado_id, vacantes_activas=True).first()
                mision = None
                if mision_id:
                    mision = MisionEmpleabilidad.objects.filter(id=mision_id, estudiante=estudiante).first()

                codigo_ingresado = msg_body.strip().lower()
                codigo_esperado = str(aliado.codigo_secreto).strip().lower() if aliado else ''
                if aliado and codigo_ingresado == codigo_esperado:
                    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                    puntos_cfg = int(getattr(estudiante.cliente, 'empleabilidad_puntos_validacion', 30) or 30)
                    perfil.agregar_puntos(puntos_cfg, f"Radar Empleabilidad: {aliado.nombre_empresa}")
                    badge = Badge.objects.filter(tipo='ESPECIAL', activo=True, nombre__icontains='emple').first()
                    if badge:
                        BadgeEstudiante.objects.get_or_create(estudiante=estudiante, badge=badge)

                    if mision and mision.estado != 'completada':
                        mision.estado = 'completada'
                        mision.codigo_validado = True
                        mision.puntos_otorgados = puntos_cfg
                        mision.fecha_completada = timezone.now()
                        mision.save(update_fields=['estado', 'codigo_validado', 'puntos_otorgados', 'fecha_completada'])

                    try:
                        from ..tasks import enviar_email_org_admin_async

                        asunto = f"Match empleabilidad: {estudiante.nombre} - {aliado.nombre_empresa}"
                        mensaje_html = (
                            f"<p>El estudiante <strong>{estudiante.nombre}</strong> "
                            f"(tel: {estudiante.telefono}) validó el código secreto de "
                            f"<strong>{aliado.nombre_empresa}</strong>.</p>"
                            f"<p>Iniciar contacto para proceso de contratación.</p>"
                        )
                        enviar_email_org_admin_async.delay(estudiante.id, asunto, mensaje_html)
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo encolar notificación de empleabilidad: {e}")

                    ctx_emp['ultimo_match_empleabilidad_aliado_id'] = aliado.id
                    ctx_emp['ultimo_match_empleabilidad_fecha'] = timezone.now().isoformat()
                    estudiante.contexto_temporal = ctx_emp
                    estudiante.estado_onboarding = 'curso_finalizado'
                    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                    texto_respuesta = (
                        f"🏆 *¡Logro desbloqueado!*\n\n"
                        f"Validaste el código de *{aliado.nombre_empresa}*.\n"
                        "✅ Ya notificamos al equipo para iniciar el proceso de empleabilidad."
                    )
                    estudiante.estado_onboarding = 'curso_finalizado'
                elif codigo_ingresado in ('listo', 'continuar'):
                    texto_respuesta = (
                        "📍 Estás en el *radar de empleabilidad*.\n\n"
                        "No uses *listo* aquí: envía el *código secreto* del punto "
                        "(el que te indiquemos en la prueba / en la entrada)."
                    )
                    estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
                else:
                    if mision and mision.estado == 'descubierta':
                        mision.estado = 'reclamada'
                        mision.fecha_reclamada = timezone.now()
                        mision.save(update_fields=['estado', 'fecha_reclamada'])
                    texto_respuesta = (
                        "🔐 El código no coincide.\n\n"
                        "Verifica el código secreto en la entrada de la empresa y vuelve a enviarlo."
                    )
                    estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
                estudiante.save(update_fields=['estado_onboarding'])

            elif estudiante.estado_onboarding == 'esperando_respuesta_pregunta_abierta_final':
                from ..models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal, ProgresoEstudiante
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
                            from ..tutor_ia_modulo import evaluar_reto_facilitador
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
                                from ..gamificacion import PerfilGamificacion
                                from ..response_templates import _barra_progreso

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
                                    from ..certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
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

            # v1.9.8g: Post-certificate cutoff — no more interaction
            elif estudiante.estado_onboarding == 'curso_finalizado':
                print(f"🚫 Curso finalizado — sin interacción post-certificado")
                # Check if student has a new active course
                from ..models import ProgresoEstudiante
                nuevo_progreso = ProgresoEstudiante.objects.filter(
                    estudiante=estudiante, completado=False
                ).first()
                if nuevo_progreso:
                    # New course assigned — reset state
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    texto_respuesta = (
                        f"🎉 *¡Tienes un nuevo curso asignado!*\n\n"
                        f"📚 *{nuevo_progreso.curso.nombre}*\n\n"
                        f"Escribe *listo* para comenzar."
                    )
                else:
                    texto_respuesta = (
                        "✅ *Tu proceso del curso ya finalizó y tu certificado fue enviado.*\n\n"
                        "Cuando tu organización te inscriba en un nuevo curso, te notificaremos. "
                        "¡Gracias por tu participación! 🎓"
                    )
            
            # v1.9.8g: Asistente (compañero) — hasta 2 preguntas antes del reto
            elif estudiante.estado_onboarding == 'esperando_respuesta_asistente':
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
                        from ..models import ProgresoEstudiante
                        _pp = ProgresoEstudiante.objects.select_related('curso').get(id=progreso_id)
                        _na_curso = (_pp.curso.nombre_agente_asistente if _pp.curso else '') or ''
                    except ProgresoEstudiante.DoesNotExist:
                        pass
                nombre_asistente = (_na_cli or _na_curso or 'Darío').strip() or 'Darío'
                print(f"💬 Asistente ({nombre_asistente}): Esperando respuesta del compañero IA")
                
                msg_lower = msg_body.strip().lower()
                if msg_lower in ['ayuda', 'soporte', 'ticket']:
                    from ..security_handler import procesar_solicitud_soporte
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
                            f"Si no tiene preguntas, escriba *listo*."
                        ),
                    )
                elif _mensaje_indica_listo(msg_body) or preguntas_hechas >= 2:
                    # Flujo exigido: Darío -> Facilitadora (reto) al escribir listo
                    print("🎯 Asistente terminó → Activando Facilitadora con reto")
                    from ..models import ProgresoEstudiante
                    from ..tutor_ia_modulo import (
                        cargar_modulos_reto,
                        generar_reto_facilitador,
                        listar_modulos_cobertura_reto,
                    )
                    from ..models import Modulo as ModuloRetoCtx
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

                        nombre_tutor = (
                            (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                            progreso.curso.nombre_agente_tutor or
                            nombre_display_facilitador(progreso.curso)
                        )
                        reto = generar_reto_facilitador(
                            modulos_reto,
                            progreso.curso.nombre,
                            estudiante_nombre=estudiante.nombre or "Estudiante",
                            curso=progreso.curso,
                            modulo_checkpoint=modulos_reto[-1] if modulos_reto else None,
                        )
                        _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                        estudiante.contexto_temporal = {
                            'tipo': 'reto_facilitador',
                            'modulos_reto_ids': modulos_reto_ids,
                            'reto_texto': reto,
                            'progreso_id': progreso_id,
                            'es_final': ctx.get('es_reto_final', False),
                            '_ts_leccion': _prev_ts,
                        }
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
                        estudiante.contexto_temporal = None
                        estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
                        # Si el progreso ya está completado, no pedir *listo* como si hubiera más módulos
                        _prog_fin = None
                        try:
                            from ..models import ProgresoEstudiante
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
                    from ..models import ProgresoEstudiante
                    from ..tutor_ia_modulo import cargar_modulos_reto, generar_respuesta_asistente
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
                                f"Puede preguntar sobre el tema del curso. Si no, escriba *listo*."
                            ),
                        )
            
            # v1.9.8g: Facilitadora — evaluando respuesta al reto
            elif estudiante.estado_onboarding == 'esperando_respuesta_reto':
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
                    from ..security_handler import procesar_solicitud_soporte
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
                    from ..models import ProgresoEstudiante
                    from ..tutor_ia_modulo import cargar_modulos_reto, evaluar_reto_facilitador
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

                    nombre_tutor = (
                        (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                        nombre_display_facilitador(_curso_reto)
                    )
                    if progreso is not None:
                        nombre_tutor = (
                            progreso.curso.nombre_agente_tutor
                            or nombre_display_facilitador(progreso.curso)
                        )

                    msg_eval = construir_mensaje_evaluacion_reto(
                        estudiante, progreso, puntaje, feedback, nombre_tutor,
                    )
                    
                    es_final = ctx.get('es_final', False)
                    
                    if es_final and progreso:
                        pregunta_abierta = None
                        pregunta_abierta_ctx_id = ctx.get('pregunta_abierta_final_id')
                        if pregunta_abierta_ctx_id:
                            from ..models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal
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
                                from ..certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
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
                        from ..helpers_examenes import contexto_temporal_tras_cerrar_agente
                        from ..drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

                        _base_ctx = contexto_temporal_tras_cerrar_agente(progreso, _prev_ctx) or {}
                        estudiante.estado_onboarding = 'completado'
                        # Tras Darío + facilitadora: el drip/calendario aplica igual que sin agentes.
                        # No adelantar modulo_actual hasta que desbloquee el siguiente módulo.
                        if progreso:
                            modulo_cerrado = progreso.modulo_actual
                            from ..modulo_publicacion import (
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
                                    _base_ctx['post_reto_entregar_modulo_id'] = siguiente.id
                                estudiante.contexto_temporal = _base_ctx
                                estudiante.save(
                                    update_fields=['contexto_temporal', 'estado_onboarding']
                                )
                                texto_respuesta = (
                                    f"{msg_eval}\n\n"
                                    "✅ Escribe *continuar* para recibir el contenido del siguiente módulo.\n"
                                    "Cuando lo hayas revisado, responde *listo* para seguir."
                                )
                        else:
                            estudiante.contexto_temporal = _base_ctx
                            estudiante.save(
                                update_fields=['contexto_temporal', 'estado_onboarding']
                            )
                            texto_respuesta = (
                                f"{msg_eval}\n\n"
                                "✅ Escribe *continuar* para recibir el contenido del siguiente módulo.\n"
                                "Cuando lo hayas revisado, responde *listo* para seguir."
                            )
                    print(f"✅ Facilitadora reto evaluado | modo={modo_gami} | valor={puntaje}", flush=True)
            
            # 3.5a PRIORIDAD: Si está respondiendo al TUTOR IA (legacy)
            elif estudiante.estado_onboarding == 'esperando_respuesta_tutor_ia':
                from ..gamificacion import PerfilGamificacion
                print(f"🎓 Evaluando respuesta del Facilitador (legacy tutor IA)")
                ctx = estudiante.contexto_temporal or {}
                modulo_id = ctx.get('modulo_id')
                pregunta_tutor = ctx.get('pregunta_tutor', '')
                intentos = ctx.get('intentos_tutor', 0)
                
                # Detectar si el usuario quiere omitir el tutor
                msg_lower = msg_body.strip().lower()
                palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']
                
                if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    # Audio no pudo ser transcrito — pedir reintento
                    texto_respuesta = (
                        "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta.\n\n"
                        "Si prefieres continuar sin responder, escribe *listo*."
                    )
                elif any(p in msg_lower for p in palabras_skip):
                    # Usuario quiere seguir sin responder al tutor
                    estudiante.contexto_temporal = None
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    print(f"⏭️ Profesor Gerónimo omitido por usuario")
                    
                    # Si dijo "menu", retomar curso (B2B) o menú sandbox
                    if msg_lower in ['menu', 'menú']:
                        from ..flujo_whatsapp_b2b import respuesta_tras_keyword_menu
                        texto_respuesta = respuesta_tras_keyword_menu(
                            estudiante, estudiante.nombre, msg_body
                        )
                    else:
                        # v1.9.6: NO llamar continuar_leccion — el skip solo cierra el tutor.
                        # El estudiante ya tiene el contenido del módulo. Cuando lo estudie
                        # y escriba "listo" de nuevo, avanzará por el flujo normal (estado=completado).
                        texto_respuesta = "👍 Sin problema.\n\nContinúa revisando el contenido del módulo 👆\n\nCuando termines, escribe *listo* para avanzar al siguiente."
                        print(f"✅ v1.9.6: Skip Gerónimo sin avance automático", flush=True)
                else:
                    from ..tutor_ia_modulo import evaluar_respuesta_modulo
                    from ..models import Modulo
                    
                    try:
                        modulo = Modulo.objects.get(id=modulo_id) if modulo_id else None
                    except Modulo.DoesNotExist:
                        modulo = None
                    
                    if modulo:
                        aprobado, feedback = evaluar_respuesta_modulo(
                            modulo, msg_body, pregunta_tutor,
                            estudiante_nombre=estudiante.nombre or "Estudiante"
                        )
                        
                        # v1.9.8: Siempre 1 sola interacción — feedback y continúa
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save()
                        if aprobado:
                            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                            perfil.agregar_puntos(5, "Respuesta correcta - Profesor Gerónimo")
                            texto_respuesta = f"{feedback}\n\n💰 *+5 puntos bonus* por tu respuesta 💪\n\nContinúa revisando el módulo 👆\nCuando termines, escribe *listo* para avanzar."
                            print(f"✅ v1.9.8: Gerónimo aprobado — 1 interacción", flush=True)
                        else:
                            texto_respuesta = f"{feedback}\n\n✅ *¡Buen esfuerzo!* Sigue estudiando el módulo 👆\n\nCuando termines, escribe *listo* para avanzar."
                            print(f"✅ v1.9.8: Gerónimo incorrecto — feedback y continúa", flush=True)
                    else:
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save()
                        # v1.9.6: Solo enviar feedback, NO auto-avanzar
                        texto_respuesta = "✅ Gracias por tu respuesta!\n\nContinúa revisando el módulo 👆\nCuando termines, escribe *listo* para avanzar."
                        print(f"✅ v1.9.6: Gerónimo sin módulo — feedback sin auto-avance", flush=True)
            
            # 3.5a2 PRIORIDAD: Si está respondiendo a la REVISIÓN DE PROGRESO
            elif estudiante.estado_onboarding == 'esperando_respuesta_progreso':
                from ..gamificacion import PerfilGamificacion
                print(f"�‍🏫 Evaluando respuesta de María (Revisión de Progreso)")
                ctx = estudiante.contexto_temporal or {}
                pregunta_tutor = ctx.get('pregunta_tutor', '')
                modulos_info = ctx.get('modulos_info', '')
                intentos = ctx.get('intentos_tutor', 0)
                modulos_reto_ids = ctx.get('modulos_reto_ids', [])
                progreso_id = ctx.get('progreso_id')
                es_reto_final = ctx.get('es_reto_final', False)

                def _activar_reto_despues_de_maria(prefijo=""):
                    from ..models import ProgresoEstudiante, Modulo
                    from ..tutor_ia_modulo import (
                        cargar_modulos_reto,
                        generar_reto_facilitador,
                        listar_modulos_cobertura_reto,
                    )
                    progreso_r = (
                        ProgresoEstudiante.objects.filter(id=progreso_id)
                        .select_related('curso', 'modulo_actual')
                        .first()
                        if progreso_id
                        else None
                    )
                    _mids = list(modulos_reto_ids) if modulos_reto_ids else []
                    modulos_reto = (
                        cargar_modulos_reto(_mids, progreso_r.curso_id if progreso_r else None)
                        if _mids
                        else []
                    )
                    if not modulos_reto and progreso_r:
                        _mchk = None
                        _outer = estudiante.contexto_temporal or {}
                        mid = _outer.get('modulo_id')
                        if mid:
                            _mchk = Modulo.objects.filter(
                                id=mid, curso_id=progreso_r.curso_id
                            ).first()
                        if not _mchk and getattr(progreso_r, 'modulo_actual_id', None):
                            _mchk = progreso_r.modulo_actual
                        if _mchk:
                            modulos_reto = listar_modulos_cobertura_reto(_mchk, progreso_r.curso)
                            _mids = [m.id for m in modulos_reto]
                    if not (progreso_r and modulos_reto):
                        logger.warning(
                            "reto post-María vacío | progreso_id=%s modulo_ctx=%s ids_ctx=%s",
                            progreso_id,
                            (estudiante.contexto_temporal or {}).get('modulo_id'),
                            modulos_reto_ids,
                        )
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                        if progreso_r and progreso_r.completado:
                            return (
                                f"{prefijo}\n\n"
                                "🎉 Ya completaste este curso.\n\n"
                                "Si el certificado aún no llega, escribe *ayuda*. "
                                "Si tienes otro curso asignado, también puedes escribir *listo*."
                            ).strip()
                        return (
                            f"{prefijo}\n\n"
                            "Seguimos con tu curso. Escribí *listo* para continuar "
                            "o *ayuda* si necesitás soporte."
                        ).strip()
                    _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                    nombre_tutor = (
                        (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                        progreso_r.curso.nombre_agente_tutor or 'Claudia'
                    )
                    reto = generar_reto_facilitador(
                        modulos_reto,
                        progreso_r.curso.nombre,
                        estudiante_nombre=estudiante.nombre or "Estudiante",
                        curso=progreso_r.curso,
                        modulo_checkpoint=modulos_reto[-1] if modulos_reto else None,
                    )
                    _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                    estudiante.contexto_temporal = {
                        'tipo': 'reto_facilitador',
                        'modulos_reto_ids': _mids,
                        'reto_texto': reto,
                        'progreso_id': progreso_id,
                        'es_final': es_reto_final,
                        '_ts_leccion': _prev_ts,
                    }
                    estudiante.estado_onboarding = 'esperando_respuesta_reto'
                    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                    from core.tutor_ia_modulo import bloque_reto_whatsapp

                    bloque_reto = bloque_reto_whatsapp(nombre_tutor, reto)
                    return f"{prefijo}\n\n{bloque_reto}".strip()
                
                # Detectar si el usuario quiere omitir
                msg_lower = msg_body.strip().lower()
                palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']
                
                if msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    texto_respuesta = (
                        "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta.\n\n"
                        "Si prefieres continuar sin responder, escribe *listo*."
                    )
                elif any(p in msg_lower for p in palabras_skip):
                    print(f"⏭️ María omitida por usuario → activando reto")
                    
                    if msg_lower in ['menu', 'menú']:
                        from ..flujo_whatsapp_b2b import respuesta_tras_keyword_menu
                        texto_respuesta = respuesta_tras_keyword_menu(
                            estudiante, estudiante.nombre, msg_body
                        )
                    else:
                        texto_respuesta = _activar_reto_despues_de_maria("👍 Perfecto, pasemos al reto de la facilitadora.")
                else:
                    from ..tutor_ia_modulo import evaluar_respuesta_progreso
                    
                    resuelta, feedback = evaluar_respuesta_progreso(
                        modulos_info, msg_body, pregunta_tutor,
                        estudiante_nombre=estudiante.nombre or "Estudiante"
                    )
                    
                    if resuelta:
                        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                        perfil.agregar_puntos(3, "Revisión de progreso - María")
                        texto_respuesta = _activar_reto_despues_de_maria(f"{feedback}\n\n💰 *+3 puntos* por tu reflexión 💪")
                        print(f"✅ María resuelta — activando reto", flush=True)
                    else:
                        texto_respuesta = _activar_reto_despues_de_maria(f"{feedback}\n\n✅ *Buena reflexión!*")
                        print(f"✅ María evaluada — activando reto", flush=True)

            # 3.5a2 PRIORIDAD: Si está respondiendo pregunta de RECUPERACIÓN (<70 pts)
            elif estudiante.estado_onboarding == 'esperando_respuesta_recuperacion':
                ctx = estudiante.contexto_temporal or {}
                pregunta_data = ctx.get('pregunta_data', {})
                correcta = pregunta_data.get('correcta', 'A')
                explicacion = pregunta_data.get('explicacion', '')
                
                from ..tutor_ia_modulo import evaluar_respuesta_recuperacion
                es_correcta, msg_evaluacion = evaluar_respuesta_recuperacion(msg_body, correcta, explicacion)
                
                # Si acertó, dar puntos bonus
                if es_correcta:
                    try:
                        from ..gamificacion import PerfilGamificacion
                        perfil_rec = PerfilGamificacion.objects.get(estudiante=estudiante)
                        perfil_rec.agregar_puntos(15, "🏆 Pregunta de recuperación correcta")
                    except Exception:
                        pass
                
                # Limpiar estado y continuar al certificado
                curso_id = ctx.get('curso_id')
                estudiante.estado_onboarding = 'completado'
                estudiante.contexto_temporal = None
                estudiante.save()
                
                # Generar certificado y resumen
                from ..response_templates import _generar_completado_final
                msg_final = _generar_completado_final(estudiante, curso_id)
                
                texto_respuesta = f"[MULTI_MSG]{msg_evaluacion}[SEP]{msg_final}"

            # 3.5b PRIORIDAD: Si está respondiendo pregunta de módulo (examen clásico)
            elif estudiante.estado_onboarding == 'esperando_respuesta_modulo':
                from ..pregunta_handler import (
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
                        from ..response_templates import get_response_for_intent

                        texto_respuesta = get_response_for_intent(
                            'continuar_leccion',
                            estudiante.nombre,
                            estudiante_id=estudiante.id,
                            mensaje_original=msg_body,
                        )
                    else:
                        texto_respuesta = (
                            "No hay una pregunta pendiente. "
                            "Si quiere avanzar, escriba *listo*."
                        )
                elif msg_body.strip() == '[AUDIO_NO_TRANSCRITO]':
                    texto_respuesta = (
                        "⚠️ No pude escuchar tu audio. Por favor intenta de nuevo "
                        "o escríbeme tu respuesta."
                    )
                elif msg_body.strip().lower() in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    from ..flujo_whatsapp_b2b import respuesta_tras_keyword_menu
                    texto_respuesta = respuesta_tras_keyword_menu(
                        estudiante, estudiante.nombre, msg_body
                    )
                else:
                    # Validar respuesta a pregunta de módulo
                    from ..pregunta_handler import validar_respuesta, procesar_respuesta_abierta_ia
                    print(f"📝 Validando respuesta a pregunta de módulo")
                    
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
                        from ..helpers_examenes import puede_avanzar_modulo, es_modulo_checkpoint_reto_ia
                        
                        if modulo_completado:
                            progreso = modulo_completado.progreso
                            modulo_actual = modulo_completado.modulo
                        else:
                            # Para preguntas IA abierta, obtener progreso desde contexto
                            from ..models import ProgresoEstudiante, Modulo
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
                                from ..modulo_publicacion import (
                                    mensaje_bloqueo_sin_siguiente_publicado,
                                    siguiente_modulo_publicado_wa,
                                    total_modulos_publicados_wa,
                                )

                                from ..helpers_examenes import evaluar_checkpoint_reto_ia
                                from ..response_templates import (
                                    activar_checkpoint_facilitador,

```

El contrato de esta funcion esta al cierre de `02f_webhook_twilio_parte3.md`.
