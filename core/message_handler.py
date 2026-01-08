"""
Handler para capturar y procesar mensajes entrantes de WhatsApp
- Meta WhatsApp Business API
- Twilio WhatsApp
"""

from django.utils import timezone
import logging
from .models import WhatsappLog, Estudiante
from .intent_detector import detect_intent
from .response_templates import get_response_for_intent
from .utils import enviar_whatsapp
from .audio_processor import procesar_audio_whatsapp
from .learning_system import guardar_aprendizaje, obtener_contexto_ia
from .gamificacion_actions import otorgar_puntos_mensaje, otorgar_puntos_audio, generar_mensaje_motivacional

logger = logging.getLogger(__name__)


class MensajeEntrante:
    """Clase para normalizar mensajes de diferentes proveedores"""
    def __init__(self, telefono, texto, mensaje_id, proveedor='twilio', timestamp=None, 
                 es_audio=False, audio_url=None, audio_transcripcion=None, audio_path=None):
        self.telefono = self._limpiar_telefono(telefono)
        self.texto = texto.strip() if texto else ''
        self.mensaje_id = mensaje_id
        self.proveedor = proveedor
        self.timestamp = timestamp or timezone.now()
        self.es_audio = es_audio
        self.audio_url = audio_url
        self.audio_transcripcion = audio_transcripcion
        self.audio_path = audio_path
        
    def _limpiar_telefono(self, numero):
        """Normaliza el número de teléfono"""
        import re
        numero = re.sub(r'\D', '', str(numero))
        if len(numero) == 10:
            numero = f"57{numero}"  # Agregar código de Colombia
        return numero
        
    def guardar(self):
        """Guarda el mensaje en la BD"""
        # Usar transcripción si es un audio
        mensaje_texto = self.audio_transcripcion if self.es_audio and self.audio_transcripcion else self.texto
        
        log = WhatsappLog.objects.create(
            telefono=self.telefono,
            mensaje=mensaje_texto,
            mensaje_id=self.mensaje_id,
            tipo='INCOMING',  # Mensaje recibido del usuario
            estado='RECIBIDO',
            fecha=self.timestamp,
            es_audio=self.es_audio,
            audio_url=self.audio_url,
            audio_transcripcion=self.audio_transcripcion,
            audio_path=self.audio_path
        )
        
        if self.es_audio:
            logger.info(f"🎤 Audio guardado: {self.mensaje_id} de {self.telefono} - Transcripción: {mensaje_texto[:50]}...")
        else:
            logger.info(f"✅ Mensaje guardado: {self.mensaje_id} de {self.telefono}")
        
        return log


