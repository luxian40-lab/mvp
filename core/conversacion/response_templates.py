"""
Plantillas de respuesta para cada intent - Agro Colombiano.
Permite personalizar respuestas sin cambiar la lógica del webhook.
"""
import contextvars
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from urllib.parse import quote

from core.conversacion.claves_contexto import contexto_limpio
from core.conversacion.multimsg import MEDIA, partir_sep
from core.helpers_examenes import evaluar_checkpoint_reto_ia


logger = logging.getLogger(__name__)

TEXTO_MODULO_CARGANDO = "⏳ Tu módulo se está cargando, espera unos segundos y Pulse continuar, para seguir aprendiendo."
# Un *listo* mientras el anterior todavía se está enviando. No se manda al chat.
LECCION_EN_CURSO = '[LECCION_EN_CURSO]'
_VENTANA_ENTREGA_SEG = 90
_retener_turno = contextvars.ContextVar('eki_retener_turno', default=False)
_turno_estudiante = contextvars.ContextVar('eki_turno_est', default=None)


def activar_retencion_turno():
    """El webhook retiene el turno hasta terminar de enviar; un test lo suelta al volver a entrar."""
    return _retener_turno.set(True)


def cerrar_retencion_turno(token):
    _retener_turno.reset(token)


def soltar_turno_entrega_actual():
    estudiante_id = _turno_estudiante.get()
    if not estudiante_id:
        return
    _turno_estudiante.set(None)
    from django.db import transaction

    from core.models import Estudiante

    try:
        with transaction.atomic():
            est = Estudiante.objects.select_for_update().get(id=estudiante_id)
            ctx = dict(est.contexto_temporal or {})
            if ctx.pop('_leccion_enviando', None) is None:
                return
            est.contexto_temporal = ctx
            est.save(update_fields=['contexto_temporal'])
    except Estudiante.DoesNotExist:
        return

# Twilio exige body no vacío junto a media_url; nunca usar solo emoji (p. ej. 📹).
MENSAJE_CAPTION_SOLO_MEDIA = (
    'Aquí tiene el material del módulo. Revíselo con calma.'
)


def parte_mensaje_con_media(url: str, caption: str | None = None) -> str:
    """Bloque para [MULTI_MSG]: marcador [MEDIA:…] con el texto del autor si lo hay.

    Sin caption el adjunto viaja solo: el relleno genérico y los títulos
    internos no le dicen nada al estudiante.
    """
    cap = (caption or '').strip()
    u = (url or '').strip()
    if not u:
        return cap or MENSAJE_CAPTION_SOLO_MEDIA
    return f'{cap}\n\n{MEDIA}{u}]' if cap else f'{MEDIA}{u}]'


def _es_mensaje_listo_avance_curso(texto: str) -> bool:
    """*listo* y *continuar* son el mismo disparador de avance."""
    from core.intent_detector import mensaje_indica_listo
    return mensaje_indica_listo(texto)


def partes_presentacion_agentes_curso(estudiante, curso) -> list:
    """
    Bloques de texto tutor + asistente (+ gamificación según cliente), sin prefijo [MULTI_MSG].
    Lista vacía si el curso no usa agentes IA.
    """
    if not getattr(curso, 'usar_agentes_ia', True):
        return []
    from core.tutor_ia_modulo import generar_presentacion_agentes

    nombre_tutor = 'Formador'
    nombre_asistente = 'Compañero'
    msg_facilitador, msg_asistente = generar_presentacion_agentes(
        curso.nombre,
        estudiante_nombre=getattr(estudiante, 'nombre', None) or 'Estudiante',
        nombre_tutor=nombre_tutor,
        nombre_asistente=nombre_asistente,
        curso=curso,
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
            '*Nuestra experiencia de formación funciona a través de puntos*\n\n'
            'A medida que avance en el curso, tendrá retos que evaluar.\n\n'
            '¡Vamos a aprender y avanzar juntos!'
        )
    return partes


