"""
Plantillas de respuesta para cada intent - Agro Colombiano.
Permite personalizar respuestas sin cambiar la lógica del webhook.
"""
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from urllib.parse import quote

from .helpers_examenes import evaluar_checkpoint_reto_ia


logger = logging.getLogger(__name__)

# Twilio exige body no vacío junto a media_url; nunca usar solo emoji (p. ej. 📹).
MENSAJE_CAPTION_SOLO_MEDIA = (
    'Aquí tiene el material del módulo. Revíselo con calma.'
)


def parte_mensaje_con_media(url: str, caption: str | None = None) -> str:
    """Bloque para [MULTI_MSG]: texto legible + marcador [MEDIA:…]."""
    cap = (caption or '').strip() or MENSAJE_CAPTION_SOLO_MEDIA
    u = (url or '').strip()
    if not u:
        return cap
    return f'{cap}\n\n[MEDIA:{u}]'


def _es_mensaje_listo_avance_curso(texto: str) -> bool:
    """Igual que en webhook: *listo*, Listo, LISTO cuentan como avance de lección."""
    t = (texto or '').strip().lower().replace('*', '').strip()
    return t == 'listo'


def partes_presentacion_agentes_curso(estudiante, curso) -> list:
    """
    Bloques de texto tutor + asistente (+ gamificación según cliente), sin prefijo [MULTI_MSG].
    Lista vacía si el curso no usa agentes IA.
    """
    if not getattr(curso, 'usar_agentes_ia', True):
        return []
    from .tutor_ia_modulo import generar_presentacion_agentes

    nombre_tutor = curso.nombre_agente_tutor or 'Gerónimo'
    nombre_asistente = curso.nombre_agente_asistente or 'María'
    msg_facilitador, msg_asistente = generar_presentacion_agentes(
        curso.nombre,
        estudiante_nombre=getattr(estudiante, 'nombre', None) or 'Estudiante',
        nombre_tutor=nombre_tutor,
        nombre_asistente=nombre_asistente,
    )
    partes = [msg_facilitador, msg_asistente]
    cliente_obj = getattr(estudiante, 'cliente', None)
    usar_gamificacion = (
        bool(getattr(cliente_obj, 'usar_gamificacion', True))
        if cliente_obj is not None
        else True
    )
    if usar_gamificacion:
        partes.append(
            '🎮 *Nuestra experiencia de formación funciona a través de puntos*\n\n'
            'A medida que avances en el curso, tendrás retos que evaluar.\n\n'
            '¡Vamos a aprender y avanzar juntos! 💪'
        )
    return partes


def _barra_progreso(porcentaje: int) -> str:
    """Genera barra de progreso visual para WhatsApp."""
    llenas = int(porcentaje / 10)
    vacias = 10 - llenas
    return "▓" * llenas + "░" * vacias


def _mensaje_bloqueo_drip(fecha_desbloqueo):
    from .drip_schedule import format_mensaje_bloqueo_drip
    return format_mensaje_bloqueo_drip(fecha_desbloqueo)


def _mensaje_pregunta_abierta_final(pregunta_texto):
    return (
        "📝 *Pregunta abierta final de la Facilitadora*\n\n"
        f"{pregunta_texto}\n\n"
        "✍️ Responde con tus propias palabras (texto o audio).\n"
        "Tu facilitadora calificará esta respuesta."
    )


def _cliente_en_ventana(cliente, campo_habilitar, campo_inicio, campo_fin):
    if not cliente:
        return True
    if not getattr(cliente, campo_habilitar, False):
        return False

    hoy = timezone.localdate()
    inicio = getattr(cliente, campo_inicio, None)
    fin = getattr(cliente, campo_fin, None)
    if inicio and hoy < inicio:
        return False
    if fin and hoy > fin:
        return False
    return True


def _cliente_habilita_pregunta_abierta_final(cliente):
    return _cliente_en_ventana(
        cliente,
        'habilitar_pregunta_abierta_final',
        'fecha_inicio_pregunta_abierta_final',
        'fecha_fin_pregunta_abierta_final',
    )


def _cliente_habilita_proximidad(cliente):
    return _cliente_en_ventana(
        cliente,
        'habilitar_gamificacion_proximidad',
        'fecha_inicio_gamificacion_proximidad',
        'fecha_fin_gamificacion_proximidad',
    )


