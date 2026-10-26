"""Intent `inscribir_curso` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.response_templates import dividir_contenido_seguro, logger, obtener_video_url, parte_mensaje_con_media, partir_sep, timezone
    from core.models import ProgresoEstudiante, Estudiante
    from core.selector_curso import cursos_visibles_para_estudiante
    import re
    
    mensaje_original = kwargs.get('mensaje_original', '').strip()
    estudiante_id = kwargs.get('estudiante_id')
    
    if not estudiante_id:
        return "Error al identificar estudiante. ⚠️"
    
    try:
        estudiante = Estudiante.objects.select_related('cliente').get(id=estudiante_id)
    except Estudiante.DoesNotExist:
        return "❌ Error: No se encontró tu perfil de estudiante."
    
    curso = None
    cursos_activos = list(cursos_visibles_para_estudiante(estudiante))
    
    if not cursos_activos:
        return (
            "❌ No hay cursos disponibles para tu organización en este momento.\n\n"
            "Si el curso acaba de publicarse, espera unos minutos o escribe *ayuda*."
        )
    
    # Detectar número del curso (evitar tomar el dígito de "opción 1" en frases largas: solo si mensaje es corto o patrón tomar/inscribir)
    match = re.search(r'\d+', mensaje_original)
    if match and (
        len(mensaje_original) <= 12
        or re.match(r'^(tomar|inscribir)\s*\d+', mensaje_original.lower())
    ):
        numero_curso = int(match.group())
        if 1 <= numero_curso <= len(cursos_activos):
            curso = cursos_activos[numero_curso - 1]
        else:
            return f"❌ Número inválido. Tienes {len(cursos_activos)} cursos disponibles.\n\nEscribe \"ver cursos\" para verlos."
    elif len(cursos_activos) == 1:
        curso = cursos_activos[0]
    else:
        return (
            "📚 Para *iniciar un curso*, escribe el *número* de la lista.\n\n"
            "Ejemplo: *1* o *2*\n\n"
            "Escribe *ver cursos* para ver la lista."
        )
    
    # Verificar si ya está inscrito
    progreso_existente = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        curso=curso
    ).first()
    
    if progreso_existente:
        porcentaje = progreso_existente.porcentaje_avance()
        
        if progreso_existente.completado:
            return f"""✅ Ya completaste *{curso.emoji} {curso.nombre}*\n\n¡Felicidades! 🎉\n\nEscribe "ver cursos" para tomar otro curso."""
        
        # Curso ya iniciado - reactivar
        progreso_existente.fecha_inicio = timezone.now()
        progreso_existente.save()
        
        modulo_actual = progreso_existente.modulo_actual
        return f"""✅ Retomando *{curso.emoji} {curso.nombre}*\n\n📍 Módulo actual: {modulo_actual.numero}. {modulo_actual.titulo}\n📈 Avance: {porcentaje}%\n\nEscribe "continuar" para seguir."""
    
    # Inscribir al estudiante (nuevo)
    primer_modulo = curso.modulos.order_by('numero').first()
    
    if not primer_modulo:
        return f"❌ El curso {curso.nombre} no tiene módulos configurados aún."
    
    progreso = ProgresoEstudiante.objects.create(
        estudiante=estudiante,
        curso=curso,
        modulo_actual=primer_modulo
    )
    
    # Split into multiple messages to avoid Twilio 1600 char limit
    # Message 1: Enrollment confirmation (short)
    mensaje_1 = f"""✅ {curso.emoji} ¡Inscripción exitosa!

Te inscribiste en: *{curso.nombre}*