def _barra_progreso(porcentaje: int) -> str:
    """Genera barra de progreso visual para WhatsApp."""
    llenas = int(porcentaje / 10)
    vacias = 10 - llenas
    return "▓" * llenas + "░" * vacias


def _mensaje_bloqueo_drip(fecha_desbloqueo):
    from core.drip_schedule import format_mensaje_bloqueo_drip
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
    from core.empleabilidad_pausa import empleabilidad_en_pausa

    if empleabilidad_en_pausa():
        return False
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
    from core.models import Curso, ProgresoEstudiante, AliadoEmpleabilidad, PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal
    from core.gamificacion import PerfilGamificacion
    
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
                nombre_tutor_final = 'Formador'
                nombre_asist_final = 'Compañero'
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
                estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
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
                })
                estudiante.estado_onboarding = 'esperando_respuesta_asistente'
                estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])

                from core.agentes_whatsapp import mensaje_con_titular_agente

                return (
                    "[MULTI_MSG]"
                    "🎉 *¡Completaste todos los módulos del curso!*"
                    "[SEP]"
                    + mensaje_con_titular_agente(
                        nombre_asist_final,
                        (
                            f"Antes de tu certificado, {nombre_tutor_final} te planteará un reto final sobre {modulos_final_range}.\n\n"
                            "¿Tienes dudas antes del reto? Envíame tu pregunta (texto o audio).\n"
                            "Si no tiene dudas, pulse continuar, para seguir aprendiendo.\n\n"
                            "[SEND_BUTTON:continuemos]"
                        ),
                    )
                )

            progreso.completado = True
            progreso.fecha_completado = timezone.now()
            progreso.fecha_ultimo_avance = timezone.now()
            progreso.save(update_fields=['completado', 'fecha_completado', 'fecha_ultimo_avance'])
            estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
                'tipo': 'pregunta_abierta_final',
                'curso_id': curso.id,
                'progreso_id': progreso.id,
                'pregunta_abierta_final_id': pregunta_abierta.id,
            })
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
        from core.certificado_service import crear_certificado_automatico, obtener_url_certificado_twilio
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
    
    # Post-certificate cutoff — radar pausado: no Subachoque.
    from core.empleabilidad_pausa import empleabilidad_en_pausa, mensaje_radar_desbloqueado

    estudiante.estado_onboarding = 'curso_finalizado'
    ctx = estudiante.contexto_temporal or {}
    if empleabilidad_en_pausa():
        ctx.pop('radar_empleabilidad_activo', None)
        ctx.pop('aliado_empleabilidad_objetivo_id', None)
        ctx.pop('mision_empleabilidad_id', None)
    elif not ctx.get('radar_empleabilidad_activo') and _cliente_habilita_proximidad(estudiante.cliente):
        hay_aliados = AliadoEmpleabilidad.objects.filter(vacantes_activas=True).filter(
            Q(cliente__isnull=True) | Q(cliente=estudiante.cliente)
        ).exists() if estudiante.cliente_id else AliadoEmpleabilidad.objects.filter(vacantes_activas=True).exists()
        if hay_aliados:
            ctx['radar_empleabilidad_activo'] = True
            ctx['empleabilidad_habilitado_en'] = timezone.now().isoformat()
    estudiante.contexto_temporal = ctx if ctx else None
    estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])
    
    partes = [mensaje]
    radar_copy = mensaje_radar_desbloqueado()
    if radar_copy and (estudiante.contexto_temporal or {}).get('radar_empleabilidad_activo'):
        partes.append(radar_copy)
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
    Usa URL pública regional S3 (presigned + rewrite de host causaba 63019).
    
    Args:
        leccion_o_modulo: Instancia de Leccion o Modulo con video_archivo o video_url
        
    Returns:
        str: URL completa del video o None
    """
    from core.twilio_media import normalizar_media_url_s3

    # Prioridad 1: Archivo subido a S3 → pública regional
    if hasattr(leccion_o_modulo, 'video_archivo') and leccion_o_modulo.video_archivo:
        key = leccion_o_modulo.video_archivo.name.lstrip('/')
        return normalizar_media_url_s3(f'https://eki-produccion.s3.us-east-2.amazonaws.com/{key}')

    # Prioridad 2: URL externa (YouTube/Vimeo/directa)
    if hasattr(leccion_o_modulo, 'video_url') and leccion_o_modulo.video_url:
        url = leccion_o_modulo.video_url
        if 'eki-produccion.s3' in url or 'amazonaws.com' in url:
            return normalizar_media_url_s3(url) or url
        return url

    # Prioridad 3: Método personalizado del modelo
    if hasattr(leccion_o_modulo, 'get_video_url_publica'):
        url = leccion_o_modulo.get_video_url_publica()
        if url:
            if 'eki-produccion.s3' in url or 'amazonaws.com' in url:
                return normalizar_media_url_s3(url) or url
            return url

    return None


def activar_checkpoint_facilitador(estudiante, progreso, modulo_cerrado) -> str:
    """
    Abre el checkpoint IA al cerrar `modulo_cerrado`: el compañero saluda y la
    facilitadora entrega el reto cuando el estudiante responde *listo*.

    El puntero de módulo no avanza; eso ocurre después de evaluar el reto.
    """
    from core.tutor_ia_modulo import (
        descripcion_rango_modulos_reto_esp,
        listar_modulos_cobertura_reto,
    )

    cliente = getattr(estudiante, 'cliente', None)
    nombre_tutor = 'Formador'
    nombre_asistente = 'Compañero'

    logger.info(
        '🎯 [checkpoint-reto] activo | est=%s curso_id=%s modulo_cerrado_id=%s num=%s',
        estudiante.id,
        progreso.curso_id,
        modulo_cerrado.id,
        modulo_cerrado.numero,
    )

    modulos_reto = listar_modulos_cobertura_reto(modulo_cerrado, progreso.curso)
    modulos_reto_range = descripcion_rango_modulos_reto_esp(modulos_reto)

    from core.agentes_whatsapp import mensaje_con_titular_agente

    dario_msg = mensaje_con_titular_agente(
        nombre_asistente,
        (
            f"Soy el Compañero. Es hora de una pausa para repasar conceptos. "
            f"El Formador le va a plantear un reto sobre {modulos_reto_range}.\n\n"
            f"Le puedo ayudar a resolver un par de preguntas antes. "
            f"¿Tiene alguna pregunta sobre lo que hemos visto? Envíeme un audio o "
            "escríbame. Si no tiene preguntas, pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]"
        ),
    )

    _prev_ts = (estudiante.contexto_temporal or {}).get('_ts_leccion', 0)
    estudiante.contexto_temporal = contexto_limpio(estudiante.contexto_temporal, {
        'tipo': 'asistente_dario',
        'curso_activo_id': progreso.curso_id,
        'modulo_id': modulo_cerrado.id,
        'progreso_id': progreso.id,
        'modulos_reto_ids': [m.id for m in modulos_reto],
        'preguntas_hechas': 0,
        '_ts_leccion': _prev_ts,
    })
    estudiante.estado_onboarding = 'esperando_respuesta_asistente'
    estudiante.save()

    return dario_msg


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
    estudiante_id_b2b = kwargs.get('estudiante_id')
    if estudiante_id_b2b:
        try:
            from core.models import Estudiante
            from core.flujo_whatsapp_b2b import respuesta_b2b_sin_menu

            _est_b2b = Estudiante.objects.select_related('cliente').get(id=estudiante_id_b2b)
            _alt = respuesta_b2b_sin_menu(_est_b2b, intent, nombre_usuario, kwargs)
            if _alt is not None:
                return _alt
        except Estudiante.DoesNotExist:
            pass

    from core.conversacion.intents.despacho import INTENTS

    _responder = INTENTS.get(intent)
    if _responder is not None:
        return _responder(intent, nombre_usuario, kwargs)
    
    return f"Hola {nombre_usuario}, ¿cómo te puedo ayudar con tu aprendizaje agropecuario? 🌱"