def procesar_mensaje_entrante(mensaje: MensajeEntrante):
    """
    Procesa un mensaje entrante:
    1. Guarda en BD
    2. Obtiene o crea estudiante
    3. Genera respuesta con IA (OpenAI)
    4. Envía respuesta
    """
    print("🔵 ENTRANDO A procesar_mensaje_entrante")
    try:
        # 1. Guardar mensaje
        print("🔵 Guardando mensaje en BD...")
        log = mensaje.guardar()
        print(f"✅ Mensaje guardado con ID: {log.id}")
        
        # 2. Obtener o crear estudiante
        print("🔵 Obteniendo/creando estudiante...")
        estudiante, created = Estudiante.objects.get_or_create(
            telefono=mensaje.telefono,
            defaults={'nombre': f'Usuario {mensaje.telefono[-4:]}'}
        )
        print(f"✅ Estudiante: {estudiante.nombre} (created={created})")
        
        # 3. PRIMERO revisar contexto conversacional ANTES de detectar intent
        print("🔵 Revisando contexto conversacional...")
        respuesta_text = None
        agente_nombre = None
        intent = None
        
        # CONTEXTO ESPECIAL: Detectar si el último mensaje fue selección de curso
        # Buscar el último mensaje enviado a este usuario
        ultimo_mensaje_sistema = WhatsappLog.objects.filter(
            telefono=mensaje.telefono,
            tipo='SENT'
        ).order_by('-fecha').first()
        
        # Si el último mensaje tenía el marcador de selector de curso y el usuario escribió un número
        if (ultimo_mensaje_sistema and 
            '[SELECTOR_CURSO_ACTIVO]' in ultimo_mensaje_sistema.mensaje and
            mensaje.texto.strip().isdigit()):
            
            print(f"🎯 Detectado contexto: Selección de curso activo")
            indice = int(mensaje.texto.strip())
            
            from .selector_curso import continuar_curso_seleccionado
            respuesta_text = continuar_curso_seleccionado(
                estudiante_id=estudiante.id,
                indice_curso=indice,
                mensaje_original=mensaje.texto
            )
            intent = 'seleccion_curso_activo'
        
        # Si NO hay contexto especial, entonces detectar intent normal
        if intent is None:
            print("🔵 Detectando intención...")
            print(f"🔵 Texto recibido: '{mensaje.texto}'")
            print(f"🔵 Es audio: {mensaje.es_audio}")
            if mensaje.es_audio:
                print(f"🔵 Transcripción: '{mensaje.audio_transcripcion}'")
            
            intent = detect_intent(mensaje.texto)
            print(f"✅ Intent detectado: {intent}")
        
        # Usar plantillas para casos simples (rápido y gratis)
        if intent in ['saludo', 'opcion_1', 'opcion_2', 'opcion_3', 'ayuda', 'progreso', 'tareas', 
                      'cafe', 'cacao', 'aguacate',
                      'ver_cursos', 'inscribir_curso', 'continuar_leccion', 'mi_progreso_cursos', 'iniciar_examen', 'cambiar_nombre']:
            print(f"🎯 Usando plantilla para intent: {intent}")
            print(f"🎯 Estudiante ID: {estudiante.id}, Nombre: {estudiante.nombre}")
            
            # Pasar datos adicionales necesarios para cursos
            respuesta_text = get_response_for_intent(
                intent, 
                nombre_usuario=estudiante.nombre,
                estudiante_id=estudiante.id,
                mensaje_original=mensaje.texto
            )
            logger.info(f"🎯 Usando plantilla para intent: {intent}")
        
        # Detectar si está cambiando su nombre con formato "mi nombre es X"
        elif 'mi nombre es' in mensaje.texto.lower() or 'me llamo' in mensaje.texto.lower():
            print(f"👤 Estudiante cambiando nombre...")
            respuesta_text = _manejar_cambio_nombre(estudiante, mensaje.texto)
        
        else:
            # Sistema de Agentes Especializados (estilo Huaku)
            print(f"🤖 Activando sistema de agentes IA...")
            try:
                from .agentes_ia import seleccionar_agente
                
                # Obtener contexto de conversación para IA
                contexto_conversacion = obtener_contexto_ia(estudiante, limite=5)
                
                # Seleccionar agente apropiado según contexto
                agente = seleccionar_agente(estudiante, mensaje.texto)
                agente_nombre = agente.__class__.__name__
                print(f"✅ Agente seleccionado: {agente_nombre}")
                
                # Generar respuesta con el agente
                respuesta_text = agente.responder(mensaje.texto)
                intent = 'ai_response'
                print(f"✅ {agente_nombre} respondió: {respuesta_text[:50]}...")
                logger.info(f"🤖 Respuesta generada por {agente_nombre}")
                
                # Guardar para aprendizaje
                try:
                    guardar_aprendizaje(
                        estudiante=estudiante,
                        pregunta=mensaje.texto,
                        respuesta=respuesta_text,
                        agente=agente_nombre
                    )
                except Exception as e_learn:
                    logger.warning(f"⚠️ Error guardando aprendizaje: {e_learn}")
                    
            except Exception as e:
                print(f"⚠️ Error en sistema de agentes: {str(e)[:100]}")
                logger.warning(f"⚠️ Error en agentes, usando IA básica: {e}")
                
                # Fallback a IA básica
                try:
                    from .ai_assistant import responder_con_ia
                    respuesta_text = responder_con_ia(mensaje.texto, mensaje.telefono)
                    intent = 'ai_response'
                    agente_nombre = 'IA Básica'
                except Exception as e2:
                    # Último fallback
                    respuesta_text = "Gracias por tu mensaje. Un asesor te responderá pronto. ¿Puedo ayudarte con algo más? Escribe 'ayuda' para ver opciones."
                    print(f"💬 Usando respuesta genérica: {respuesta_text}")
                    logger.info(f"💬 Usando respuesta genérica")
        
        # 4. Enviar respuesta automática
        print("🔵 Preparando para enviar respuesta...")
        print(f"🔵 respuesta_text: {respuesta_text}")
        print(f"🔵 proveedor: {mensaje.proveedor}")
        
        if respuesta_text:
            # Remover marcadores especiales antes de enviar al usuario
            respuesta_text_limpia = respuesta_text.replace('[SELECTOR_CURSO_ACTIVO]', '').strip()
            
            # Guardar info del agente en el log si se usó IA
            if agente_nombre and log:
                try:
                    log.agente_usado = agente_nombre
                    log.save(update_fields=['agente_usado'])
                except Exception as e_log:
                    logger.warning(f"⚠️ Error actualizando log con agente: {e_log}")
            
            # Si el mensaje vino de Twilio, responder por Twilio
            if mensaje.proveedor == 'twilio':
                print("📤 Enviando por Twilio...")
                print(f"📱 Teléfono destino: {mensaje.telefono}")
                print(f"💬 Mensaje: {respuesta_text_limpia[:100]}...")
                
                # Detectar si hay video en el mensaje
                import re
                video_url = None
                # Buscar: "🎥 Video educativo:" seguido de URL
                video_match = re.search(r'🎥\s*Video educativo:\s*\n\s*(https?://[^\s]+)', respuesta_text_limpia)
                
                if video_match:
                    video_url = video_match.group(1)
                    print(f"🎥 Video detectado: {video_url}")
                    
                    # Si es localhost, NO enviar como media_url (Twilio no puede acceder)
                    if 'localhost' in video_url or '127.0.0.1' in video_url:
                        print("⚠️ Video es localhost - Twilio no puede acceder")
                        print("💡 Usa ngrok para exponer el servidor públicamente")
                        # Reemplazar con nota informativa
                        respuesta_text_limpia = re.sub(
                            r'🎥\s*Video educativo:\s*\n\s*[^\n]+',
                            '🎥 Video educativo disponible\n\n⚠️ Para ver el video, necesitas configurar ngrok o un servidor público.',
                            respuesta_text_limpia
                        ).strip()
                        video_url = None  # No enviar como media
                    else:
                        # URL pública válida - quitar del texto para no duplicar
                        respuesta_text_limpia = re.sub(r'🎥\s*Video educativo:\s*\n\s*[^\n]+', '', respuesta_text_limpia).strip()
                
                from .utils import enviar_whatsapp_twilio
                resultado_envio = enviar_whatsapp_twilio(
                    telefono=mensaje.telefono,
                    texto=respuesta_text_limpia,
                    mensaje_id_referencia=mensaje.mensaje_id,
                    media_url=video_url,
                    texto_log=respuesta_text  # Preservar marcador en log
                )
                print(f"✅ Resultado envío Twilio: {resultado_envio}")
                if resultado_envio.get('success'):
                    print(f"✅ ENVIADO a {mensaje.telefono}")
                else:
                    print(f"❌ ERROR enviando: {resultado_envio.get('response')}")
            else:
                print("📤 Enviando por Meta WhatsApp...")
                # Usar Meta WhatsApp Cloud API
                from .utils import enviar_whatsapp
                resultado_envio = enviar_whatsapp(
                    telefono=mensaje.telefono,
                    texto=respuesta_text_limpia,
                    mensaje_id_referencia=mensaje.mensaje_id
                )
                print(f"✅ Resultado envío Meta: {resultado_envio}")
            logger.info(f"📤 Respuesta automática enviada a {mensaje.telefono}")
        else:
            print("⚠️ No hay respuesta_text para enviar")
        
        # 5. 🎮 GAMIFICACIÓN: DESACTIVADA (Usuario prefiere enfoque en certificados)
        # try:
        #     if mensaje.es_audio:
        #         resultado_puntos = otorgar_puntos_audio(estudiante)
        #     else:
        #         resultado_puntos = otorgar_puntos_mensaje(estudiante)
        #     print(f"✨ Actividad: +{resultado_puntos.get('puntos_ganados', 0)} pts")
        # except Exception as e_gamif:
        #     logger.warning(f"⚠️ Error en gamificación: {e_gamif}")
        pass  # Gamificación desactivada
        
        return {
            'status': 'success',
            'mensaje_id': log.id,
            'intent': intent,
            'estudiante': estudiante.nombre
        }
        
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


