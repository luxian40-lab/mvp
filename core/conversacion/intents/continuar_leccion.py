"""Intent `continuar_leccion` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.response_templates import LECCION_EN_CURSO, _VENTANA_ENTREGA_SEG, _barra_progreso, _cliente_habilita_pregunta_abierta_final, _es_mensaje_listo_avance_curso, _mensaje_pregunta_abierta_final, _retener_turno, _turno_estudiante, activar_checkpoint_facilitador, contexto_limpio, dividir_contenido_seguro, evaluar_checkpoint_reto_ia, logger, obtener_video_url, parte_mensaje_con_media, soltar_turno_entrega_actual, timezone
    from core.models import ProgresoEstudiante, ModuloCompletado
    
    estudiante_id = kwargs.get('estudiante_id')
    if not estudiante_id:
        return "Error al identificar estudiante. ⚠️"
    
    from core.models import Estudiante
    
    # ═══════════════════════════════════════════════════════════════
    # ANTI-DUPLICADO v1.9.1: Prevenir que dos workers entreguen
    # el mismo módulo simultáneamente (race condition con Gunicorn).
    # Bypass: llamadas internas post-evaluación de microcontenidos
    # (_bypass_anti_duplicado) — el alumno acaba de responder A/B, no es doble *listo*.
    # ═══════════════════════════════════════════════════════════════
    _salida = _preparar_progresos(kwargs, _turno_estudiante, estudiante_id, _retener_turno, soltar_turno_entrega_actual, Estudiante, _VENTANA_ENTREGA_SEG, LECCION_EN_CURSO, ProgresoEstudiante)
    if not isinstance(_salida, tuple):
        return _salida
    estudiante, mensaje_original, progresos_activos = _salida

    # Varios cursos activos: solo forzar curso en drip si TODOS están bloqueados.
    # Si hay al menos uno libre (p. ej. mid-pasos), no hijackear el *listo*.
    _salida = _elegir_progreso(progresos_activos, ProgresoEstudiante, estudiante)
    if not isinstance(_salida, tuple):
        return _salida
    progreso, = _salida
    
    _ctx_sesion_asistente = estudiante.contexto_temporal or {}
    _salida = _ubicar_modulo_listo(_ctx_sesion_asistente, estudiante, _es_mensaje_listo_avance_curso, mensaje_original, progreso, ProgresoEstudiante, contexto_limpio, logger, ModuloCompletado)
    if not isinstance(_salida, tuple):
        return _salida
    modulo_actual, msg_norm = _salida

    # Regla del curso: "listo" o "continuar" avanzan (mismo trigger).
    if _es_mensaje_listo_avance_curso(msg_norm):
        from core.drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

        ya_completo_modulo = ModuloCompletado.objects.filter(
            progreso=progreso,
            modulo=modulo_actual
        ).exists()
        if ya_completo_modulo and progreso.fecha_ultimo_avance:
            _blk = mensaje_bloqueo_avance_siguiente_modulo(
                estudiante, progreso, modulo_actual
            )
            if _blk:
                from core.avance_whatsapp import adaptar_mensaje_drip_bloqueo
                return adaptar_mensaje_drip_bloqueo(_blk, estudiante)

        from core.inicio_curso import falta_primera_entrega, mensaje_primera_entrega

        if falta_primera_entrega(estudiante, progreso, modulo_actual):
            return mensaje_primera_entrega(estudiante, progreso, modulo_actual)

        from core.module_steps import (
            modulo_usa_pasos,
            pasos_activos_qs,
            entregar_bloque_secciones_desde_paso,
            log_y_mensaje_modo_pasos_sin_pasos,
        )

        usa_pasos = modulo_usa_pasos(modulo_actual) if modulo_actual else False
        _n_pasos_raw = pasos_activos_qs(modulo_actual).count() if modulo_actual else 0
        _n_pasos = _n_pasos_raw if usa_pasos else 0

        if usa_pasos and _n_pasos_raw == 0:
            return log_y_mensaje_modo_pasos_sin_pasos(
                modulo_actual, 'continuar_leccion_listo'
            )

        _saltar_pasos = kwargs.get('_saltar_bloque_pasos_internos')

        if _n_pasos > 0 and not _saltar_pasos:
            idx_p = progreso.paso_actual_modulo or 1
            if idx_p < 1:
                idx_p = 1
                progreso.paso_actual_modulo = 1
                progreso.save(update_fields=['paso_actual_modulo'])
            if idx_p <= _n_pasos:
                try:
                    logger.info(
                        "📚 [pasos] listo → entregar paso | est=%s idx=%s n=%s",
                        estudiante.id,
                        idx_p,
                        _n_pasos,
                    )
                    return entregar_bloque_secciones_desde_paso(
                        progreso, modulo_actual, idx_p
                    )
                except ValueError:
                    logger.warning(
                        "⚠️ [pasos] índice inválido | est=%s idx=%s — se reintenta desde 1",
                        estudiante.id,
                        idx_p,
                        exc_info=True,
                    )
                    try:
                        from core.module_steps import reset_progreso_pasos_modulo

                        reset_progreso_pasos_modulo(progreso, save=True)
                        return entregar_bloque_secciones_desde_paso(
                            progreso, modulo_actual, 1
                        )
                    except ValueError:
                        logger.warning(
                            "⚠️ [pasos] reintento idx=1 también falló | est=%s",
                            estudiante.id,
                            exc_info=True,
                        )

        # Mini examen (PreguntaModulo): legacy sin pasos, o tras completar todos los pasos activos
        return _cerrar_modulo_listo(usa_pasos, _n_pasos, progreso, modulo_actual, ModuloCompletado, estudiante, logger, timezone, evaluar_checkpoint_reto_ia, activar_checkpoint_facilitador, _siguiente_modulo_listo, obtener_video_url, dividir_contenido_seguro, parte_mensaje_con_media, _cliente_habilita_pregunta_abierta_final, _mensaje_pregunta_abierta_final, contexto_limpio, _barra_progreso)
    
    # Cualquier otro texto en continuar_leccion: reenviar el módulo actual.
    else:
        return _reenviar_modulo_actual(estudiante, modulo_actual, progreso, obtener_video_url, dividir_contenido_seguro, parte_mensaje_con_media)


def _reenviar_modulo_actual(estudiante, modulo_actual, progreso, obtener_video_url, dividir_contenido_seguro, parte_mensaje_con_media):
    _ctx_show = dict(estudiante.contexto_temporal or {})
    if modulo_actual and _ctx_show.get('post_reto_entregar_modulo_id') == modulo_actual.id:
        _ctx_show.pop('post_reto_entregar_modulo_id', None)
        estudiante.contexto_temporal = _ctx_show or None
        estudiante.save(update_fields=['contexto_temporal'])

    from core.module_steps import (
        modulo_usa_pasos,
        mensaje_recordatorio_paso_actual,
        pasos_activos_qs,
        log_y_mensaje_modo_pasos_sin_pasos,
    )
    if modulo_actual and modulo_usa_pasos(modulo_actual):
        if not pasos_activos_qs(modulo_actual).exists():
            return log_y_mensaje_modo_pasos_sin_pasos(
                modulo_actual, 'continuar_leccion_mensaje_continuar'
            )
        _np_cur = pasos_activos_qs(modulo_actual).count()
        if (
            progreso.paso_actual_modulo > _np_cur
            and not progreso.esperando_respuesta_evaluacion_paso
        ):
            return (
                "✅ Ya recibiste todo el material de esta unidad.\n\n"
                "Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]"
            )
        _rem_p = mensaje_recordatorio_paso_actual(progreso, modulo_actual)
        if _rem_p:
            return _rem_p

    video_url = obtener_video_url(modulo_actual)

    # Verificar archivos multimedia
    archivos_multimedia_c = modulo_actual.archivos_multimedia.filter(activo=True)
    archivos_msg_c = ""
    primera_media_url_c = None
    extra_media_urls_c = []

    if archivos_multimedia_c.exists():
        archivos_msg_c = ""
        for idx, archivo in enumerate(archivos_multimedia_c):
            icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
            url = archivo.get_url_para_envio()
            if url:
                if not primera_media_url_c:
                    primera_media_url_c = url
                    archivos_msg_c += f"\n{icono} {archivo.titulo} (adjunto)"
                else:
                    extra_media_urls_c.append((url, archivo.titulo, icono))
                    archivos_msg_c += f"\n{icono} {archivo.titulo} (adjunto)"
            else:
                archivos_msg_c += f"\n{icono} {archivo.titulo}"

    if not archivos_multimedia_c.exists() and video_url:
        primera_media_url_c = video_url

    # Usar dividir_contenido_seguro para evitar exceder 1600 chars
    contenido_c = modulo_actual.contenido or ''
    chunks_c = dividir_contenido_seguro(contenido_c, max_chars=1300)
    modulo_header_c = f"{progreso.curso.emoji} {progreso.curso.nombre}\n\nMódulo {modulo_actual.numero}: {modulo_actual.titulo}\n\n"
    if chunks_c:
        respuesta = modulo_header_c + chunks_c[0]
        for chunk_c in chunks_c[1:]:
            if len(respuesta) + len(chunk_c) + 4 < 1400:
                respuesta += "\n\n" + chunk_c
            else:
                break
    else:
        respuesta = modulo_header_c + (modulo_actual.descripcion or '')
    # v1.9.8: No mostrar labels de archivos en texto (se envían como mensajes separados)

    # NO embeber video en respuesta — enviar como parte separada DESPUÉS del texto

    # "Escribe listo" solo si NO es el último módulo
    # Siempre usar multi-mensaje para garantizar orden: texto → video(s) → "escribe listo"
    partes_c = [respuesta]
    hay_media_c = False
    if primera_media_url_c:
        partes_c.append(parte_mensaje_con_media(primera_media_url_c))
        hay_media_c = True
    for extra_url_c, _extra_titulo_c, _extra_icono_c in extra_media_urls_c:
        partes_c.append(parte_mensaje_con_media(extra_url_c))
        hay_media_c = True
    if hay_media_c:
        partes_c.append("[DELAY:5]")
    partes_c.append("Tómese su tiempo para ver el material. Mientras usted aprende, aquí iremos organizando los recursos del siguiente nivel. En cuanto termine, solo responda *listo* para continuar.")

    from core.video_links import reescribir_videos_en_mensaje

    if len(partes_c) > 1:
        return reescribir_videos_en_mensaje(
            "[MULTI_MSG]" + "[SEP]".join(partes_c),
            estudiante=estudiante,
            curso=progreso.curso,
            modulo=modulo_actual,
        )

    return reescribir_videos_en_mensaje(
        respuesta,
        estudiante=estudiante,
        curso=progreso.curso,
        modulo=modulo_actual,
    )


def _siguiente_modulo_listo(siguiente_modulo, estudiante, progreso, modulo_actual, es_modulo_reto, logger, total_modulos, usar_ia_curso, decision_cp, obtener_video_url, dividir_contenido_seguro, activar_checkpoint_facilitador, parte_mensaje_con_media, _cliente_habilita_pregunta_abierta_final, timezone, _mensaje_pregunta_abierta_final, perfil, contexto_limpio, _barra_progreso):
    if siguiente_modulo:
        from core.drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

        _blk_fin = mensaje_bloqueo_avance_siguiente_modulo(
            estudiante, progreso, modulo_actual
        )
        # Checkpoint: compañero + facilitadora al cerrar el módulo — no lo bloquea el drip.
        if _blk_fin and not es_modulo_reto:
            logger.info(
                "⏳ [drip-block] estudiante_id=%s curso_id=%s modulo_actual=%s siguiente_modulo=%s",
                estudiante.id,
                progreso.curso_id,
                getattr(modulo_actual, 'numero', None),
                getattr(siguiente_modulo, 'numero', None),
            )
            from core.avance_whatsapp import adaptar_mensaje_drip_bloqueo
            return adaptar_mensaje_drip_bloqueo(_blk_fin, estudiante)

        _cp_pref = getattr(modulo_actual, 'facilitador_checkpoint', None)
        logger.info(
            '🎯 [checkpoint-leccion] curso=%s mod_cerrado_num=%s total_mod=%s usar_ia=%s '
            'facilitador_checkpoint=%s regla=%s -> es_reto=%s | est=%s',
            progreso.curso_id,
            getattr(modulo_actual, 'numero', None),
            total_modulos,
            usar_ia_curso,
            _cp_pref,
            decision_cp.regla_aplicada,
            es_modulo_reto,
            estudiante.id,
        )
    
        return _texto_siguiente_modulo(es_modulo_reto, estudiante, progreso, modulo_actual, siguiente_modulo, logger, obtener_video_url, dividir_contenido_seguro, activar_checkpoint_facilitador, parte_mensaje_con_media)

    else:
        # Completó el último módulo del curso (p. ej. balance GEI en M5)
        try:
            from formulario.hooks import intentar_iniciar_formulario_al_completar_modulo
            _msg_ficha = intentar_iniciar_formulario_al_completar_modulo(
                estudiante, progreso, modulo_actual, None
            )
        except Exception as _e:
            _msg_ficha = None
            logger.warning("Formulario GEI (último módulo): %s", _e, exc_info=True)
        if _msg_ficha:
            return _msg_ficha

        # Completó todos los módulos
        from core.models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal

        pregunta_abierta = None
        preguntas_abiertas = PreguntaAbiertaFinalCurso.objects.filter(
            curso=progreso.curso,
            activa=True
        ).order_by('orden', 'id')[:3]
        if preguntas_abiertas.exists():
            cliente_habilita = _cliente_habilita_pregunta_abierta_final(estudiante.cliente)
            curso_habilita = bool(getattr(progreso.curso, 'habilitar_pregunta_abierta_final', False))
            if not (cliente_habilita and curso_habilita):
                logger.info(
                    "⚠️ [templates] Fallback pregunta abierta final al completar curso | estudiante_id=%s | curso_id=%s | cliente_habilita=%s | curso_habilita=%s",
                    estudiante.id,
                    progreso.curso.id,
                    cliente_habilita,
                    curso_habilita,
                )
            for p in preguntas_abiertas:
                ya_respondio_abierta = RespuestaAbiertaFinal.objects.filter(
                    pregunta=p,
                    estudiante=estudiante
                ).exists()
                if not ya_respondio_abierta:
                    pregunta_abierta = p
                    break

        if pregunta_abierta:
            logger.info(
                "🧭 [templates] Pregunta abierta final seleccionada al completar curso | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                estudiante.id,
                progreso.curso.id,
                pregunta_abierta.id,
                getattr(pregunta_abierta, 'orden', None),
                (pregunta_abierta.pregunta or '')[:180],
            )

        usar_gamificacion_final = bool(
            progreso.curso.usar_gamificacion or
            (estudiante.cliente.usar_gamificacion if getattr(estudiante, 'cliente', None) else False)
        )

        if pregunta_abierta and not usar_gamificacion_final:
            progreso.completado = True
            progreso.fecha_completado = timezone.now()
            progreso.fecha_ultimo_avance = timezone.now()
            progreso.save(update_fields=['completado', 'fecha_completado', 'fecha_ultimo_avance'])

            ctx = estudiante.contexto_temporal or {}
            ctx.update({
                'tipo': 'pregunta_abierta_final',
                'curso_id': progreso.curso.id,
                'progreso_id': progreso.id,
                'pregunta_abierta_final_id': pregunta_abierta.id,
            })
            estudiante.contexto_temporal = ctx
            estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
            estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
            return _mensaje_pregunta_abierta_final(pregunta_abierta.pregunta)

        # Marcar curso como completado
        progreso.completado = True
        progreso.fecha_completado = timezone.now()
        progreso.fecha_ultimo_avance = timezone.now()
        progreso.save(update_fields=['completado', 'fecha_completado', 'fecha_ultimo_avance'])
    
        perfil.refresh_from_db()
        porcentaje = progreso.porcentaje_avance()
    
        # === v1.9.8h: RETO FINAL en lugar de pregunta de recuperación ===
        # Activar Darío + Claudia con reto que cubre TODOS los módulos
        return _cierre_curso_listo(usar_gamificacion_final, estudiante, progreso, contexto_limpio, pregunta_abierta, _barra_progreso, porcentaje, perfil)


def _cierre_curso_listo(usar_gamificacion_final, estudiante, progreso, contexto_limpio, pregunta_abierta, _barra_progreso, porcentaje, perfil):
    if usar_gamificacion_final:
        try:
            _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
            nombre_tutor = 'Formador'
            nombre_asistente = 'Compañero'
    
            modulos_final = list(progreso.curso.modulos.filter(numero__gte=4).order_by('numero'))
            if not modulos_final:
                modulos_final = list(progreso.curso.modulos.all().order_by('numero'))
            if modulos_final:
                modulo_inicio = modulos_final[0].numero
                modulo_fin = modulos_final[-1].numero
                if modulo_inicio == modulo_fin:
                    modulos_final_range = f"el módulo {modulo_inicio}"
                else:
                    modulos_final_range = f"los módulos {modulo_inicio} a {modulo_fin}"
            else:
                modulos_final_range = "los módulos finales"
    
            from core.agentes_whatsapp import mensaje_con_titular_agente

            dario_final = mensaje_con_titular_agente(
                nombre_asistente,
                (
                    f"¡Felicitaciones! Terminaste todos los módulos. "
                    f"Antes de recibir tu certificado, {nombre_tutor} tiene un reto final para ti sobre {modulos_final_range}.\n\n"
                    "¿Tiene alguna pregunta sobre lo que vimos en esta parte del curso? Envíeme un audio o escríbame. Si no tiene preguntas, pulse continuar, para seguir aprendiendo.\n\n"
                    "[SEND_BUTTON:continuemos]"
                ),
            )
    
            _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
            estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
                'tipo': 'asistente_dario',
                'curso_activo_id': progreso.curso_id,
                'modulo_id': modulos_final[-1].id if modulos_final else None,
                'progreso_id': progreso.id,
                'modulos_reto_ids': [m.id for m in modulos_final],
                'preguntas_hechas': 0,
                'es_reto_final': True,
                '_ts_leccion': _prev_ts,
            })
            if pregunta_abierta:
                estudiante.contexto_temporal['pregunta_abierta_final_id'] = pregunta_abierta.id
            estudiante.estado_onboarding = 'esperando_respuesta_asistente'
            estudiante.save()

            return dario_final
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"⚠️ Reto final falló: {e}, generando certificado directo")
    
    # Fallback: certificado directo (sin gamificación o si falla el reto)
    barra = _barra_progreso(porcentaje)
    
    mensaje = (
        f"🎉 *¡CURSO COMPLETADO!*\n\n"
        f"📊 Puntos: *{perfil.puntos_totales} pts*\n"
        f"{barra} {porcentaje}%\n\n"
        f"🎓 *¡Felicitaciones! Ha completado todo el curso.*"
    )
    
    msg_cert_img = ""
    try:
        from core.certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
        cert = crear_certificado_automatico(estudiante, progreso.curso)
        if cert and cert.archivo_imagen:
            cert_url = obtener_url_certificado_twilio(cert)
            if cert_url:
                msg_cert_img = f"🎓 *¡Su certificado!*\n\n[MEDIA:{cert_url}]"
            else:
                from django.conf import settings as _s
                bucket = getattr(_s, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
                s3_key = str(cert.archivo_imagen.name)
                cert_url = f"https://{bucket}.s3.us-east-2.amazonaws.com/{s3_key}"
                msg_cert_img = f"🎓 *¡Su certificado!*\n\n[MEDIA:{cert_url}]"
        elif cert and cert.archivo_pdf:
            cert_url = cert.archivo_pdf.url
            msg_cert_img = f"🎓 *¡Su certificado!*\n📄 Descárgalo: {cert_url}"
        else:
            msg_cert_img = "🎓 Su certificado se está generando. Se lo enviaremos pronto."
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ Certificado falló: {e}")
        msg_cert_img = "🎓 Su certificado se está generando. Se lo enviaremos pronto."
    
    estudiante.estado_onboarding = 'curso_finalizado'
    estudiante.save()
    
    partes = [mensaje]
    if msg_cert_img:
        partes.append(msg_cert_img)
    return "[MULTI_MSG]" + "[SEP]".join(partes)


def _texto_siguiente_modulo(es_modulo_reto, estudiante, progreso, modulo_actual, siguiente_modulo, logger, obtener_video_url, dividir_contenido_seguro, activar_checkpoint_facilitador, parte_mensaje_con_media):
    if not es_modulo_reto:
        try:
            from formulario.hooks import intentar_iniciar_formulario_al_completar_modulo
            _msg_ficha = intentar_iniciar_formulario_al_completar_modulo(
                estudiante, progreso, modulo_actual, siguiente_modulo
            )
        except Exception as _e:
            _msg_ficha = None
            logger.warning("Formulario GEI: no se pudo iniciar sesión: %s", _e, exc_info=True)
        if _msg_ficha:
            return _msg_ficha
        progreso.modulo_actual = siguiente_modulo
        from core.module_steps import (
            reset_progreso_pasos_modulo,
            modulo_usa_pasos,
            pasos_activos_qs,
            entregar_bloque_secciones_desde_paso,
            log_y_mensaje_modo_pasos_sin_pasos,
        )
        reset_progreso_pasos_modulo(progreso, save=False)
        progreso.save()
        if modulo_usa_pasos(siguiente_modulo):
            if not pasos_activos_qs(siguiente_modulo).exists():
                return log_y_mensaje_modo_pasos_sin_pasos(
                    siguiente_modulo, 'avance_siguiente_modulo'
                )
            logger.info(
                "📚 [pasos] primer paso del módulo siguiente | est=%s mod_id=%s",
                estudiante.id,
                siguiente_modulo.id,
            )
            return entregar_bloque_secciones_desde_paso(
                progreso, siguiente_modulo, 1
            )
    
    porcentaje = progreso.porcentaje_avance()
    video_url = obtener_video_url(siguiente_modulo)
    
    # Verificar archivos multimedia del módulo
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
        print(f"📎 Multimedia módulo: {archivos_multimedia.count()} archivos, primera_media={'Sí' if primera_media_url else 'No'}, extras={len(extra_media_urls)}", flush=True)

    # Si no hay archivos multimedia pero sí video_url, usarlo como primera media
    if not archivos_multimedia.exists() and video_url:
        primera_media_url = video_url

    # v1.9.8i: No "completado" message — just flow to next content
    
    # Mensaje: Siguiente módulo CON multimedia embebida
    from core.module_steps import texto_legacy_whatsapp
    contenido_mod = texto_legacy_whatsapp(siguiente_modulo)
    chunks_mod = dividir_contenido_seguro(contenido_mod, max_chars=1300)
    modulo_header = f"📖 *Módulo {siguiente_modulo.numero}: {siguiente_modulo.titulo}*\n\n"
    if chunks_mod:
        msg_modulo = modulo_header + chunks_mod[0]
        for chunk_m in chunks_mod[1:]:
            if len(msg_modulo) + len(chunk_m) + 4 < 1400:
                msg_modulo += "\n\n" + chunk_m
            else:
                break
    else:
        msg_modulo = modulo_header + (siguiente_modulo.descripcion or '')
    # v1.9.8: No mostrar labels de archivos en texto (se envían como mensajes separados)
    
    # NO embeber media en msg_modulo — enviar video como mensaje separado después del texto
    # primera_media_url y extra_media_urls se agregan como partes separadas más abajo
    
    if es_modulo_reto:
        # Reto: solo el compañero; el siguiente módulo se entrega tras evaluarlo.
        return activar_checkpoint_facilitador(
            estudiante, progreso, modulo_actual
        )
    
    # v1.9.8i: Normal module — just show next module (no completado msg)
    partes = [msg_modulo]
    hay_media = False
    if primera_media_url:
        partes.append(parte_mensaje_con_media(primera_media_url))
        hay_media = True
    for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
        partes.append(parte_mensaje_con_media(extra_url))
        hay_media = True
    if hay_media:
        partes.append("[DELAY:5]")
    from core.avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo

    partes.append(
        resolver_cta_listo(estudiante, progreso.curso, CTX_FIN_ENTREGA_MODULO)
    )
    from core.video_links import reescribir_videos_en_mensaje

    return reescribir_videos_en_mensaje(
        "[MULTI_MSG]" + "[SEP]".join(partes),
        estudiante=estudiante,
        curso=progreso.curso,
        modulo=siguiente_modulo,
    )


def _cerrar_modulo_listo(usa_pasos, _n_pasos, progreso, modulo_actual, ModuloCompletado, estudiante, logger, timezone, evaluar_checkpoint_reto_ia, activar_checkpoint_facilitador, _siguiente_modulo_listo, obtener_video_url, dividir_contenido_seguro, parte_mensaje_con_media, _cliente_habilita_pregunta_abierta_final, _mensaje_pregunta_abierta_final, contexto_limpio, _barra_progreso):
    from core.pregunta_handler import tiene_pregunta_modulo, obtener_pregunta_modulo, formatear_pregunta, guardar_contexto_pregunta

    pasos_internos_completos = (
        usa_pasos
        and _n_pasos > 0
        and progreso.paso_actual_modulo > _n_pasos
        and not progreso.esperando_respuesta_evaluacion_paso
    )
    legacy_sin_pasos = _n_pasos == 0

    if (
        (legacy_sin_pasos or pasos_internos_completos)
        and tiene_pregunta_modulo(modulo_actual)
    ):
        ya_respondio = ModuloCompletado.objects.filter(
            progreso=progreso,
            modulo=modulo_actual
        ).exists()

        if not ya_respondio:
            pregunta = obtener_pregunta_modulo(modulo_actual)
            if pregunta:
                guardar_contexto_pregunta(estudiante, modulo_actual, pregunta, progreso)
                logger.info(
                    "📝 [mini-examen] mostrar PreguntaModulo | est=%s modulo=%s tras_pasos=%s",
                    estudiante.id,
                    modulo_actual.id,
                    pasos_internos_completos,
                )
                return formatear_pregunta(pregunta)

    # Completar módulo y avanzar (el tutor IA se envía como mensaje separado después)
    from core.gamificacion import PerfilGamificacion
    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    nivel_antes = perfil.nivel

    # v1.9.8j: Check if module was already completed BEFORE creating it
    modulo_ya_completado = ModuloCompletado.objects.filter(
        progreso=progreso, modulo=modulo_actual
    ).exists()

    if _n_pasos > 0 or not tiene_pregunta_modulo(modulo_actual):
        modulo_creado, created = ModuloCompletado.objects.get_or_create(
            progreso=progreso,
            modulo=modulo_actual
        )
        if created:
            progreso.fecha_ultimo_avance = timezone.now()
            progreso.save(update_fields=['fecha_ultimo_avance'])

    perfil.refresh_from_db()
    subio_nivel = perfil.nivel > nivel_antes

    from core.modulo_publicacion import (
        mensaje_bloqueo_sin_siguiente_publicado,
        siguiente_modulo_publicado_wa,
        total_modulos_publicados_wa,
    )

    total_modulos = total_modulos_publicados_wa(progreso.curso)
    usar_ia_curso = bool(getattr(progreso.curso, 'usar_agentes_ia', True))
    decision_cp = evaluar_checkpoint_reto_ia(
        modulo_actual,
        total_modulos,
        usar_ia_curso,
        modulo_ya_completado=modulo_ya_completado,
    )
    es_modulo_reto = decision_cp.es_reto
    try:
        from core.eventos_ia import emit_checkpoint_evaluado

        emit_checkpoint_evaluado(
            decision_cp,
            estudiante=estudiante,
            curso=progreso.curso,
            modulo=modulo_actual,
            origen='continuar_leccion',
        )
    except Exception:
        pass

    _blk_pub = mensaje_bloqueo_sin_siguiente_publicado(
        estudiante, progreso, modulo_actual
    )
    if _blk_pub:
        # El checkpoint no lo tapa el siguiente módulo en borrador: primero el
        # reto, y el bloqueo llega al cerrarlo (ver flujo reto en views).
        if es_modulo_reto:
            return activar_checkpoint_facilitador(
                estudiante, progreso, modulo_actual
            )
        from core.avance_whatsapp import adaptar_mensaje_drip_bloqueo
        return adaptar_mensaje_drip_bloqueo(_blk_pub, estudiante)

    siguiente_modulo = siguiente_modulo_publicado_wa(progreso.curso, modulo_actual)

    return _siguiente_modulo_listo(siguiente_modulo, estudiante, progreso, modulo_actual, es_modulo_reto, logger, total_modulos, usar_ia_curso, decision_cp, obtener_video_url, dividir_contenido_seguro, activar_checkpoint_facilitador, parte_mensaje_con_media, _cliente_habilita_pregunta_abierta_final, timezone, _mensaje_pregunta_abierta_final, perfil, contexto_limpio, _barra_progreso)


def _ubicar_modulo_listo(_ctx_sesion_asistente, estudiante, _es_mensaje_listo_avance_curso, mensaje_original, progreso, ProgresoEstudiante, contexto_limpio, logger, ModuloCompletado):
    if (
        _ctx_sesion_asistente.get('tipo') == 'asistente_dario'
        and estudiante.estado_onboarding == 'esperando_respuesta_asistente'
    ):
        # *listo* / *continuar* → pasar a Claudia (mismo contrato que el webhook).
        # Antes solo se reenviaba el nudge y el alumno veía el mismo mensaje muchas veces.
        if _es_mensaje_listo_avance_curso(mensaje_original or ''):
            from core.tutor_ia_modulo import (
                cargar_modulos_reto,
                generar_reto_facilitador,
                listar_modulos_cobertura_reto,
            )
            from core.models import Modulo as ModuloRetoCtx

            progreso_id = _ctx_sesion_asistente.get('progreso_id') or progreso.id
            modulos_reto_ids = list(_ctx_sesion_asistente.get('modulos_reto_ids') or [])
            try:
                progreso_reto = ProgresoEstudiante.objects.get(id=progreso_id)
            except ProgresoEstudiante.DoesNotExist:
                progreso_reto = progreso
            modulos_reto = cargar_modulos_reto(
                modulos_reto_ids, progreso_reto.curso_id if progreso_reto else None
            )
            if not modulos_reto and progreso_reto and _ctx_sesion_asistente.get('modulo_id'):
                _mchk = ModuloRetoCtx.objects.filter(
                    id=_ctx_sesion_asistente['modulo_id'],
                    curso_id=progreso_reto.curso_id,
                ).first()
                if _mchk:
                    modulos_reto = listar_modulos_cobertura_reto(_mchk, progreso_reto.curso)
                    modulos_reto_ids = [m.id for m in modulos_reto]
            if modulos_reto and progreso_reto:
                _cliente = (
                    estudiante.cliente
                    if getattr(estudiante, 'cliente_id', None)
                    else None
                )
                nombre_tutor = 'Formador'
                reto = generar_reto_facilitador(
                    modulos_reto, progreso_reto.curso.nombre,
                    estudiante_nombre=estudiante.nombre or 'Estudiante',
                    curso=progreso_reto.curso,
                    modulo_checkpoint=modulos_reto[-1] if modulos_reto else None,
                    estudiante=estudiante,
                )
                _prev_ts = _ctx_sesion_asistente.get('_ts_leccion', 0)
                estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
                    'tipo': 'reto_facilitador',
                    'modulos_reto_ids': modulos_reto_ids,
                    'reto_texto': reto,
                    'progreso_id': progreso_id,
                    'es_final': _ctx_sesion_asistente.get('es_reto_final', False),
                    '_ts_leccion': _prev_ts,
                })
                estudiante.estado_onboarding = 'esperando_respuesta_reto'
                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
                logger.info(
                    "continuar_leccion: Darío→Claudia por *listo* | estudiante_id=%s",
                    estudiante.id,
                )
                from core.tutor_ia_modulo import bloque_reto_whatsapp

                return bloque_reto_whatsapp(nombre_tutor, reto)
            estudiante.estado_onboarding = 'completado'
            estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal)
            estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
            return (
                "Seguimos con tu curso. Escribí *listo* para continuar "
                "o *ayuda* si necesitás soporte."
            )
        logger.info(
            "continuar_leccion: ya hay sesión activa con el compañero | estudiante_id=%s",
            estudiante.id,
        )
        return (
            "💬 Sigues con tu compañero de estudio.\n\n"
            "Escribe una pregunta de repaso o *listo* para pasar al reto con la facilitadora."
        )

    # Obtener módulo actual
    modulo_actual = progreso.modulo_actual
    if not modulo_actual:
        # Si no hay módulo actual, tomar el primero
        modulo_actual = progreso.curso.modulos.order_by('numero').first()
        if not modulo_actual:
            return f"❌ El curso {progreso.curso.nombre} no tiene módulos configurados. Contacta a soporte."
        progreso.modulo_actual = modulo_actual
        from core.module_steps import reset_progreso_pasos_modulo
        reset_progreso_pasos_modulo(progreso, save=False)
        progreso.save()

    # Tras cerrar reto (Darío + facilitadora), el puntero ya está en el siguiente módulo pero el estudiante
    # aún no ha visto su contenido. Un "listo" aquí no debe cerrar ese módulo (evita saltar módulo 4):
    # debe ENTREGAR el material. Con microcontenidos eso es entregar_bloque; sin ellos, el else reenvía texto.
    msg_norm = (mensaje_original or '').strip()
    _ctx_reto = dict(estudiante.contexto_temporal or {})
    _post_reto_mid = _ctx_reto.get('post_reto_entregar_modulo_id')
    primero_listo_sin_ver_modulo = (
        _es_mensaje_listo_avance_curso(msg_norm)
        and _post_reto_mid
        and modulo_actual
        and modulo_actual.id == _post_reto_mid
        and not ModuloCompletado.objects.filter(progreso=progreso, modulo=modulo_actual).exists()
    )
    if primero_listo_sin_ver_modulo:
        from core.module_steps import (
            entregar_bloque_secciones_desde_paso,
            modulo_usa_pasos,
            pasos_activos_qs,
            reset_progreso_pasos_modulo,
        )

        _ctx_reto.pop('post_reto_entregar_modulo_id', None)
        estudiante.contexto_temporal = _ctx_reto or None
        estudiante.save(update_fields=['contexto_temporal'])

        if modulo_usa_pasos(modulo_actual) and pasos_activos_qs(modulo_actual).exists():
            _n_post = pasos_activos_qs(modulo_actual).count()
            idx_post = progreso.paso_actual_modulo or 1
            if idx_post > _n_post:
                reset_progreso_pasos_modulo(progreso, save=True)
                idx_post = 1
            logger.info(
                "📚 [pasos] primer listo post-reto → entregar material | est=%s idx=%s n=%s mod=%s",
                estudiante.id,
                idx_post,
                _n_post,
                modulo_actual.id,
            )
            return entregar_bloque_secciones_desde_paso(
                progreso, modulo_actual, idx_post
            )
        # Legacy (sin microcontenidos): caer al reenvío de Modulo.contenido, no al cierre.
        msg_norm = ''
    return (modulo_actual, msg_norm)


def _elegir_progreso(progresos_activos, ProgresoEstudiante, estudiante):
    if progresos_activos.count() > 1:
        from core.drip_schedule import drip_bloquea_siguiente_modulo

        _bloqueados_drip = []
        _libres_drip = []
        for _p in progresos_activos:
            _m = _p.modulo_actual
            if _m and drip_bloquea_siguiente_modulo(_p, _m):
                _bloqueados_drip.append(_p)
            else:
                _libres_drip.append(_p)
        if _bloqueados_drip and not _libres_drip:
            _bloqueados_drip.sort(
                key=lambda p: p.fecha_ultimo_avance.timestamp() if p.fecha_ultimo_avance else 0.0,
                reverse=True,
            )
            _chosen = _bloqueados_drip[0]
            progresos_activos = ProgresoEstudiante.objects.filter(id=_chosen.id)
            _ctx_drip = dict(estudiante.contexto_temporal or {})
            _ctx_drip['curso_activo_id'] = _chosen.curso_id
            estudiante.contexto_temporal = _ctx_drip
            estudiante.save(update_fields=['contexto_temporal'])

    # Si tiene MÚLTIPLES cursos activos (sandbox o B2B), preguntar cuál continuar
    if progresos_activos.count() > 1:
        respuesta = "📚 Tienes varios cursos activos:\n\n"
        for idx, prog in enumerate(progresos_activos, 1):
            porcentaje = prog.porcentaje_avance()
            respuesta += f"{idx}️⃣ {prog.curso.emoji} {prog.curso.nombre}\n"
            respuesta += f"   📊 Avance: {porcentaje}%\n"
            if prog.modulo_actual:
                respuesta += f"   📖 Módulo actual: {prog.modulo_actual.numero} - {prog.modulo_actual.titulo}\n"
            respuesta += "\n"
    
        respuesta += "Escribe el número del curso o *tomar* y el número (ej.: *tomar 2*).\n"
        respuesta += "Ejemplo: \"1\" o \"2\" — así evitamos confundirlo con las opciones del menú (1, 2, 3)."
    
        # Guardar estado para que views.py intercepte la respuesta numérica
        estudiante.estado_onboarding = 'esperando_seleccion_curso'
        _ctx_sel = dict(estudiante.contexto_temporal or {})
        _ctx_sel['tipo'] = 'seleccion_curso'
        _ctx_sel.pop('curso_activo_id', None)
        estudiante.contexto_temporal = _ctx_sel
        estudiante.save()
    
        return respuesta

    # Si solo tiene UN curso activo, continuar directamente
    progreso = progresos_activos.first()

    # NOTA: Esta validación es redundante pero se mantiene por seguridad
    # first() retorna None si no hay resultados, no genera excepción
    if not progreso:
        return """Aún no tienes un curso asignado. 📚

    Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""

    if progreso.curso_id and getattr(progreso.curso, 'es_modo_clases', lambda: False)():
        return (
            f"📚 *{progreso.curso.nombre}* se estudia en *Aprende* "
            "(clases y biblioteca), no con *listo* por WhatsApp.\n\n"
            "Escribe *aula* para entrar, o abre:\n"
            "https://aprende.eki.technology/aprende/estudiante/login/"
        )
    return (progreso,)


