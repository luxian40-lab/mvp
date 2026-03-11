"""
Plantillas de respuesta para cada intent - Agro Colombiano.
Permite personalizar respuestas sin cambiar la lógica del webhook.
"""
from django.conf import settings
from django.utils import timezone
from urllib.parse import quote


def _barra_progreso(porcentaje: int) -> str:
    """Genera barra de progreso visual para WhatsApp."""
    llenas = int(porcentaje / 10)
    vacias = 10 - llenas
    return "▓" * llenas + "░" * vacias


def _generar_completado_final(estudiante, curso_id):
    """
    Genera el mensaje final de completado con certificado y resumen.
    Se usa tanto en el flujo normal como después de la pregunta de recuperación.
    """
    from .models import Curso, ProgresoEstudiante
    from .gamificacion import PerfilGamificacion, BadgeEstudiante
    
    try:
        curso = Curso.objects.get(id=curso_id)
        progreso = ProgresoEstudiante.objects.get(estudiante=estudiante, curso=curso)
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
    except Exception:
        return "🎓 *¡Felicitaciones! Has completado todo el curso.*\n\n🎓 Tu certificado se está generando."
    
    porcentaje = progreso.porcentaje_avance()
    
    badges_nuevos = BadgeEstudiante.objects.filter(
        estudiante=estudiante,
        badge__tipo='CURSO'
    ).order_by('-fecha_obtenido')[:2]
    
    barra = _barra_progreso(porcentaje)
    nivel_emoji = ["🌱","🌿","🍃","🌾","🌳","🌲","🎋","🌺","💎","👑"][min(perfil.nivel-1,9)]
    
    mensaje = f"""🎉 *¡CURSO COMPLETADO!*

💰 Total: *{perfil.puntos_totales} pts*
{nivel_emoji} Nivel {perfil.nivel}
{barra} {porcentaje}%"""
    
    if badges_nuevos.exists():
        mensaje += "\n\n🏅 *LOGROS DESBLOQUEADOS:*"
        for badge_est in badges_nuevos:
            mensaje += f"\n  {badge_est.badge.icono} {badge_est.badge.nombre}"
    
    mensaje += "\n\n🎓 *¡Felicitaciones! Has completado todo el curso.*"
    
    # Asistente: Resumen
    _cliente_fin = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
    nombre_asistente_fin = (
        (_cliente_fin.nombre_agente_asistente if _cliente_fin and hasattr(_cliente_fin, 'nombre_agente_asistente') and _cliente_fin.nombre_agente_asistente else '') or
        curso.nombre_agente_asistente or 'María'
    )
    msg_resumen = None
    try:
        from .tutor_ia_modulo import generar_resumen_curso_completo
        modulos_completados_qs = progreso.modulos_completados.all().order_by('modulo__numero')
        modulos_obj = [mc.modulo for mc in modulos_completados_qs]
        resumen_maria = generar_resumen_curso_completo(
            curso.nombre,
            modulos_obj,
            estudiante_nombre=estudiante.nombre or "Estudiante"
        )
        if resumen_maria:
            msg_resumen = f"� *{nombre_asistente_fin} — Resumen del Curso*\n\n{resumen_maria}"
    except Exception:
        pass
    
    # Certificado
    msg_cert_img = ""
    try:
        from .certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
        cert = crear_certificado_automatico(estudiante, curso)
        if cert and cert.archivo_imagen:
            cert_url = obtener_url_certificado_twilio(cert)
            if cert_url:
                msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
            else:
                from django.conf import settings as _s
                bucket = getattr(_s, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
                s3_key = str(cert.archivo_imagen.name)
                cert_url = f"https://{bucket}.s3.us-east-2.amazonaws.com/{s3_key}"
                msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
        elif cert and cert.archivo_pdf:
            cert_url = cert.archivo_pdf.url
            msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert_url}"
        else:
            msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
    except Exception:
        msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
    
    partes = [mensaje]
    if msg_cert_img:
        partes.append(msg_cert_img)
    if msg_resumen:
        partes.append(msg_resumen)
    return "[MULTI_MSG]" + "[SEP]".join(partes)


def dividir_contenido_seguro(contenido: str, max_chars: int = 1500) -> list:
    """
    Divide contenido en chunks seguros para Twilio (1600 char limit).
    Intenta mantener integridad de párrafos cuando es posible.
    
    Args:
        contenido: Texto a dividir
        max_chars: Máximo de caracteres por chunk (default 1500)
    
    Returns:
        Lista de strings, cada uno <= max_chars
    """
    if len(contenido) <= max_chars:
        return [contenido]
    
    chunks = []
    current_chunk = ""
    parrafos = contenido.split('\n\n')
    
    for parrafo in parrafos:
        # If single paragraph is too long, split it further
        if len(parrafo) > max_chars:
            # Save current chunk first
            if current_chunk:
                chunks.append(current_chunk.rstrip())
                current_chunk = ""
            
            # Split long paragraph by sentences (.)
            oraciones = parrafo.split('. ')
            for oracion in oraciones:
                if len(current_chunk) + len(oracion) + 2 < max_chars:
                    if current_chunk:
                        current_chunk += ". "
                    current_chunk += oracion
                else:
                    if current_chunk:
                        chunks.append(current_chunk.rstrip() + ".")
                    current_chunk = oracion
        else:
            # Normal paragraph
            if len(current_chunk) + len(parrafo) + 4 < max_chars:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += parrafo
            else:
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                current_chunk = parrafo
    
    # Add remaining content
    if current_chunk:
        chunks.append(current_chunk.rstrip())
    
    return [c for c in chunks if c]  # Remove empty chunks