📚 Módulos: {curso.modulos.count()}
⏱️ Duración: {curso.duracion_semanas} semanas"""

    # Message 2 & 3: Agent introductions (custom names from curso)
    from core.tutor_ia_modulo import generar_presentacion_agentes
    nombre_tutor = 'Formador'
    nombre_asistente = 'Compañero'
    msg_geronimo, msg_maria = generar_presentacion_agentes(
        curso.nombre,
        estudiante_nombre=estudiante.nombre or "Estudiante",
        nombre_tutor=nombre_tutor,
        nombre_asistente=nombre_asistente,
        curso=curso,
    )

    # Obtener video del primer módulo si existe
    video_url_modulo = obtener_video_url(primer_modulo)

    # Verificar archivos multimedia del primer módulo
    archivos_multimedia_1 = primer_modulo.archivos_multimedia.filter(activo=True)
    primera_media_url_1 = None
    extra_media_urls_1 = []
    archivos_msg_1 = ""

    if archivos_multimedia_1.exists():
        archivos_msg_1 = ""
        for idx, archivo in enumerate(archivos_multimedia_1):
            icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
            url = archivo.get_url_para_envio()
            if url:
                if not primera_media_url_1:
                    primera_media_url_1 = url
                    archivos_msg_1 += f"\n{icono} {archivo.titulo} (adjunto)"
                else:
                    extra_media_urls_1.append((url, archivo.titulo, icono))
                    archivos_msg_1 += f"\n{icono} {archivo.titulo} (adjunto)"
            else:
                archivos_msg_1 += f"\n{icono} {archivo.titulo}"

    # Si no hay archivos multimedia pero sí video_url, usarlo como primera media
    if not archivos_multimedia_1.exists() and video_url_modulo:
        primera_media_url_1 = video_url_modulo

    # Texto legacy del módulo (vacío si el módulo usa pasos internos)
    from core.module_steps import texto_legacy_whatsapp
    contenido = texto_legacy_whatsapp(primer_modulo)
    chunks = dividir_contenido_seguro(contenido, max_chars=1500)

    modulo_header = f"📖 *{primer_modulo.numero}. {primer_modulo.titulo}*\n\n"

    from core.module_steps import (
        modulo_usa_pasos,
        pasos_activos_qs,
        reset_progreso_pasos_modulo,
        entregar_bloque_secciones_desde_paso,
        log_y_mensaje_modo_pasos_sin_pasos,
    )

    from core.models import Cliente
    cliente_obj = None
    try:
        if estudiante and hasattr(estudiante, 'telefono'):
            cliente_obj = Cliente.objects.filter(estudiantes=estudiante).first()
    except Exception:
        pass
    usar_gamificacion = (cliente_obj.usar_gamificacion if cliente_obj else True) if cliente_obj else True
    msg_gamificacion = ""
    if usar_gamificacion:
        msg_gamificacion = (
            "*Nuestra experiencia de formación funciona a través de puntos*\n\n"
            "A medida que avance en el curso, tendrá retos que evaluar.\n\n"
            "¡Vamos a aprender y avanzar juntos!"
        )
    partes_intro = [mensaje_1]
    partes_intro.append(msg_geronimo)
    partes_intro.append(msg_maria)
    if msg_gamificacion:
        partes_intro.append(msg_gamificacion)
    partes_intro.append("*Comenzamos con el primer módulo de su curso...*")
    msg_intro = "\n\n".join(partes_intro)

    if modulo_usa_pasos(primer_modulo):
        if not pasos_activos_qs(primer_modulo).exists():
            _fb_ins = log_y_mensaje_modo_pasos_sin_pasos(
                primer_modulo, 'inscripcion_primer_modulo'
            )
            return '[MULTI_MSG]' + msg_intro + '[SEP]' + _fb_ins
        partes_bloque_mod0: list[str] = []
        reset_progreso_pasos_modulo(progreso, save=True)
        msg_pasos = entregar_bloque_secciones_desde_paso(progreso, primer_modulo, 1)
        cuerpo_p = msg_pasos[len('[MULTI_MSG]') :]
        partes_insc = [msg_intro] + partes_bloque_mod0 + [p for p in partir_sep(cuerpo_p) if p]
        logger.info(
            "📚 [pasos] inscripción con pasos internos | estudiante_id=%s curso_id=%s",
            estudiante.id,
            curso.id,
        )
        return '[MULTI_MSG]' + '[SEP]'.join(partes_insc)

    if chunks:
        mensaje_modulo = modulo_header + chunks[0]
        if len(chunks) > 1:
            remaining_chunks = chunks[1:]
            for chunk in remaining_chunks:
                if len(mensaje_modulo) + len(chunk) + 4 < 1500:
                    mensaje_modulo += "\n\n" + chunk
                else:
                    break
    else:
        desc = (primer_modulo.descripcion or '').strip()
        mensaje_modulo = modulo_header + (
            desc if desc else '📚 Continuamos con el material de esta unidad.'
        )

    # v1.9.8: labels de archivos no van en el texto (se envían como mensajes aparte)
    partes_insc = [msg_intro, mensaje_modulo]
    hay_media_insc = False
    if primera_media_url_1:
        partes_insc.append(parte_mensaje_con_media(primera_media_url_1))
        hay_media_insc = True
    for extra_url_1, _extra_titulo_1, _extra_icono_1 in extra_media_urls_1:
        partes_insc.append(parte_mensaje_con_media(extra_url_1))
        hay_media_insc = True
    if hay_media_insc:
        partes_insc.append("[DELAY:5]")
    hay_mas_modulos = curso.modulos.filter(numero__gt=primer_modulo.numero).exists()
    if hay_mas_modulos:
        partes_insc.append(
            "Tómese su tiempo para ver el material. Mientras usted aprende, aquí iremos organizando "
            "los recursos del siguiente nivel. En cuanto termine, solo responda *listo* para continuar."
        )

    from core.video_links import reescribir_videos_en_mensaje

    return reescribir_videos_en_mensaje(
        "[MULTI_MSG]" + "[SEP]".join(partes_insc),
        estudiante=estudiante,
        curso=curso,
        modulo=primer_modulo,
    )