def _preparar_progresos(kwargs, _turno_estudiante, estudiante_id, _retener_turno, soltar_turno_entrega_actual, Estudiante, _VENTANA_ENTREGA_SEG, LECCION_EN_CURSO, ProgresoEstudiante):
    import time as _time
    from django.db import transaction

    _dedup_ok = bool(kwargs.get('_bypass_anti_duplicado'))
    if not _dedup_ok:
        # Un segundo *listo* en el mismo hilo de un test suelta el turno anterior.
        # En el webhook la retención sigue activa y el segundo *listo* no avanza.
        previo = _turno_estudiante.get()
        if previo and previo != estudiante_id and not _retener_turno.get():
            soltar_turno_entrega_actual()
        try:
            with transaction.atomic():
                est_lock = Estudiante.objects.select_for_update().get(id=estudiante_id)
                ctx_lock = dict(est_lock.contexto_temporal or {})
                now_ts = _time.time()
                en_curso = (
                    ctx_lock.get('_leccion_enviando')
                    and now_ts - float(ctx_lock.get('_ts_leccion') or 0) < _VENTANA_ENTREGA_SEG
                )
                if en_curso:
                    print(
                        "⏳ [ANTI-DUPLICADO] continuar_leccion en curso: "
                        "el *listo* anterior todavía se está enviando",
                        flush=True,
                    )
                else:
                    ctx_lock['_leccion_enviando'] = True
                    ctx_lock['_ts_leccion'] = now_ts
                    est_lock.contexto_temporal = ctx_lock
                    est_lock.save(update_fields=['contexto_temporal'])
                    _turno_estudiante.set(estudiante_id)
                    _dedup_ok = True
        except Exception as e:
            print(f"⚠️ [ANTI-DUPLICADO] Error en lock: {e}", flush=True)
            _dedup_ok = True  # En caso de error, permitir (fail-open)

    if not _dedup_ok:
        return LECCION_EN_CURSO
    # ═══════════════════════════════════════════════════════════════

    estudiante = Estudiante.objects.get(id=estudiante_id)

    try:
        from core.models import EstudianteEventoAprendizaje
        from core.telemetria import marcar_recordatorio_respondido, registrar_evento

        prog0 = (
            ProgresoEstudiante.objects.filter(estudiante=estudiante, completado=False)
            .select_related('curso', 'modulo_actual')
            .first()
        )
        registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_LISTO_RECIBIDO,
            estudiante=estudiante,
            curso=prog0.curso if prog0 else None,
            modulo=prog0.modulo_actual if prog0 else None,
            paso=getattr(prog0, 'paso_evaluacion_paso', None) if prog0 else None,
            metadata={'origen': 'continuar_leccion'},
        )
        marcar_recordatorio_respondido(estudiante)
    except Exception:
        pass

    mensaje_original = kwargs.get('mensaje_original', '').lower()

    # Validar que el estudiante existe
    if not estudiante:
        return "❌ Error al identificar tu perfil. Por favor contacta soporte."

    # Buscar todos los progresos activos (no completados)
    progresos_activos = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        completado=False
    ).order_by('-fecha_inicio')

    if not progresos_activos.exists():
        completados = (
            ProgresoEstudiante.objects.filter(
                estudiante=estudiante,
                completado=True,
            )
            .select_related('curso')
            .order_by('-fecha_inicio')
        )
        if completados.exists():
            nombres = ', '.join(
                f"*{p.curso.nombre}*" for p in completados[:3] if p.curso_id
            )
            return (
                f"🎉 Ya completaste {nombres}.\n\n"
                "No hay más módulos pendientes en ese curso. "
                "Si estás en el reto final o el certificado, responde lo que te pidió el agente "
                "o escribe *ayuda* si necesitas soporte.\n\n"
                "Si tu organización te asigna otro curso, te avisaremos por aquí."
            )
        return """Aún no tienes un curso asignado. 📚

    Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""

    # Curso en foco: tras elegir de la lista multi-curso (selector_curso), seguir ese curso hasta *menú* u otro cambio explícito
    _ctx_foco = estudiante.contexto_temporal or {}
    _curso_foco_id = _ctx_foco.get('curso_activo_id')
    if _curso_foco_id:
        _foco_qs = progresos_activos.filter(curso_id=_curso_foco_id)
        if _foco_qs.exists():
            progresos_activos = _foco_qs
        else:
            _ctx_foco = dict(_ctx_foco)
            _ctx_foco.pop('curso_activo_id', None)
            estudiante.contexto_temporal = _ctx_foco or None
            estudiante.save(update_fields=['contexto_temporal'])

    # 10x / modo Clases: *listo* no avanza por WA; el estudio es en Aprende.
    progresos_activos = progresos_activos.select_related('curso')
    if progresos_activos.count() == 1:
        _p_clases = progresos_activos.first()
        _c_clases = getattr(_p_clases, 'curso', None)
        if _c_clases is not None and getattr(_c_clases, 'es_modo_clases', lambda: False)():
            return (
                f"📚 *{_c_clases.nombre}* se estudia en *Aprende* "
                "(clases y biblioteca), no con *listo* por WhatsApp.\n\n"
                "Escribe *aula* para entrar, o abre:\n"
                "https://aprende.eki.technology/aprende/estudiante/login/\n\n"
                "Si también tienes un curso por WhatsApp, escribe *menú*."
            )
    elif progresos_activos.count() > 1:
        _solo_clases = all(
            getattr(p.curso, 'es_modo_clases', lambda: False)()
            for p in progresos_activos
            if p.curso_id
        )
        if _solo_clases:
            _noms = ', '.join(f"*{p.curso.nombre}*" for p in progresos_activos[:3] if p.curso_id)
            return (
                f"📚 Tus cursos ({_noms}) se estudian en *Aprende*, "
                "no con *listo* aquí.\n\n"
                "Escribe *aula* o entra a:\n"
                "https://aprende.eki.technology/aprende/estudiante/login/"
            )
    return (estudiante, mensaje_original, progresos_activos)