def _generar_completado_final(estudiante, curso_id):
    """
    Genera el mensaje final de completado con certificado.
    v1.9.8g: Removed levels, badges, María resumen. Added post-cert cutoff.
    """
    from django.db.models import Q
    from .models import Curso, ProgresoEstudiante, AliadoEmpleabilidad, PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal
    from .gamificacion import PerfilGamificacion
    
    try:
        curso = Curso.objects.get(id=curso_id)
        progreso = ProgresoEstudiante.objects.get(estudiante=estudiante, curso=curso)
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
    except Exception:
        return "🎓 *¡Felicitaciones! Ha completado todo el curso.*\n\n🎓 Su certificado se está generando."
    
    porcentaje = progreso.porcentaje_avance()
    barra = _barra_progreso(porcentaje)

    # Pregunta abierta final configurable antes del cierre completo
    pregunta_abierta = None
    preguntas_abiertas = PreguntaAbiertaFinalCurso.objects.filter(
        curso=curso,
        activa=True
    ).order_by('orden', 'id')[:3]
    if preguntas_abiertas.exists():
        cliente_habilita = _cliente_habilita_pregunta_abierta_final(estudiante.cliente)
        curso_habilita = bool(getattr(curso, 'habilitar_pregunta_abierta_final', False))
        if not (cliente_habilita and curso_habilita):
            logger.info(
                "⚠️ [templates] Fallback pregunta abierta final por configuración | estudiante_id=%s | curso_id=%s | cliente_habilita=%s | curso_habilita=%s",
                estudiante.id,
                curso.id,
                cliente_habilita,
                curso_habilita,
            )
        for p in preguntas_abiertas:
            ya_respondio = RespuestaAbiertaFinal.objects.filter(
                pregunta=p,
                estudiante=estudiante
            ).exists()
            if not ya_respondio:
                pregunta_abierta = p
                break
    if pregunta_abierta:
            logger.info(
                "🧭 [templates] Pregunta abierta final seleccionada | estudiante_id=%s | curso_id=%s | pregunta_id=%s | orden=%s | texto=%s",
                estudiante.id,
                curso.id,
                pregunta_abierta.id,
                getattr(pregunta_abierta, 'orden', None),
                (pregunta_abierta.pregunta or '')[:180],
            )
            usar_gamificacion_final = bool(
                getattr(curso, 'usar_gamificacion', False) or
                (estudiante.cliente.usar_gamificacion if getattr(estudiante, 'cliente', None) else False)
            )

            if usar_gamificacion_final:
                nombre_tutor_final = curso.nombre_agente_tutor or 'Claudia'
                nombre_asist_final = curso.nombre_agente_asistente or 'Dario'
                modulos_all = list(curso.modulos.filter(numero__gte=4).order_by('numero'))
                if not modulos_all:
                    modulos_all = list(curso.modulos.all().order_by('numero'))
                modulos_final_range = "los módulos finales del curso"
                if len(modulos_all) >= 2:
                    modulos_final_range = f"los módulos {modulos_all[0].numero} a {modulos_all[-1].numero}"

                progreso.completado = True
                progreso.fecha_completado = timezone.now()
                progreso.fecha_ultimo_avance = timezone.now()
                progreso.save(update_fields=['completado', 'fecha_completado', 'fecha_ultimo_avance'])

                _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                estudiante.contexto_temporal = {
                    'tipo': 'asistente_dario',
                    'curso_activo_id': curso.id,
                    'curso_id': curso.id,
                    'modulo_id': getattr(progreso.modulo_actual, 'id', None),
                    'progreso_id': progreso.id,
                    'modulos_reto_ids': [m.id for m in modulos_all],
                    'preguntas_hechas': 0,
                    'es_reto_final': True,
                    'pregunta_abierta_final_id': pregunta_abierta.id,
                    '_ts_leccion': _prev_ts,
                }
                estudiante.estado_onboarding = 'esperando_respuesta_asistente'
                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

                return (
                    "[MULTI_MSG]"
                    "🎉 *¡Completaste todos los módulos del curso!*"
                    "[SEP]"
                    f"💬 *{nombre_asist_final}*\n\n"
                    f"Antes de tu certificado, {nombre_tutor_final} te planteará un reto final sobre {modulos_final_range}.\n\n"
                    "¿Tienes dudas antes del reto? Envíame tu pregunta (texto o audio).\n"
                    "Si no tienes dudas, escribe *listo* para pasar con la facilitadora."
                )

            progreso.completado = True
            progreso.fecha_completado = timezone.now()
            progreso.fecha_ultimo_avance = timezone.now()
            progreso.save(update_fields=['completado', 'fecha_completado', 'fecha_ultimo_avance'])
            estudiante.contexto_temporal = {
                'tipo': 'pregunta_abierta_final',
                'curso_id': curso.id,
                'progreso_id': progreso.id,
                'pregunta_abierta_final_id': pregunta_abierta.id,
            }
            estudiante.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
            estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
            return _mensaje_pregunta_abierta_final(pregunta_abierta.pregunta)
    
    mensaje = f"""🎉 *¡CURSO COMPLETADO!*

💰 Total: *{perfil.puntos_totales} pts*
{barra} {porcentaje}%

🎓 *¡Felicitaciones! Ha completado todo el curso.*"""
    
    # Certificado
    msg_cert_img = ""
    try:
        from .certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
        cert = crear_certificado_automatico(estudiante, curso)
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
            msg_cert_img = f"🎓 *¡Su certificado!*\n📄 Descárgalo aquí: {cert_url}"
        else:
            msg_cert_img = "🎓 Su certificado se está generando. Se lo enviaremos pronto."
    except Exception:
        msg_cert_img = "🎓 Su certificado se está generando. Se lo enviaremos pronto."
    
    # Post-certificate cutoff
    estudiante.estado_onboarding = 'curso_finalizado'
    ctx = estudiante.contexto_temporal or {}
    if not ctx.get('radar_empleabilidad_activo') and _cliente_habilita_proximidad(estudiante.cliente):
        hay_aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).filter(
            Q(cliente__isnull=True) | Q(cliente=estudiante.cliente)
        ).exists() if estudiante.cliente_id else AliadoEmpleabilidad.objects.filter(vacantes_activas=True).exists()
        if hay_aliados:
            ctx['radar_empleabilidad_activo'] = True
            ctx['empleabilidad_habilitado_en'] = timezone.now().isoformat()
    estudiante.contexto_temporal = ctx if ctx else None
    estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
    
    partes = [mensaje]
    if (estudiante.contexto_temporal or {}).get('radar_empleabilidad_activo'):
        partes.append(
            "📍 *¡Radar de Empleos desbloqueado!*\n\n"
            "Ve al parque principal de Subachoque y envíame tu *Ubicación* "
            "usando el clip de WhatsApp (📎)."
        )
    if msg_cert_img:
        partes.append(msg_cert_img)
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
        estudiante_id_menu = kwargs.get('estudiante_id')
        if estudiante_id_menu:
            try:
                from .models import Estudiante as _EstMenu
                from .selector_curso import asegurar_inscripcion_catalogo_cliente

                _est = _EstMenu.objects.select_related('cliente').get(id=estudiante_id_menu)
                # B2B: con organización no hay menú 1-2-3; el curso viene del cliente vinculado
                if _est.cliente_id:
                    prog = asegurar_inscripcion_catalogo_cliente(_est)
                    org = _est.cliente.nombre if _est.cliente else 'tu organización'
                    if prog and prog.curso:
                        cur = prog.curso
                        emoji = (cur.emoji or '📚').strip()
                        return (
                            f"🌱 Hola {nombre_usuario}, bienvenido al programa de *{org}*.\n\n"
                            f"{emoji} Tu curso: *{cur.nombre}*\n\n"
                            "Escribe *continuar* para seguir tu lección.\n"
                            "Si tienes dudas, escribe *ayuda*."
                        )
                    return (
                        f"🌱 Hola {nombre_usuario}, bienvenido a *{org}*.\n\n"
                        "Tu organización aún no tiene cursos activos o siguen en preparación.\n"
                        "Escribe *ayuda* si necesitas soporte."
                    )
                _ctxm = dict(_est.contexto_temporal or {})
                _ctxm.pop('curso_activo_id', None)
                _est.contexto_temporal = _ctxm or None
                _est.save(update_fields=['contexto_temporal'])
            except Exception:
                pass
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
        from .selector_curso import asegurar_inscripcion_catalogo_cliente
        estudiante = Estudiante.objects.get(id=estudiante_id)
        if getattr(estudiante, 'cliente_id', None):
            asegurar_inscripcion_catalogo_cliente(estudiante)

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
    
    # Opción 2: cursos (sandbox: lista + números; B2B: sin menú global, curso del cliente)
    if intent == 'opcion_2':
        from .models import Curso, Estudiante
        from .selector_curso import cursos_visibles_para_estudiante, asegurar_inscripcion_catalogo_cliente

        estudiante_id_menu = kwargs.get('estudiante_id')
        if estudiante_id_menu:
            try:
                _est_cur = Estudiante.objects.select_related('cliente').get(id=estudiante_id_menu)
                if _est_cur.cliente_id:
                    prog = asegurar_inscripcion_catalogo_cliente(_est_cur)
                    if not prog or not prog.curso:
                        return (
                            "Tu organización aún no tiene cursos activos en este momento. ⚠️\n\n"
                            "Escribe *ayuda* si necesitas soporte."
                        )
                    cursos_list = list(cursos_visibles_para_estudiante(_est_cur))
                    if len(cursos_list) <= 1:
                        return (
                            f"📚 Tu curso asignado es *{prog.curso.nombre}*.\n\n"
                            "Escribe *continuar* para seguir."
                        )
                    respuesta = f"📚 *Cursos en {_est_cur.cliente.nombre}*\n\n"
                    for idx, curso in enumerate(cursos_list, 1):
                        respuesta += f"{idx}. {curso.emoji} *{curso.nombre}*\n"
                        respuesta += f"   📅 {curso.duracion_semanas} semanas | 📖 {curso.modulos.count()} módulos\n\n"
                    respuesta += (
                        "👉 Escribe el *número* del curso que quieres (o *continuar* para seguir el actual).\n\n"
                        "Escribe *menú* para volver al mensaje de bienvenida."
                    )
                    _est_cur.estado_onboarding = 'esperando_seleccion_curso'
                    _est_cur.save(update_fields=['estado_onboarding'])
                    return respuesta
            except Estudiante.DoesNotExist:
                pass

            try:
                _est_cur = Estudiante.objects.select_related('cliente').get(id=estudiante_id_menu)
                cursos_activos = cursos_visibles_para_estudiante(_est_cur)
            except Estudiante.DoesNotExist:
                cursos_activos = Curso.objects.filter(activo=True).order_by('orden', 'nombre')
        else:
            cursos_activos = Curso.objects.filter(activo=True).order_by('orden', 'nombre')

        if not cursos_activos.exists():
            return "No hay cursos disponibles en este momento. ⚠️"

        respuesta = "📚 *CURSOS DISPONIBLES EN eki*\n\n"

        for idx, curso in enumerate(cursos_activos, 1):
            respuesta += f"{idx}. {curso.emoji} *{curso.nombre}*\n"
            respuesta += f"   📅 {curso.duracion_semanas} semanas | 📖 {curso.modulos.count()} módulos\n\n"

        respuesta += "Para inscribirte en un curso:\n"
        respuesta += "👉 Escribe el *número* (ej: *1* o *2*)\n\n"
        respuesta += "También puedes escribir *MENÚ* para volver"

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
        # Curso de lista (mismo orden que opcion_2 / selector_curso por cliente)
        from .selector_curso import continuar_curso_seleccionado

        sid = kwargs.get('estudiante_id')
        msg = (kwargs.get('mensaje_original') or '').strip()
        if not sid or not msg.isdigit():
            return "Escribe el número del curso o *menú* para volver."
        return continuar_curso_seleccionado(sid, int(msg), msg)
    
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
        
        if mi_perfil:
            respuesta += f"📍 TU POSICIÓN: #{mi_posicion}\n"
            respuesta += f"⭐ {mi_perfil.puntos_totales} puntos | Nivel {mi_perfil.nivel}\n"
        
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
        from .models import Curso, Estudiante
        from .selector_curso import cursos_visibles_para_estudiante, asegurar_inscripcion_catalogo_cliente

        estudiante_id_vc = kwargs.get('estudiante_id')
        cursos_activos = None
        if estudiante_id_vc:
            try:
                _est_vc = Estudiante.objects.select_related('cliente').get(id=estudiante_id_vc)
                cursos_activos = cursos_visibles_para_estudiante(_est_vc)
                if _est_vc.cliente_id and cursos_activos.count() == 1:
                    prog = asegurar_inscripcion_catalogo_cliente(_est_vc)
                    if prog and prog.curso:
                        return (
                            f"📚 Tu curso: *{prog.curso.nombre}*\n\n"
                            "Escribe *continuar* para seguir."
                        )
            except Estudiante.DoesNotExist:
                pass
        if cursos_activos is None:
            cursos_activos = Curso.objects.filter(activo=True).order_by('orden', 'nombre')

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
        from .models import ProgresoEstudiante, Estudiante
        from .selector_curso import cursos_visibles_para_estudiante
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

        # Texto legacy del módulo (puede estar vacío si todo va en PasoModulo)
        contenido = primer_modulo.contenido or ''
        chunks = dividir_contenido_seguro(contenido, max_chars=1500)

        modulo_header = f"📖 *{primer_modulo.numero}. {primer_modulo.titulo}*\n\n"

        from .module_steps import (
            modulo_usa_pasos,
            pasos_activos_qs,
            reset_progreso_pasos_modulo,
            entregar_bloque_secciones_desde_paso,
            log_y_mensaje_modo_pasos_sin_pasos,
        )

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
                "🎮 *Nuestra experiencia de formación funciona a través de puntos*\n\n"
                "A medida que avances en el curso, tendrás retos que evaluar.\n\n"
                "¡Vamos a aprender y avanzar juntos! 💪"
            )
        partes_intro = [mensaje_1]
        partes_intro.append(msg_geronimo)
        partes_intro.append(msg_maria)
        if msg_gamificacion:
            partes_intro.append(msg_gamificacion)
        partes_intro.append("📚 *Comenzamos con el primer módulo de tu curso...* 👇")
        msg_intro = "\n\n".join(partes_intro)

        if modulo_usa_pasos(primer_modulo):
            if not pasos_activos_qs(primer_modulo).exists():
                _fb_ins = log_y_mensaje_modo_pasos_sin_pasos(
                    primer_modulo, 'inscripcion_primer_modulo'
                )
                return '[MULTI_MSG]' + msg_intro + '[SEP]' + _fb_ins
            partes_bloque_mod0: list[str] = []
            if primer_modulo.numero == 0 and (primer_modulo.contenido or '').strip():
                chunks0 = dividir_contenido_seguro(primer_modulo.contenido, max_chars=1500)
                if chunks0:
                    mensaje_mod0 = modulo_header + chunks0[0]
                    for chunk in chunks0[1:]:
                        if len(mensaje_mod0) + len(chunk) + 4 < 1500:
                            mensaje_mod0 += "\n\n" + chunk
                        else:
                            break
                    partes_bloque_mod0.append(mensaje_mod0)
            reset_progreso_pasos_modulo(progreso, save=True)
            msg_pasos = entregar_bloque_secciones_desde_paso(progreso, primer_modulo, 1)
            cuerpo_p = msg_pasos[len('[MULTI_MSG]') :]
            partes_insc = [msg_intro] + partes_bloque_mod0 + [p for p in cuerpo_p.split('[SEP]') if p]
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
        for extra_url_1, extra_titulo_1, extra_icono_1 in extra_media_urls_1:
            cap_1 = f'{extra_icono_1} {extra_titulo_1}'.strip() if extra_titulo_1 else None
            partes_insc.append(parte_mensaje_con_media(extra_url_1, cap_1))
            hay_media_insc = True
        if hay_media_insc:
            partes_insc.append("[DELAY:5]")
        hay_mas_modulos = curso.modulos.filter(numero__gt=primer_modulo.numero).exists()
        if hay_mas_modulos:
            partes_insc.append(
                "Tómese su tiempo para ver el material. Mientras usted aprende, aquí iremos organizando "
                "los recursos del siguiente nivel. En cuanto termine, solo responda *listo* para continuar."
            )

        return "[MULTI_MSG]" + "[SEP]".join(partes_insc)
    
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
            return "⏳ Tu módulo se está cargando, espera unos segundos y vuelve a escribir *listo*."
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

        # Varios cursos activos pero en pausa drip en alguno: no pedir "elige curso"; seguir solo ese curso
        if progresos_activos.count() > 1:
            from .drip_schedule import drip_bloquea_siguiente_modulo

            _bloqueados_drip = []
            for _p in progresos_activos:
                _m = _p.modulo_actual
                if _m and drip_bloquea_siguiente_modulo(_p, _m):
                    _bloqueados_drip.append(_p)
            if _bloqueados_drip:
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
        
        _ctx_sesion_asistente = estudiante.contexto_temporal or {}
        if (
            _ctx_sesion_asistente.get('tipo') == 'asistente_dario'
            and estudiante.estado_onboarding == 'esperando_respuesta_asistente'
        ):
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
            from .module_steps import reset_progreso_pasos_modulo
            reset_progreso_pasos_modulo(progreso, save=False)
            progreso.save()
        
        # Tras cerrar reto (Darío + facilitadora), el puntero ya está en el siguiente módulo pero el estudiante
        # aún no ha visto su contenido. Un "listo" aquí no debe cerrar ese módulo (evita saltar módulo 4).
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
            msg_norm = ''
        
        # Regla estricta del curso: solo "listo" avanza.
        if _es_mensaje_listo_avance_curso(msg_norm):
            from .drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

            ya_completo_modulo = ModuloCompletado.objects.filter(
                progreso=progreso,
                modulo=modulo_actual
            ).exists()
            if ya_completo_modulo and progreso.fecha_ultimo_avance:
                _blk = mensaje_bloqueo_avance_siguiente_modulo(
                    estudiante, progreso, modulo_actual
                )
                if _blk:
                    return _blk

            from .module_steps import (
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
                idx_p = progreso.paso_actual_modulo
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
                            "⚠️ [pasos] índice inválido | est=%s idx=%s",
                            estudiante.id,
                            idx_p,
                            exc_info=True,
                        )

            # Mini examen (PreguntaModulo): legacy sin pasos, o tras completar todos los pasos activos
            from .pregunta_handler import tiene_pregunta_modulo, obtener_pregunta_modulo, formatear_pregunta, guardar_contexto_pregunta

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
            from .gamificacion import PerfilGamificacion
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
            
            siguiente_modulo = progreso.curso.modulos.filter(
                numero__gt=modulo_actual.numero
            ).order_by('numero').first()
            
            if siguiente_modulo:
                from .drip_schedule import mensaje_bloqueo_avance_siguiente_modulo

                total_modulos = progreso.curso.modulos.count()
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
                    return _blk_fin

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
                    from .module_steps import (
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
                
                # v1.9.8h: Agentes — Darío (checkpoints: ej. módulos 1, 3, último si curso largo, …) + Facilitadora después
                _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                nombre_tutor = (
                    (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                    progreso.curso.nombre_agente_tutor or 'Claudia'
                )
                nombre_asistente = (
                    (_cliente.nombre_agente_asistente if _cliente and hasattr(_cliente, 'nombre_agente_asistente') and _cliente.nombre_agente_asistente else '') or
                    progreso.curso.nombre_agente_asistente or 'Darío'
                )
                
                dario_msg = None
                
                if es_modulo_reto:
                    logger.info(
                        '🎯 [checkpoint-reto] activo | est=%s curso_id=%s modulo_cerrado_id=%s num=%s',
                        estudiante.id,
                        progreso.curso_id,
                        modulo_actual.id,
                        modulo_actual.numero,
                    )
                    from .tutor_ia_modulo import (
                        descripcion_rango_modulos_reto_esp,
                        listar_modulos_cobertura_reto,
                    )

                    modulos_reto = listar_modulos_cobertura_reto(modulo_actual, progreso.curso)
                    modulos_reto_range = descripcion_rango_modulos_reto_esp(modulos_reto)

                    dario_msg = (
                        f"💬 *{nombre_asistente}*\n\n"
                        f"¡Hola! Es hora de una pausa para repasar conceptos. "
                        f"{nombre_tutor} te va a recibir con un reto sobre {modulos_reto_range}.\n\n"
                        f"Te puedo ayudar a resolver un par de preguntas antes. "
                        f"¿Tienes alguna pregunta sobre lo que hemos visto? Envíame un audio o escríbeme; si no tienes preguntas, escribe *listo*."
                    )

                    _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                    estudiante.contexto_temporal = {
                        'tipo': 'asistente_dario',
                        'curso_activo_id': progreso.curso_id,
                        'modulo_id': modulo_actual.id,
                        'progreso_id': progreso.id,
                        'modulos_reto_ids': [m.id for m in modulos_reto],
                        'preguntas_hechas': 0,
                        '_ts_leccion': _prev_ts,
                    }
                    estudiante.estado_onboarding = 'esperando_respuesta_asistente'
                    estudiante.save()
                    
                    # v1.9.8i: Reto modules — only Darío (NO completado msg, NO next module)
                    return dario_msg
                
                # v1.9.8i: Normal module — just show next module (no completado msg)
                partes = [msg_modulo]
                hay_media = False
                if primera_media_url:
                    partes.append(parte_mensaje_con_media(primera_media_url))
                    hay_media = True
                for extra_url, extra_titulo, extra_icono in extra_media_urls:
                    cap_x = f'{extra_icono} {extra_titulo}'.strip() if extra_titulo else None
                    partes.append(parte_mensaje_con_media(extra_url, cap_x))
                    hay_media = True
                if hay_media:
                    partes.append("[DELAY:5]")
                partes.append("Tómese su tiempo para ver el material. Mientras usted aprende, aquí iremos organizando los recursos del siguiente nivel. En cuanto termine, solo responda *listo* para continuar.")
                return "[MULTI_MSG]" + "[SEP]".join(partes)
            
            else:
                # Completó todos los módulos
                from .models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal

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
                if usar_gamificacion_final:
                    try:
                        _cliente = estudiante.cliente if hasattr(estudiante, 'cliente') and estudiante.cliente else None
                        nombre_tutor = (
                            (_cliente.nombre_agente_tutor if _cliente and hasattr(_cliente, 'nombre_agente_tutor') and _cliente.nombre_agente_tutor else '') or
                            progreso.curso.nombre_agente_tutor or 'Claudia'
                        )
                        nombre_asistente = (
                            (_cliente.nombre_agente_asistente if _cliente and hasattr(_cliente, 'nombre_agente_asistente') and _cliente.nombre_agente_asistente else '') or
                            progreso.curso.nombre_agente_asistente or 'Darío'
                        )
                        
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
                        
                        dario_final = (
                            f"💬 *{nombre_asistente}*\n\n"
                            f"¡Felicitaciones! Terminaste todos los módulos. "
                            f"Antes de recibir tu certificado, {nombre_tutor} tiene un reto final para ti sobre {modulos_final_range}.\n\n"
                            f"¿Tienes alguna pregunta sobre lo que vimos en esta parte del curso? Envíame un audio o escríbeme; si no tienes preguntas, escribe *listo*."
                        )
                        
                        _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
                        estudiante.contexto_temporal = {
                            'tipo': 'asistente_dario',
                            'curso_activo_id': progreso.curso_id,
                            'modulo_id': modulos_final[-1].id if modulos_final else None,
                            'progreso_id': progreso.id,
                            'modulos_reto_ids': [m.id for m in modulos_final],
                            'preguntas_hechas': 0,
                            'es_reto_final': True,
                            '_ts_leccion': _prev_ts,
                        }
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
                    from .certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
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
        
        # Si escribieron "continuar" (primera vez o retomando), mostrar el módulo actual
        else:
            _ctx_show = dict(estudiante.contexto_temporal or {})
            if modulo_actual and _ctx_show.get('post_reto_entregar_modulo_id') == modulo_actual.id:
                _ctx_show.pop('post_reto_entregar_modulo_id', None)
                estudiante.contexto_temporal = _ctx_show or None
                estudiante.save(update_fields=['contexto_temporal'])

            from .module_steps import (
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
                        "Escribe *listo* para registrar tu avance y seguir 👇"
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
            for extra_url_c, extra_titulo_c, extra_icono_c in extra_media_urls_c:
                cap_c = f'{extra_icono_c} {extra_titulo_c}'.strip() if extra_titulo_c else None
                partes_c.append(parte_mensaje_con_media(extra_url_c, cap_c))
                hay_media_c = True
            if hay_media_c:
                partes_c.append("[DELAY:5]")
            partes_c.append("Tómese su tiempo para ver el material. Mientras usted aprende, aquí iremos organizando los recursos del siguiente nivel. En cuanto termine, solo responda *listo* para continuar.")
            
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