def _generar_presigned_url_s3(key, expires_in=3600):
    """
    Genera una URL prefirmada de S3 para que Twilio pueda descargar el archivo.
    Resuelve error 63019 (Media download failed) cuando el bucket es privado.
    Incluye ResponseContentType según extensión del archivo.
    """
    try:
        import boto3
        from botocore.config import Config
        region = 'us-east-2'
        bucket = 'eki-produccion'
        s3_client = boto3.client('s3', config=Config(signature_version='s3v4', region_name=region))
        
        # Determinar ContentType según extensión para evitar error 63019
        params = {'Bucket': bucket, 'Key': key}
        ext = key.rsplit('.', 1)[-1].lower() if '.' in key else ''
        content_types = {
            'mp4': 'video/mp4', 'mov': 'video/quicktime', 'avi': 'video/x-msvideo',
            'mp3': 'audio/mpeg', 'ogg': 'audio/ogg', 'wav': 'audio/wav',
            'm4a': 'audio/mp4', 'aac': 'audio/aac', 'opus': 'audio/opus',
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'gif': 'image/gif', 'webp': 'image/webp',
            'pdf': 'application/pdf',
        }
        if ext in content_types:
            params['ResponseContentType'] = content_types[ext]
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params=params,
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ Error generando presigned URL: {e}")
        # Fallback: URL directa (puede fallar si bucket es privado)
        return f"https://eki-produccion.s3.us-east-2.amazonaws.com/{key}"


def obtener_video_url(leccion_o_modulo):
    """
    Genera URL del video accesible por Twilio.
    Usa presigned URLs de S3 para evitar error 63019 (Media download failed).
    
    Args:
        leccion_o_modulo: Instancia de Leccion o Modulo con video_archivo o video_url
        
    Returns:
        str: URL completa del video o None
    """
    # Prioridad 1: Archivo subido a S3 → presigned URL
    if hasattr(leccion_o_modulo, 'video_archivo') and leccion_o_modulo.video_archivo:
        key = leccion_o_modulo.video_archivo.name.lstrip('/')
        return _generar_presigned_url_s3(key)

    # Prioridad 2: URL externa (YouTube/Vimeo/directa)
    if hasattr(leccion_o_modulo, 'video_url') and leccion_o_modulo.video_url:
        url = leccion_o_modulo.video_url
        # Si es una URL directa de S3, convertirla a presigned
        if 'eki-produccion.s3' in url:
            from urllib.parse import unquote_plus
            key = unquote_plus(url.split('.amazonaws.com/')[-1].split('?')[0])
            return _generar_presigned_url_s3(key)
        return url

    # Prioridad 3: Método personalizado del modelo
    if hasattr(leccion_o_modulo, 'get_video_url_publica'):
        url = leccion_o_modulo.get_video_url_publica()
        if url:
            # Si es S3, convertir a presigned
            if 'eki-produccion.s3' in url:
                from urllib.parse import unquote_plus
                key = unquote_plus(url.split('.amazonaws.com/')[-1].split('?')[0])
                return _generar_presigned_url_s3(key)
            return url

    return None


def get_response_for_intent(intent: str, nombre_usuario: str = "Estudiante", **kwargs) -> str:
    """
    LÓGICA SIMPLIFICADA PARA SANDBOX:
    - opcion_1: siempre = progreso
    - opcion_2: siempre = ayuda 
    - opcion_3: siempre = menú principal
    - opcion_numerica (4-9): inscribir curso (sin ambigüedad)
    
    Retorna una respuesta templada según el intent.
    
    Args:
        intent: categoría detectada (saludo, progreso, tareas, ayuda, etc.)
        nombre_usuario: nombre del estudiante (para personalizar)
        kwargs: datos adicionales (progreso, siguiente_tarea, etc.)
    
    Returns:
        mensaje: respuesta en formato texto
    """
    
    # Saludos
    if intent == 'saludo':
        return f"""🌱 Hola {nombre_usuario}, bienvenido a eki

🚜 *Tu plataforma de soluciones educativas*

Aprende y mejora tus conocimientos con nosotros.


*¿Qué deseas hacer?*

1️⃣ Ver mi progreso
2️⃣ Explorar cursos
3️⃣ Ayuda y soporte

📝 Escribe el número (1, 2 o 3)"""
    
    # Cambiar nombre
    if intent == 'cambiar_nombre':
        return """Para cambiar tu nombre, escribe:

Mi nombre es [Tu Nombre]

Ejemplo:
- Mi nombre es Juan Pérez
- Mi nombre es María González"""
    
    # Confirmar cambio de nombre
    if intent == 'confirmar_cambio_nombre':
        nuevo_nombre = kwargs.get('nuevo_nombre', 'Usuario')
        return f"""✅ Listo, ahora te llamaré {nuevo_nombre}.

¿Quieres continuar?
Escribe "continuar", "ver cursos" o "mi progreso"."""
    
    # ========== OPCIONES NUMÉRICAS (SIMPLIFICADAS) ==========
    
    # Opción 1: SIEMPRE = Ver mi progreso
    if intent == 'opcion_1':
        from .models import ProgresoEstudiante
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        # Obtener o crear perfil de gamificación
        from .gamificacion import PerfilGamificacion, BadgeEstudiante
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        
        progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)
        
        if not progresos.exists():
            return f"""📊 TU PROGRESO

👋 Hola {estudiante.nombre}, aún no tienes un curso asignado.

Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""
        
        respuesta = "📊 TU PROGRESO DE APRENDIZAJE\n\n"
        
        # Mostrar gamificación
        nivel_index = min(perfil.nivel - 1, 9)  # Proteger índice
        nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][nivel_index]
        respuesta += f"🎮 {nivel_emoji} Nivel {perfil.nivel} | ⭐ {perfil.puntos_totales} puntos"
        
        # Mostrar racha si está activa
        if perfil.racha_dias_actual > 0:
            fuego = "🔥" * min(perfil.racha_dias_actual, 5)
            respuesta += f" | {fuego} Racha: módulo {perfil.racha_dias_actual}"
        
        respuesta += "\n"
        
        # Barra de progreso del nivel
        porcentaje_nivel = perfil.porcentaje_nivel()
        barras_llenas = int(porcentaje_nivel / 10)
        barra = "█" * barras_llenas + "░" * (10 - barras_llenas)
        respuesta += f"[{barra}] {porcentaje_nivel}% al nivel {perfil.nivel + 1}\n\n"
        
        # Badges obtenidos
        badges = BadgeEstudiante.objects.filter(estudiante=estudiante).select_related('badge').order_by('-fecha_obtenido')[:3]
        if badges.exists():
            respuesta += "🏆 Últimos logros: "
            respuesta += " ".join([f"{b.badge.icono}" for b in badges])
            respuesta += f" ({BadgeEstudiante.objects.filter(estudiante=estudiante).count()} total)\n\n"
        
        respuesta += "📚 TUS CURSOS:\n\n"
        
        for prog in progresos:
            porcentaje = prog.porcentaje_avance()
            estado = "✅ Completo" if prog.completado else f"⏳ En progreso"
            
            respuesta += f"{prog.curso.emoji} {prog.curso.nombre}\n"
            respuesta += f"   Avance: {porcentaje}% {estado}\n"
            
            if not prog.completado and prog.modulo_actual:
                respuesta += f"   📖 Módulo actual: {prog.modulo_actual.numero} - {prog.modulo_actual.titulo}\n"
            
            respuesta += "\n"
        
        respuesta += "Escribe *CONTINUAR* para seguir tu lección\n"
        respuesta += "O escribe *MENÚ* para volver al inicio"
        return respuesta
    
    # Opción 2: SIEMPRE = Ver cursos disponibles
    if intent == 'opcion_2':
        from .models import Curso, Estudiante
        cursos_activos = Curso.objects.filter(activo=True).order_by('orden')
        
        if not cursos_activos.exists():
            return "No hay cursos disponibles en este momento. ⚠️"
        
        respuesta = "📚 *CURSOS DISPONIBLES EN eki*\n\n"
        
        for idx, curso in enumerate(cursos_activos, 1):
            respuesta += f"{idx}. {curso.emoji} *{curso.nombre}*\n"
            respuesta += f"   📅 {curso.duracion_semanas} semanas | 📖 {curso.modulos.count()} módulos\n\n"
        
        respuesta += "Para inscribirte en un curso:\n"
        respuesta += "👉 Escribe el *número* (ej: *1* o *2*)\n\n"
        respuesta += "También puedes escribir *MENÚ* para volver"
        
        # Configurar estado para interceptar la selección numérica
        estudiante_id = kwargs.get('estudiante_id')
        if estudiante_id:
            try:
                est = Estudiante.objects.get(id=estudiante_id)
                est.estado_onboarding = 'esperando_seleccion_curso'
                est.save()
            except Estudiante.DoesNotExist:
                pass
        
        return respuesta
    
    # Opción 3: SIEMPRE = Ayuda/Soporte
    if intent == 'opcion_3':
        return f"""🆘 ¿NECESITAS AYUDA, {nombre_usuario}?