def procesar_twilio_webhook(post_data):
    """
    Procesa webhooks de Twilio WhatsApp
    Esperado: Body, From (whatsapp:+57...), To, MessageSid
    Soporta mensajes de texto y audio
    """
    print("🔵 ENTRANDO A procesar_twilio_webhook")
    print(f"🔵 post_data recibida: {post_data}")
    try:
        msg_body = post_data.get('Body', '').strip()
        msg_from = post_data.get('From', '')
        msg_sid = post_data.get('MessageSid', '')
        num_media = int(post_data.get('NumMedia', 0))
        
        print(f"🔵 Body: {msg_body}")
        print(f"🔵 From: {msg_from}")
        print(f"🔵 MessageSid: {msg_sid}")
        print(f"🔵 NumMedia: {num_media}")
        
        # Limpiar número
        if msg_from.startswith('whatsapp:'):
            msg_from = msg_from.replace('whatsapp:', '')
        
        # Variables para audio
        es_audio = False
        audio_url = None
        audio_transcripcion = None
        audio_path = None
        
        # Variables para video
        es_video = False
        video_url = None
        video_path = None
        
        # Verificar si es un audio o video
        if num_media > 0:
            media_type = post_data.get('MediaContentType0', '')
            media_url = post_data.get('MediaUrl0', '')
            media_sid = post_data.get('MediaSid0', msg_sid)
            
            if 'audio' in media_type.lower():
                es_audio = True
                audio_url = media_url
                
                print(f"🎤 AUDIO DETECTADO: {media_type}")
                print(f"🎤 MediaUrl: {audio_url}")
                
                # Procesar audio: descargar + transcribir
                resultado_audio = procesar_audio_whatsapp(
                    {'media_url': audio_url, 'media_sid': media_sid},
                    proveedor='twilio'
                )
                
                if resultado_audio['success']:
                    audio_transcripcion = resultado_audio['texto']
                    audio_path = resultado_audio['audio_path']
                    msg_body = audio_transcripcion  # Usar transcripción como texto
                    print(f"✅ Audio transcrito: {audio_transcripcion}")
                else:
                    print(f"❌ Error procesando audio: {resultado_audio['error']}")
                    msg_body = "[Audio recibido - Error en transcripción]"
            
            elif 'video' in media_type.lower():
                es_video = True
                video_url = media_url
                
                print(f"📹 VIDEO DETECTADO: {media_type}")
                print(f"📹 MediaUrl: {video_url}")
                
                # Guardar info del video (procesamiento posterior)
                msg_body = "[Video recibido - Analizando cultivo]"
                
                # TODO: Aquí puedes procesar el video (guardar, analizar con IA, etc.)
        
        if not msg_from:
            print("❌ Twilio: Datos incompletos en webhook")
            logger.warning("❌ Twilio: Datos incompletos en webhook")
            return False
        
        print(f"📥 TWILIO: Mensaje de {msg_from}: {msg_body}")
        logger.info(f"📥 TWILIO: Mensaje de {msg_from}: {msg_body}")
        
        # Crear objeto normalizado
        mensaje = MensajeEntrante(
            telefono=msg_from,
            texto=msg_body,
            mensaje_id=msg_sid,
            proveedor='twilio',
            es_audio=es_audio,
            audio_url=audio_url,
            audio_transcripcion=audio_transcripcion,
            audio_path=audio_path
        )
        
        print(f"✅ Objeto mensaje creado: {mensaje.telefono} - Audio: {es_audio}")
        
        # Procesar
        print("🔵 Llamando a procesar_mensaje_entrante...")
        resultado = procesar_mensaje_entrante(mensaje)
        print(f"✅ Resultado: {resultado}")
        return resultado.get('status') == 'success'
        
    except Exception as e:
        print(f"❌ Error en Twilio webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        logger.error(f"❌ Error en Twilio webhook: {str(e)}", exc_info=True)
        return False


def procesar_meta_webhook(payload):
    """
    Procesa webhooks de Meta WhatsApp Business API
    Estructura esperada: entry[0].changes[0].value.messages
    """
    try:
        # Navegar en la estructura de Meta
        entries = payload.get('entry', [])
        
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                
                for msg in messages:
                    # Solo procesar mensajes de texto
                    if msg.get('type') != 'text':
                        continue
                    
                    msg_from = msg.get('from', '')
                    msg_id = msg.get('id', '')
                    texto = msg.get('text', {}).get('body', '')
                    timestamp = msg.get('timestamp', '')
                    
                    if not texto or not msg_from:
                        continue
                    
                    logger.info(f"📥 META: Mensaje de {msg_from}: {texto}")
                    
                    # Crear objeto normalizado
                    mensaje = MensajeEntrante(
                        telefono=msg_from,
                        texto=texto,
                        mensaje_id=msg_id,
                        proveedor='meta'
                    )
                    
                    # Procesar
                    procesar_mensaje_entrante(mensaje)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en Meta webhook: {str(e)}", exc_info=True)
        return False


# ==========================================
# FUNCIONES AUXILIARES PARA SISTEMA DE CURSOS
# ==========================================

def _manejar_modulo_especifico(estudiante, mensaje_texto: str):
    """Maneja cuando un estudiante pide un módulo específico"""
    from .models import ProgresoEstudiante
    import re
    
    # Extraer número
    match = re.search(r'(\d+)', mensaje_texto)
    if not match:
        return "Especifica el número del módulo (1-5). Ejemplo: 'módulo 2'"
    
    numero = int(match.group(1))
    
    # Buscar progreso activo
    progreso = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        completado=False
    ).first()
    
    if not progreso:
        return "No tienes cursos activos. Escribe 'ver cursos' para empezar. 📚"
    
    modulo = progreso.curso.modulos.filter(numero=numero).first()
    
    if not modulo:
        return f"Ese módulo no existe. El curso tiene {progreso.curso.modulos.count()} módulos."
    
    # Mostrar contenido
    return f"""{progreso.curso.emoji} **{progreso.curso.nombre}**

📖 **Módulo {modulo.numero}: {modulo.titulo}**

{modulo.contenido}

━━━━━━━━━━━━━━━━━━━━

✅ Cuando termines, escribe:
   "completar módulo {modulo.numero}"

💡 O pregúntame dudas sobre este tema."""