Estoy aquí para apoyarte con tu aprendizaje.

Puedes preguntarme:
💬 Dudas sobre cultivo de café
📚 Información de los cursos
📖 Cómo usar la plataforma

Ejemplos:
• "¿Cómo combato la roya del café?"
• "¿Qué sistema de riego es mejor?"
• "Ver mis cursos"
• "Continuar con mi lección"

También puedes:
• Escribir "menú" para volver al inicio
• Escribir "continuar" para seguir tu curso
• Escribir "progreso" para ver tu avance

✍️ ¿En qué te puedo ayudar?"""
    
    # Opción numérica genérica (4-9): Por defecto = Inscribir curso
    # El contexto en message_handler determina si es curso, módulo, etc.
    if intent == 'opcion_numerica':
        # El mensaje_handler ya determinó el contexto
        # Aquí solo manejamos el caso por defecto: inscribir curso
        return _manejar_inscribir_curso(kwargs.get('estudiante_id'), kwargs.get('mensaje_original', ''))
    
    # Progreso (sin pasar por menú) - Redirigir a opcion_1
    if intent == 'progreso':
        return get_response_for_intent('opcion_1', nombre_usuario, kwargs)
    
    # Tareas/Cursos (sin pasar por menú) - Redirigir a ver_cursos
    if intent == 'tareas':
        return get_response_for_intent('ver_cursos', nombre_usuario, **kwargs)
    
    # Ver ranking de gamificación
    if intent == 'ver_ranking':
        from .gamificacion import PerfilGamificacion, BadgeEstudiante
        from django.db.models import Count
        
        # Top 5 por puntos
        top_puntos = PerfilGamificacion.objects.select_related('estudiante').order_by('-puntos_totales')[:5]
        
        # Top 5 por racha actual
        top_racha = PerfilGamificacion.objects.select_related('estudiante').filter(racha_dias_actual__gt=0).order_by('-racha_dias_actual')[:5]
        
        # Estadísticas del estudiante actual
        estudiante_id = kwargs.get('estudiante_id')
        mi_perfil = None
        mi_posicion = None
        
        if estudiante_id:
            from .models import Estudiante
            estudiante = Estudiante.objects.get(id=estudiante_id)
            mi_perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
            
            # Calcular posición
            mejores = PerfilGamificacion.objects.filter(puntos_totales__gt=mi_perfil.puntos_totales).count()
            mi_posicion = mejores + 1
        
        respuesta = "🏆 RANKING DE ESTUDIANTES eki\n\n"
        respuesta += "📊 TOP 5 POR PUNTOS:\n"
        
        for idx, perfil in enumerate(top_puntos, 1):
            nivel_index = min(perfil.nivel - 1, 9)  # Proteger índice
            nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][nivel_index]
            medalla = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][idx - 1]
            respuesta += f"{medalla} {perfil.estudiante.nombre}\n"
            respuesta += f"   {nivel_emoji} Nivel {perfil.nivel} | ⭐ {perfil.puntos_totales} pts\n"
        
        if top_racha.exists():
            respuesta += "\n🔥 TOP 5 POR RACHA:\n"
            for idx, perfil in enumerate(top_racha, 1):
                fuego = "🔥" * min(perfil.racha_dias_actual, 3)
                respuesta += f"{idx}. {perfil.estudiante.nombre}\n"
                respuesta += f"   {fuego} Racha: módulo {perfil.racha_dias_actual}\n"
        
        if mi_perfil:
            respuesta += f"📍 TU POSICIÓN: #{mi_posicion}\n"
            respuesta += f"⭐ {mi_perfil.puntos_totales} puntos | Nivel {mi_perfil.nivel}\n"
            
            if mi_perfil.racha_dias_actual > 0:
                fuego = "🔥" * min(mi_perfil.racha_dias_actual, 3)
                respuesta += f"{fuego} Racha: módulo {mi_perfil.racha_dias_actual}\n"
        
        respuesta += "\n✨ Completa cursos y módulos para subir en el ranking!"
        
        return respuesta
    
    # Ayuda (sin pasar por menú) — doble "ayuda" crea ticket de soporte
    if intent == 'ayuda':
        estudiante_id = kwargs.get('estudiante_id')
        if estudiante_id:
            try:
                from .models import Estudiante, SolicitudSoporte
                est = Estudiante.objects.get(id=estudiante_id)
                ctx = est.contexto_temporal or {}
                conteo_ayuda = ctx.get('conteo_ayuda', 0) + 1
                
                if conteo_ayuda >= 2:
                    # Segunda vez pidiendo ayuda → crear ticket de soporte
                    solicitud = SolicitudSoporte.objects.create(
                        estudiante=est,
                        mensaje_original=kwargs.get('mensaje_original', 'ayuda x2'),
                        keyword_usada='ayuda (doble)',
                        prioridad='media'
                    )
                    # Limpiar conteo
                    ctx.pop('conteo_ayuda', None)
                    est.contexto_temporal = ctx if ctx else None
                    est.save()
                    
                    return f"""🆘 *Ticket de Soporte Creado*

Hola {nombre_usuario}, vemos que necesitas más ayuda.

📝 *Ticket #{solicitud.id}* registrado correctamente.
📧 Nuestro equipo ha sido notificado.

🕐 *Tiempo de respuesta:* menos de 24 horas.

Mientras tanto puedes seguir usando la plataforma normalmente.

Escribe *"menú"* para volver al inicio."""
                else:
                    # Primera vez → guardar conteo y mostrar ayuda normal
                    ctx['conteo_ayuda'] = conteo_ayuda
                    est.contexto_temporal = ctx
                    est.save()
            except Exception:
                pass
        
        return """☕ AYUDA - CURSOS DE CAFÉ eki

📋 COMANDOS PRINCIPALES:

• "ver cursos" - Ver cursos disponibles
• "2" - Inscribirte en un curso
• "continuar" - Seguir tu curso actual
• "progreso" o "1" - Ver tu avance
• "menú" - Volver al inicio

🎮 GAMIFICACIÓN:
⭐ Ganas puntos al completar módulos
🏆 Desbloqueas badges por logros
📈 Subes de nivel
🔥 Mantén tu racha por módulos

💬 PREGUNTAS:
También puedes preguntarme sobre café:
• "¿Cómo hacer análisis de suelos?"
• "¿Qué sistema de riego usar?"
• "¿Cómo controlar la roya?"

🆘 _Si necesitas hablar con soporte, escribe *"ayuda"* otra vez._
✍️ Escribe "menú" para volver al inicio."""
    
    # ========== SISTEMA DE CURSOS ==========
    
    # Número inválido (detectado por usuario)
    if intent == 'numero_invalido':
        return """❌ Número inválido.

Las opciones del menú son:

1️⃣ Ver mi progreso
2️⃣ Ver cursos de café
3️⃣ Ayuda y soporte

Escribe solo el número: 1, 2 o 3

O escribe "menú" para ver todas las opciones."""
    
    # Ver cursos disponibles
    if intent == 'ver_cursos':
        from .models import Curso
        cursos_activos = Curso.objects.filter(activo=True).order_by('orden')
        
        if not cursos_activos.exists():
            return "No hay cursos disponibles en este momento. ⚠️"
        
        respuesta = "📚 CURSOS DISPONIBLES EN eki\n\n"
        
        for idx, curso in enumerate(cursos_activos, 1):
            respuesta += f"{idx}️⃣ {curso.emoji} *{curso.nombre}*\n"
            respuesta += f"   📅 {curso.duracion_semanas} semanas | 📖 {curso.modulos.count()} módulos\n\n"
        
        respuesta += "👉 *Escribe el número* del curso que quieres tomar"
        return respuesta
    
    # Inscribirse en curso
    if intent == 'inscribir_curso':
        from .models import Curso, ProgresoEstudiante, Estudiante
        import re
        
        mensaje_original = kwargs.get('mensaje_original', '').strip()
        estudiante_id = kwargs.get('estudiante_id')
        
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        try:
            estudiante = Estudiante.objects.get(id=estudiante_id)
        except Estudiante.DoesNotExist:
            return "❌ Error: No se encontró tu perfil de estudiante."
        
        curso = None
        
        # Detectar número del curso
        match = re.search(r'\d+', mensaje_original)
        if match:
            numero_curso = int(match.group())
            cursos_activos = list(Curso.objects.filter(activo=True).order_by('orden'))
            
            if not cursos_activos:
                return "❌ No hay cursos disponibles en este momento."
            
            if 1 <= numero_curso <= len(cursos_activos):
                curso = cursos_activos[numero_curso - 1]
            else:
                return f"❌ Número inválido. Tenemos {len(cursos_activos)} cursos disponibles.\n\nEscribe \"ver cursos\" para verlos."
        
        if not curso:
            return """❌ No encontré ese curso.\n\nEscribe "ver cursos" para ver las opciones disponibles."""
        
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
        from .tutor_ia_modulo import generar_presentacion_agentes
        nombre_tutor = curso.nombre_agente_tutor or 'Gerónimo'
        nombre_asistente = curso.nombre_agente_asistente or 'María'
        msg_geronimo, msg_maria = generar_presentacion_agentes(
            curso.nombre,
            estudiante_nombre=estudiante.nombre or "Estudiante",
            nombre_tutor=nombre_tutor,
            nombre_asistente=nombre_asistente,
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

        # Divide module content into safe chunks
        contenido = primer_modulo.contenido
        chunks = dividir_contenido_seguro(contenido, max_chars=1500)
        
        # Build header for module
        modulo_header = f"📖 *{primer_modulo.numero}. {primer_modulo.titulo}*\n\n"
        
        # Combine header with first chunk
        if chunks:
            mensaje_modulo = modulo_header + chunks[0]
            
            # If there are more chunks, combine them
            if len(chunks) > 1:
                remaining_chunks = chunks[1:]
                for chunk in remaining_chunks:
                    if len(mensaje_modulo) + len(chunk) + 4 < 1500:
                        mensaje_modulo += "\n\n" + chunk
                    else:
                        break
            
            # v1.9.8: No mostrar labels de archivos en el texto del módulo (se envían como mensajes separados)
            
            # v1.9.6: Orden correcto: inscripción → gamificación → agentes → "Comenzamos..." → módulo texto → video(s) → "escribe listo"
            # Explicación de gamificación
            from .models import Cliente
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
                    "🎮 *Nuestro sistema funciona como un video juego*\n\n"
                    "A medida que completes los módulos, ganarás:\n"
                    "💰 *Puntos* por cada módulo completado\n"
                    "🏅 *Niveles* que subirás automáticamente\n"
                    "🔥 *Rachas* por módulos consecutivos\n\n"
                    "¡Vamos a aprender y avanzar juntos! 💪"
                )
            
            # Construir intro: inscripción + gamificación + agentes + "Comenzamos..."
            partes_intro = [mensaje_1]
            if msg_gamificacion:
                partes_intro.append(msg_gamificacion)
            partes_intro.append(msg_geronimo)
            partes_intro.append(msg_maria)
            partes_intro.append("📚 *Comenzamos con el primer módulo de tu curso...* 👇")
            msg_intro = "\n\n".join(partes_intro)
            
            partes_insc = [msg_intro, mensaje_modulo]
            hay_media_insc = False
            if primera_media_url_1:
                partes_insc.append(f"[MEDIA:{primera_media_url_1}]")
                hay_media_insc = True
            for extra_url_1, extra_titulo_1, extra_icono_1 in extra_media_urls_1:
                partes_insc.append(f"[MEDIA:{extra_url_1}]")
                hay_media_insc = True
            if hay_media_insc:
                # [DELAY:5] para que WhatsApp entregue videos antes de texto
                partes_insc.append("[DELAY:5]")
            # Mensaje "listo" solo si hay más módulos después del primero
            hay_mas_modulos = curso.modulos.filter(numero__gt=primer_modulo.numero).exists()
            if hay_mas_modulos:
                partes_insc.append("Cuando termines de revisar el contenido, escribe *listo* para continuar con el siguiente modulo")
            
            return "[MULTI_MSG]" + "[SEP]".join(partes_insc)
        else:
            # Fallback (shouldn't happen)
            return f"""✅ {curso.emoji} ¡Inscripción exitosa!