def _manejar_cambio_nombre(estudiante, mensaje_texto: str):
    """Maneja el cambio de nombre del estudiante"""
    import re
    
    # Extraer el nuevo nombre usando patrones comunes
    # Buscar después de "mi nombre es" o "me llamo"
    patrones = [
        r'mi nombre es\s+(.+)',
        r'me llamo\s+(.+)',
        r'cambiar nombre\s+(.+)',
        r'actualizar nombre\s+(.+)',
        r'modificar nombre\s+(.+)',
    ]
    
    nuevo_nombre = None
    texto_limpio = mensaje_texto.lower().strip()
    
    for patron in patrones:
        match = re.search(patron, texto_limpio, re.IGNORECASE)
        if match:
            nuevo_nombre = match.group(1).strip()
            break
    
    if not nuevo_nombre:
        return """❌ No pude detectar tu nuevo nombre.

Por favor escribe:
"Mi nombre es [Tu Nombre]"

Ejemplo:
• Mi nombre es Juan Pérez
• Me llamo María González"""
    
    # Capitalizar nombre correctamente
    nuevo_nombre = nuevo_nombre.title()
    
    # Validar longitud
    if len(nuevo_nombre) < 2:
        return "El nombre debe tener al menos 2 caracteres. Intenta de nuevo."
    
    if len(nuevo_nombre) > 100:
        return "El nombre es muy largo (máximo 100 caracteres). Intenta de nuevo."
    
    # Actualizar en BD
    nombre_anterior = estudiante.nombre
    estudiante.nombre = nuevo_nombre
    estudiante.save()
    
    logger.info(f"✅ Nombre actualizado: {nombre_anterior} → {nuevo_nombre}")
    
    # Confirmar cambio
    from .response_templates import get_response_for_intent
    return get_response_for_intent('confirmar_cambio_nombre', nuevo_nombre=nuevo_nombre)