Te inscribiste en: {curso.nombre}

Escribe "continuar" para empezar el primer módulo."""
    
    # Continuar con lección
    if intent == 'continuar_leccion':
        from .models import ProgresoEstudiante, ModuloCompletado
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        
        # ═══════════════════════════════════════════════════════════════
        # ANTI-DUPLICADO v1.9.1: Prevenir que dos workers entreguen
        # el mismo módulo simultáneamente (race condition con Gunicorn)
        # ═══════════════════════════════════════════════════════════════
        import time as _time
        from django.db import transaction
        
        _dedup_ok = False
        try:
            with transaction.atomic():
                est_lock = Estudiante.objects.select_for_update().get(id=estudiante_id)
                ctx_lock = est_lock.contexto_temporal or {}
                last_leccion = ctx_lock.get('_ts_leccion', 0)
                now_ts = _time.time()
                
                if now_ts - last_leccion < 45:
                    print(f"⏳ [ANTI-DUPLICADO] continuar_leccion bloqueado: última entrega hace {now_ts - last_leccion:.1f}s", flush=True)
                else:
                    ctx_lock['_ts_leccion'] = now_ts
                    est_lock.contexto_temporal = ctx_lock
                    est_lock.save(update_fields=['contexto_temporal'])
                    _dedup_ok = True
        except Exception as e:
            print(f"⚠️ [ANTI-DUPLICADO] Error en lock: {e}", flush=True)
            _dedup_ok = True  # En caso de error, permitir (fail-open)
        
        if not _dedup_ok:
            return "⏳ Tu módulo se está cargando, espera unos segundos..."
        # ═══════════════════════════════════════════════════════════════
        
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
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
            return """Aún no tienes un curso asignado. 📚

Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""
        
        # Si tiene MÚLTIPLES cursos activos, preguntar cuál continuar
        if progresos_activos.count() > 1:
            respuesta = "📚 Tienes varios cursos activos:\n\n"
            for idx, prog in enumerate(progresos_activos, 1):
                porcentaje = prog.porcentaje_avance()
                respuesta += f"{idx}️⃣ {prog.curso.emoji} {prog.curso.nombre}\n"
                respuesta += f"   📊 Avance: {porcentaje}%\n"
                if prog.modulo_actual:
                    respuesta += f"   📖 Módulo actual: {prog.modulo_actual.numero} - {prog.modulo_actual.titulo}\n"
                respuesta += "\n"
            
            respuesta += "Escribe el número del curso al que quieres continuar.\n"
            respuesta += "Ejemplo: \"1\" o \"2\" o \"3\""
            
            # Guardar estado para que views.py intercepte la respuesta numérica
            estudiante.estado_onboarding = 'esperando_seleccion_curso'
            estudiante.contexto_temporal = {'tipo': 'seleccion_curso'}
            estudiante.save()
            
            return respuesta
        
        # Si solo tiene UN curso activo, continuar directamente
        progreso = progresos_activos.first()
        
        # NOTA: Esta validación es redundante pero se mantiene por seguridad
        # first() retorna None si no hay resultados, no genera excepción
        if not progreso:
            return """Aún no tienes un curso asignado. 📚

Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""
        
        # Obtener módulo actual
        modulo_actual = progreso.modulo_actual
        if not modulo_actual:
            # Si no hay módulo actual, tomar el primero
            modulo_actual = progreso.curso.modulos.order_by('numero').first()
            if not modulo_actual:
                return f"❌ El curso {progreso.curso.nombre} no tiene módulos configurados. Contacta a soporte."
            progreso.modulo_actual = modulo_actual
            progreso.save()
        
        # Si escribieron "listo" o "siguiente", significa que terminaron el módulo actual
        # Completarlo y avanzar al siguiente
        palabras_completar = ['listo', 'siguiente', 'ok', 'dale', 'avanzar', 'sigue']
        if any(palabra in mensaje_original for palabra in palabras_completar):
            # PRIORIDAD: Verificar si el módulo tiene pregunta de validación
            from .pregunta_handler import tiene_pregunta_modulo, obtener_pregunta_modulo, formatear_pregunta, guardar_contexto_pregunta
            
            if tiene_pregunta_modulo(modulo_actual):
                # Verificar si ya respondió esta pregunta
                ya_respondio = ModuloCompletado.objects.filter(
                    progreso=progreso,
                    modulo=modulo_actual
                ).exists()
                
                if not ya_respondio:
                    # Mostrar pregunta
                    pregunta = obtener_pregunta_modulo(modulo_actual)
                    if pregunta:
                        guardar_contexto_pregunta(estudiante, modulo_actual, pregunta, progreso)
                        return formatear_pregunta(pregunta)
            
            # Completar módulo y avanzar (el tutor IA se envía como mensaje separado después)
            from .gamificacion import PerfilGamificacion
            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
            nivel_antes = perfil.nivel
            
            if not tiene_pregunta_modulo(modulo_actual):
                ModuloCompletado.objects.get_or_create(
                    progreso=progreso,
                    modulo=modulo_actual
                )
            
            perfil.refresh_from_db()
            subio_nivel = perfil.nivel > nivel_antes
            
            siguiente_modulo = progreso.curso.modulos.filter(
                numero__gt=modulo_actual.numero
            ).order_by('numero').first()
            
            if siguiente_modulo:
                progreso.modulo_actual = siguiente_modulo
                progreso.save()
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

                # Mensaje de gamificación profesional
                barra = _barra_progreso(porcentaje)
                nivel_emoji = ["🌱","🌿","🍃","🌾","🌳","🌲","🎋","🌺","💎","👑"][min(perfil.nivel-1,9)]
                racha_txt = ""
                if hasattr(perfil, 'racha_dias_actual') and perfil.racha_dias_actual > 0:
                    racha_txt = f"\n🔥 Racha: módulo {perfil.racha_dias_actual}"
                
                # Mensaje 1: Completado + gamificación
                from .gamificacion_actions import PUNTOS_CONFIG
                _pts_modulo = PUNTOS_CONFIG.get('modulo_completado', 10)
                msg_completado = f"""
✅ *Módulo {modulo_actual.numero} completado*

💰 *+{_pts_modulo} puntos*  →  Total: *{perfil.puntos_totales} pts*
{nivel_emoji} Nivel {perfil.nivel}{racha_txt}
{barra} {porcentaje}%"""
                
                if subio_nivel:
                    msg_completado += f"\n\n🎉 *¡SUBISTE DE NIVEL!* {nivel_emoji} Nivel {perfil.nivel}"
                
                # Mensaje 2: Siguiente módulo CON multimedia embebida
                contenido_mod = siguiente_modulo.contenido or ''
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
                
                # Agentes: Tutor (impares) / Asistente (módulo 4)
                # Get agent names: Cliente > Curso > defaults
                _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                nombre_tutor = (
                    (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                    progreso.curso.nombre_agente_tutor or 'Gerónimo'
                )
                nombre_asistente = (
                    (_cliente.nombre_agente_asistente if _cliente and hasattr(_cliente, 'nombre_agente_asistente') and _cliente.nombre_agente_asistente else '') or
                    progreso.curso.nombre_agente_asistente or 'María'
                )
                tutor_msg = None
                if modulo_actual.numero >= 1 and modulo_actual.numero % 2 == 1:
                    try:
                        from .tutor_ia_modulo import generar_enseñanza_modulo
                        enseñanza = generar_enseñanza_modulo(
                            modulo_actual,
                            estudiante_nombre=estudiante.nombre or "Estudiante",
                            preguntas_ejemplo=progreso.curso.preguntas_ejemplo_ia or ""
                        )
                        if enseñanza:
                            _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                            estudiante.contexto_temporal = {
                                'tipo': 'tutor_ia_modulo',
                                'modulo_id': modulo_actual.id,
                                'pregunta_tutor': enseñanza,
                                'progreso_id': progreso.id,
                                'intentos_tutor': 0,
                                '_ts_leccion': _prev_ts,
                            }
                            estudiante.estado_onboarding = 'esperando_respuesta_tutor_ia'
                            estudiante.save()
                            tutor_msg = f"🤓 *{nombre_tutor}*\n\n{enseñanza}\n\n💬 _Escríbeme o envía un audio con tu respuesta. Si decides seguir con el módulo, en el audio o texto di *continuar*_"
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"⚠️ {nombre_tutor} falló: {e}")
                
                # Asistente: revisión de progreso SOLO en módulo 4
                maria_msg = None
                if modulo_actual.numero == 4:
                    try:
                        from .tutor_ia_modulo import generar_revision_progreso
                        from .models import Modulo
                        modulos_completados_qs = progreso.modulos_completados.all().order_by('modulo__numero')
                        modulos_obj = [mc.modulo for mc in modulos_completados_qs]
                        revision = generar_revision_progreso(
                            modulo_actual,
                            modulos_obj,
                            progreso.curso.nombre,
                            estudiante_nombre=estudiante.nombre or "Estudiante"
                        )
                        if revision:
                            maria_msg = f"📚 *{nombre_asistente} — Tu Asistente*\n\n{revision}\n\n💬 _Escríbeme o envía un audio con tu respuesta. Si decides seguir con el módulo, en el audio o texto di *continuar*_"
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"⚠️ {nombre_asistente} falló: {e}")
                
                # Estado: Tutor tiene prioridad para interacción
                if tutor_msg:
                    # Ya configurado arriba
                    pass
                elif maria_msg:
                    modulos_info = ", ".join([m.titulo for m in modulos_obj])
                    _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                    estudiante.contexto_temporal = {
                        'tipo': 'revision_progreso',
                        'modulo_id': modulo_actual.id,
                        'pregunta_tutor': revision,
                        'progreso_id': progreso.id,
                        'modulos_info': modulos_info,
                        'intentos_tutor': 0,
                        '_ts_leccion': _prev_ts,
                    }
                    estudiante.estado_onboarding = 'esperando_respuesta_progreso'
                    estudiante.save()
                
                # Construir multi-mensaje: gamificación → módulo texto → video(s) → [DELAY] → agente → "escribe listo"
                partes = [msg_completado, msg_modulo]
                # Videos/media como mensajes separados DESPUÉS del texto
                hay_media = False
                if primera_media_url:
                    partes.append(f"[MEDIA:{primera_media_url}]")
                    hay_media = True
                for extra_url, extra_titulo, extra_icono in extra_media_urls:
                    partes.append(f"[MEDIA:{extra_url}]")
                    hay_media = True
                # [DELAY:5] después de videos para que WhatsApp los entregue antes del texto siguiente
                hay_texto_post = tutor_msg or maria_msg
                es_ultimo_modulo = not progreso.curso.modulos.filter(numero__gt=siguiente_modulo.numero).exists()
                if not hay_texto_post and not es_ultimo_modulo:
                    hay_texto_post = True  # habrá "escribe listo"
                if hay_media and hay_texto_post:
                    partes.append("[DELAY:5]")
                # Agentes van DESPUÉS de los videos
                if tutor_msg:
                    partes.append(tutor_msg)
                if maria_msg:
                    partes.append(maria_msg)
                # "Escribe listo" AL FINAL — solo si NO hay agentes (agentes ya dicen "continuar") y NO es último módulo
                if not tutor_msg and not maria_msg and not es_ultimo_modulo:
                    partes.append("Cuando termines de revisar el contenido, escribe *listo* para continuar con el siguiente modulo")
                return "[MULTI_MSG]" + "[SEP]".join(partes)
            
            else:
                # Completó todos los módulos
                # Marcar curso como completado
                progreso.completado = True
                progreso.fecha_completado = timezone.now()
                progreso.save()
                
                # Refrescar perfil para ver badges obtenidos
                perfil.refresh_from_db()
                
                porcentaje = progreso.porcentaje_avance()
                
                # === PREGUNTA DE RECUPERACIÓN si <70 puntos y gamificación activa ===
                if progreso.curso.usar_gamificacion and perfil.puntos_totales < 70:
                    try:
                        from .tutor_ia_modulo import generar_pregunta_recuperacion
                        modulos_completados_qs = progreso.modulos_completados.all().order_by('modulo__numero')
                        modulos_obj = [mc.modulo for mc in modulos_completados_qs]
                        pregunta_data = generar_pregunta_recuperacion(
                            progreso.curso,
                            modulos_obj,
                            estudiante_nombre=estudiante.nombre or "Estudiante",
                            preguntas_ejemplo=progreso.curso.preguntas_ejemplo_ia or ""
                        )
                        if pregunta_data:
                            # Guardar estado para esperar respuesta
                            _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                            estudiante.contexto_temporal = {
                                'tipo': 'pregunta_recuperacion',
                                'curso_id': progreso.curso.id,
                                'progreso_id': progreso.id,
                                'pregunta_data': pregunta_data,
                                '_ts_leccion': _prev_ts,
                            }
                            estudiante.estado_onboarding = 'esperando_respuesta_recuperacion'
                            estudiante.save()
                            
                            # Construir mensaje de pregunta
                            opciones_txt = ""
                            for letra, opcion in pregunta_data['opciones'].items():
                                opciones_txt += f"\n*{letra})* {opcion}"
                            
                            from .gamificacion_actions import PUNTOS_CONFIG
                            _pts_recup = PUNTOS_CONFIG.get('pregunta_recuperacion', 15)
                            msg_recuperacion = (
                                f"🎉 *¡Completaste todos los módulos del curso!*\n\n"
                                f"Pero antes de tu certificado, tienes una oportunidad de ganar *+{_pts_recup} puntos extra* 🏆\n\n"
                                f"🤓 *Pregunta de recuperación:*\n\n"
                                f"{pregunta_data['pregunta']}\n"
                                f"{opciones_txt}\n\n"
                                f"📝 Responde con la letra (A, B, C o D)"
                            )
                            return msg_recuperacion
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"⚠️ Pregunta recuperación falló: {e}")
                        # Si falla, continuar con flujo normal de completado
                
                # Buscar badges obtenidos por este curso
                from .gamificacion import BadgeEstudiante
                badges_nuevos = BadgeEstudiante.objects.filter(
                    estudiante=estudiante,
                    badge__tipo='CURSO'
                ).order_by('-fecha_obtenido')[:2]
                
                barra = _barra_progreso(porcentaje)
                nivel_emoji = ["🌱","🌿","🍃","🌾","🌳","🌲","🎋","🌺","💎","👑"][min(perfil.nivel-1,9)]
                
                from .gamificacion_actions import PUNTOS_CONFIG
                _pts_mod_c = PUNTOS_CONFIG.get('modulo_completado', 10)
                _pts_curso_c = PUNTOS_CONFIG.get('curso_completado', 15)
                _pts_total_c = _pts_mod_c + _pts_curso_c
                mensaje = f"""
🎉 *¡CURSO COMPLETADO!*

✅ *Módulo {modulo_actual.numero} completado*

💰 *+{_pts_total_c} puntos* ({_pts_mod_c} módulo + {_pts_curso_c} curso)
→ Total: *{perfil.puntos_totales} pts*
{nivel_emoji} Nivel {perfil.nivel}
{barra} {porcentaje}%"""
                
                # Mostrar badges obtenidos
                if badges_nuevos.exists():
                    mensaje += "\n\n🏅 *LOGROS DESBLOQUEADOS:*"
                    for badge_est in badges_nuevos:
                        mensaje += f"\n  {badge_est.badge.icono} {badge_est.badge.nombre}"
                
                # Si subió de nivel, celebrar!
                if subio_nivel:
                    nivel_index = min(perfil.nivel - 1, 9)
                    nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][nivel_index]
                    mensaje += f"\n\n✨ *¡SUBISTE A {nivel_emoji} NIVEL {perfil.nivel}!*"
                
                mensaje += "\n\n🎓 *¡Felicitaciones! Has completado todo el curso.*"
                
                # Asistente: Resumen completo del curso antes de certificado
                _cliente_fin = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                nombre_asistente_fin = (
                    (_cliente_fin.nombre_agente_asistente if _cliente_fin and hasattr(_cliente_fin, 'nombre_agente_asistente') and _cliente_fin.nombre_agente_asistente else '') or
                    progreso.curso.nombre_agente_asistente or 'María'
                )
                msg_resumen = None
                try:
                    from .tutor_ia_modulo import generar_resumen_curso_completo
                    modulos_completados_qs = progreso.modulos_completados.all().order_by('modulo__numero')
                    modulos_obj = [mc.modulo for mc in modulos_completados_qs]
                    resumen_maria = generar_resumen_curso_completo(
                        progreso.curso.nombre,
                        modulos_obj,
                        estudiante_nombre=estudiante.nombre or "Estudiante"
                    )
                    if resumen_maria:
                        msg_resumen = f"📚 *{nombre_asistente_fin} — Resumen del Curso*\n\n{resumen_maria}"
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"⚠️ {nombre_asistente_fin} resumen falló: {e}")
                
                # Imagen de certificado — usar URL pública directa (sin /media/ de Django)
                msg_cert_img = ""
                try:
                    from .certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
                    cert = crear_certificado_automatico(estudiante, progreso.curso)
                    if cert and cert.archivo_imagen:
                        cert_url = obtener_url_certificado_twilio(cert)
                        if cert_url:
                            msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                        else:
                            # Fallback: construir URL directa sin /media/
                            import os
                            from django.conf import settings as _s
                            bucket = getattr(_s, 'AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
                            s3_key = str(cert.archivo_imagen.name)
                            cert_url = f"https://{bucket}.s3.us-east-2.amazonaws.com/{s3_key}"
                            msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                    elif cert and cert.archivo_pdf:
                        cert_url = cert.archivo_pdf.url
                        msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert_url}"
                    else:
                        msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"⚠️ Certificado falló: {e}")
                    msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                
                partes = []
                partes.append(mensaje)
                partes.append(msg_cert_img)
                if msg_resumen:
                    partes.append(msg_resumen)
                return "[MULTI_MSG]" + "[SEP]".join(partes)
        
        # Si escribieron solo "continuar" (primera vez o retomando), mostrar el módulo actual
        else:
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
            es_ultimo_modulo_c = not progreso.curso.modulos.filter(numero__gt=modulo_actual.numero).exists()
            
            # Siempre usar multi-mensaje para garantizar orden: texto → video(s) → "escribe listo"
            partes_c = [respuesta]
            hay_media_c = False
            if primera_media_url_c:
                partes_c.append(f"[MEDIA:{primera_media_url_c}]")
                hay_media_c = True
            for extra_url_c, extra_titulo_c, extra_icono_c in extra_media_urls_c:
                partes_c.append(f"[MEDIA:{extra_url_c}]")
                hay_media_c = True
            if not es_ultimo_modulo_c:
                if hay_media_c:
                    partes_c.append("[DELAY:5]")
                partes_c.append("Cuando termines de revisar el contenido, escribe *listo* para continuar con el siguiente modulo")
            
            if len(partes_c) > 1:
                return "[MULTI_MSG]" + "[SEP]".join(partes_c)
            
            return respuesta
    
    # Ver mi progreso en cursos
    if intent == 'mi_progreso_cursos':
        from .models import ProgresoEstudiante
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)
        
        if not progresos.exists():
            return """Tu Progreso

No tienes cursos todavía. 📚

Escribe "ver cursos" para empezar."""
        
        respuesta = "TU PROGRESO DE APRENDIZAJE\n\n"
        
        for prog in progresos:
            porcentaje = prog.porcentaje_avance()
            estado = "Completo" if prog.completado else f"⏳ {porcentaje}%"
            
            respuesta += f"{prog.curso.emoji} {prog.curso.nombre}\n"
            respuesta += f"   {estado}\n"
            
            if not prog.completado and prog.modulo_actual:
                respuesta += f"   📖 Módulo actual: {prog.modulo_actual.numero}\n"
            
            respuesta += "\n"
        
        respuesta += "Escribe \"continuar\" para seguir aprendiendo."
        return respuesta
    
    # Iniciar examen
    if intent == 'iniciar_examen':
        from .models import ProgresoEstudiante, Examen
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        # Buscar progreso activo
        progreso = ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False
        ).first()
        
        if not progreso:
            return """Aún no tienes un curso asignado para tomar examen. 📚

Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""
        
        # Verificar que haya completado todos los módulos
        total_modulos = progreso.curso.modulos.count()
        modulos_completados = progreso.modulos_completados.count()
        
        if modulos_completados < total_modulos:
            return f"""⚠️ Aún no puedes tomar el examen.

Debes completar los {total_modulos} módulos primero.
Has completado: {modulos_completados}/{total_modulos}

Escribe "continuar" para seguir con tus lecciones."""
        
        # Obtener examen
        try:
            examen = progreso.curso.examen
        except:
            return "Este curso no tiene examen configurado todavía. ⚠️"
        
        # Iniciar examen (guardar en contexto)
        primera_pregunta = examen.preguntas.order_by('numero').first()
        
        respuesta = f"""{progreso.curso.emoji} EXAMEN FINAL

{examen.instrucciones}

📝 Total de preguntas: {examen.preguntas.count()}
Puntaje mínimo: {examen.puntaje_minimo}%

---

Pregunta 1:
{primera_pregunta.pregunta}

Responde con tu mejor explicación.
   (El tutor evaluará tu respuesta)"""
        
        return respuesta
    
    return f"Hola {nombre_usuario}, ¿cómo te puedo ayudar con tu aprendizaje agropecuario? 🌱"
