"""
🛡️ MÓDULO DE SEGURIDAD Y SOPORTE
- Habeas Data (Aceptación de términos)
- Botón de Pánico (Keywords de soporte)
- Validaciones legales Colombia (Ley 1581 de 2012)
"""

from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Estudiante, SolicitudSoporte
from .utils import enviar_whatsapp
import logging

logger = logging.getLogger(__name__)

# ========== CONFIGURACIÓN ==========

# Keywords que activan el botón de pánico
# IMPORTANTE: Solo frases EXACTAS o muy específicas
# Evitar capturar preguntas educativas normales
KEYWORDS_SOPORTE = [
    'necesito ayuda', 'ayúdame', 'ayuda urgente',
    'quiero hablar con alguien', 'hablar con humano',
    'soporte', 'support', 
    'atención al cliente', 'atencion al cliente',
    'problema grave', 'error grave', 'falla grave',
    'no funciona nada', 'nada funciona',
    'urgente', 'emergencia'
]

# Keywords de aceptación de términos
KEYWORDS_ACEPTACION = [
    'si', 'sí', 'acepto', 'aceptar', 'ok', 'okay', 
    'de acuerdo', 'adelante', 'continuar', 'yes'
]

# Link a política de datos (actualizar con tu URL real)
URL_POLITICA_DATOS = getattr(settings, 'URL_POLITICA_DATOS', 'https://www.eki.com.co/home/')
EMAIL_SOPORTE = getattr(settings, 'EMAIL_SOPORTE', 'soporte@eki.com')


# ========== HABEAS DATA ==========

def verificar_terminos(estudiante, mensaje_texto):
    """
    Verifica si el estudiante ha aceptado términos y condiciones.
    Si no, intercepta el mensaje y solicita aceptación.
    
    Returns:
        tuple: (acepto: bool, respuesta_texto: str or None)
    """
    # Si ya aceptó y completó onboarding, continuar normalmente
    if estudiante.acepto_terminos and estudiante.estado_onboarding == 'completado':
        return True, None
    
    # Limpiar mensaje
    mensaje_lower = mensaje_texto.lower().strip()
    
    # Verificar si está aceptando términos
    if not estudiante.acepto_terminos:
        if any(keyword in mensaje_lower for keyword in KEYWORDS_ACEPTACION):
            # ✅ ACEPTÓ TÉRMINOS - Ahora pedir tipo de documento
            estudiante.acepto_terminos = True
            estudiante.fecha_aceptacion_terminos = timezone.now()
            estudiante.estado_onboarding = 'esperando_tipo_doc'
            estudiante.save()
            
            logger.info(f"✅ Habeas Data: {estudiante.nombre} aceptó términos, pidiendo tipo de documento")
            
            mensaje_pedir_tipo = (
                f"✅ ¡Perfecto, {estudiante.nombre}!\n\n"
                "📋 Para completar tu registro, primero necesito saber:\n\n"
                "*¿Qué tipo de documento tienes?*\n\n"
                "1️⃣ CC - Cédula de Ciudadanía\n"
                "2️⃣ TI - Tarjeta de Identidad\n"
                "3️⃣ CE - Cédula de Extranjería\n"
                "4️⃣ PP - Pasaporte\n\n"
                "👉 *Escribe el número* de tu tipo de documento\n"
                "Ejemplo: 1"
            )
            
            return False, mensaje_pedir_tipo
        else:
            # ❌ NO HA ACEPTADO - Solicitar aceptación
            logger.warning(f"⚠️ Habeas Data: {estudiante.nombre} no ha aceptado términos")
            
            mensaje_terminos = (
                f"☕ ¡Hola {estudiante.nombre}!\n\n"
                "Bienvenido a *Eki* 🚜\n"
                "Tu plataforma de educación agrícola por WhatsApp\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "📜 *PROTECCIÓN DE DATOS PERSONALES*\n\n"
                "Para comenzar, acepta nuestra política de tratamiento de datos (Ley 1581 de 2012 - Colombia).\n\n"
                f"📄 Lee aquí: {URL_POLITICA_DATOS}\n\n"
                "🔒 *Tu información está protegida*\n"
                "Solo usamos tus datos para:\n"
                "✅ Contenido educativo personalizado\n"
                "✅ Seguimiento de tu progreso\n"
                "✅ Certificados de finalización\n"
                "✅ Mejoras en nuestros cursos\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "👉 *Responde SÍ para aceptar y comenzar*"
            )
            
            return False, mensaje_terminos
    
    # Si ya aceptó pero falta tipo de documento
    if estudiante.estado_onboarding == 'esperando_tipo_doc':
        # Verificar si es una opción válida (1-4)
        if mensaje_texto.strip() in ['1', '2', '3', '4']:
            tipos_doc = {
                '1': ('CC', 'Cédula de Ciudadanía'),
                '2': ('TI', 'Tarjeta de Identidad'),
                '3': ('CE', 'Cédula de Extranjería'),
                '4': ('PP', 'Pasaporte')
            }
            
            codigo, nombre_tipo = tipos_doc[mensaje_texto.strip()]
            estudiante.tipo_documento = codigo
            estudiante.estado_onboarding = 'esperando_cedula'
            estudiante.save()
            
            logger.info(f"✅ Tipo de documento seleccionado: {estudiante.nombre} - {codigo}")
            
            mensaje_pedir_cedula = (
                f"✅ Perfecto, *{nombre_tipo}*\n\n"
                f"📝 Ahora escribe tu *número de {nombre_tipo.lower()}*\n\n"
                "📌 Solo el número, sin puntos ni espacios\n"
                "Ejemplo: 1234567890"
            )
            
            return False, mensaje_pedir_cedula
        else:
            # ❌ OPCIÓN INVÁLIDA
            mensaje_error = (
                "⚠️ Por favor selecciona una opción válida:\n\n"
                "1️⃣ CC - Cédula de Ciudadanía\n"
                "2️⃣ TI - Tarjeta de Identidad\n"
                "3️⃣ CE - Cédula de Extranjería\n"
                "4️⃣ PP - Pasaporte\n\n"
                "Escribe el número (1, 2, 3 o 4)"
            )
            
            return False, mensaje_error
    
    # Si ya aceptó y seleccionó tipo pero falta número
    if estudiante.estado_onboarding == 'esperando_cedula':
        # Verificar si es un número válido de cédula (6-15 dígitos)
        numero_limpio = ''.join(filter(str.isdigit, mensaje_texto))
        
        if len(numero_limpio) >= 6 and len(numero_limpio) <= 15:
            # ✅ CÉDULA VÁLIDA - Ahora pedir nombre
            estudiante.cedula = numero_limpio
            estudiante.estado_onboarding = 'esperando_nombre'
            estudiante.save()
            
            logger.info(f"✅ Documento registrado: {estudiante.tipo_documento} {numero_limpio}, pidiendo nombre")
            
            mensaje_pedir_nombre = (
                "✅ ¡Perfecto!\n\n"
                "👤 Por último, *¿cuál es tu nombre?*\n\n"
                "📝 Escribe tu nombre completo para personalizar tu experiencia\n\n"
                "Ejemplo: Juan Pérez"
            )
            
            return False, mensaje_pedir_nombre
        else:
            # ❌ CÉDULA INVÁLIDA
            tipo_nombre = dict(estudiante.TIPO_DOCUMENTO_CHOICES).get(estudiante.tipo_documento, 'documento')
            mensaje_error = (
                f"⚠️ El número que ingresaste no parece válido.\n\n"
                f"Por favor escribe tu *número de {tipo_nombre.lower()}* completo:\n"
                "• Solo números\n"
                "• Entre 6 y 15 dígitos\n"
                "• Sin puntos ni espacios\n\n"
                "Ejemplo: 1234567890"
            )
            
            return False, mensaje_error
    
    # Si ya tiene documento pero falta nombre
    if estudiante.estado_onboarding == 'esperando_nombre':
        # Validar que el nombre tenga al menos 2 caracteres y no sea solo números
        nombre_limpio = mensaje_texto.strip()
        
        if len(nombre_limpio) >= 2 and not nombre_limpio.isdigit():
            # ✅ NOMBRE VÁLIDO - Completar onboarding
            estudiante.nombre = nombre_limpio
            estudiante.estado_onboarding = 'completado'
            estudiante.save()
            
            logger.info(f"✅ Onboarding completado: {nombre_limpio} - {estudiante.tipo_documento}: {estudiante.cedula}")
            
            mensaje_bienvenida = (
                f"🌱 ¡Bienvenido a Eki, {nombre_limpio}!\n\n"
                "🚜 *Educación agrícola a tu alcance*\n\n"
                "Aprende técnicas de cultivo, mejora tu producción y conecta con expertos del campo.\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "*¿Qué deseas hacer?*\n\n"
                "1️⃣ Ver mi progreso\n"
                "2️⃣ Explorar cursos\n"
                "3️⃣ Ayuda y soporte\n\n"
                "📝 Escribe solo el número (1, 2 o 3)"
            )
            
            return True, mensaje_bienvenida
        else:
            # ❌ NOMBRE INVÁLIDO
            mensaje_error = (
                "⚠️ Por favor escribe un nombre válido.\n\n"
                "👤 ¿Cuál es tu nombre completo?\n\n"
                "Debe tener al menos 2 caracteres\n"
                "Ejemplo: Juan Pérez"
            )
            
            return False, mensaje_error
    
    # No debería llegar aquí, pero por seguridad
    return True, None


# ========== BOTÓN DE PÁNICO ==========

def verificar_keyword_soporte(mensaje_texto):
    """
    Verifica si el mensaje contiene una keyword de soporte.
    
    Returns:
        tuple: (es_soporte: bool, keyword_detectada: str or None)
    """
    mensaje_lower = mensaje_texto.lower().strip()
    
    for keyword in KEYWORDS_SOPORTE:
        if keyword in mensaje_lower:
            logger.info(f"🆘 Keyword de soporte detectada: '{keyword}'")
            return True, keyword
    
    return False, None


def procesar_solicitud_soporte(estudiante, mensaje_texto, keyword_usada):
    """
    Procesa una solicitud de soporte:
    1. Guarda en BD
    2. Notifica al equipo por email
    3. Responde al usuario
    
    Returns:
        str: Mensaje de respuesta para el usuario
    """
    logger.info(f"🆘 Procesando solicitud de soporte de {estudiante.nombre}")
    
    # 1. Crear registro en BD
    solicitud = SolicitudSoporte.objects.create(
        estudiante=estudiante,
        mensaje_original=mensaje_texto,
        keyword_usada=keyword_usada,
        prioridad='media'
    )
    
    # 2. Notificar al equipo por email
    try:
        asunto = f"🆘 Nueva Solicitud de Soporte - {estudiante.nombre}"
        cuerpo = f"""
Nueva solicitud de soporte recibida:

📱 Estudiante: {estudiante.nombre}
📞 Teléfono: {estudiante.telefono}
🆔 Cédula: {estudiante.cedula}
🔑 Keyword: {keyword_usada}
📅 Fecha: {solicitud.fecha_solicitud.strftime('%d/%m/%Y %H:%M')}

💬 Mensaje:
{mensaje_texto}

---
Ver en admin: {settings.ALLOWED_HOSTS[0]}/admin/core/solicitudsoporte/{solicitud.id}/change/
        """
        
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else EMAIL_SOPORTE,
            recipient_list=[EMAIL_SOPORTE],
            fail_silently=True  # No romper si falla el email
        )
        logger.info(f"✅ Email de notificación enviado a {EMAIL_SOPORTE}")
    except Exception as e:
        logger.error(f"❌ Error enviando email de soporte: {e}")
    
    # 3. Responder al usuario
    mensaje_respuesta = (
        f"🆘 *Solicitud de Soporte Recibida*\n\n"
        f"Hola {estudiante.nombre}, entendemos que necesitas ayuda.\n\n"
        "📧 *Hemos notificado a nuestro equipo.*\n\n"
        "🕐 *Tiempo de respuesta*\n"
        "Somos un equipo pequeño trabajando para ti. "
        "Te responderemos lo antes posible, generalmente en menos de 24 horas.\n\n"
        "📝 *Tu mensaje:*\n"
        f'"{mensaje_texto}"\n\n'
        "Si tienes más información, envíala ahora y la añadiremos a tu caso.\n\n"
        "Gracias por tu paciencia 🙏"
    )
    
    return mensaje_respuesta


# ========== INTERCEPTOR PRINCIPAL ==========

def interceptar_mensaje(estudiante, mensaje_texto):
    """
    Intercepta mensajes ANTES de procesarlos normalmente.
    
    Verifica en orden:
    1. Habeas Data (términos y condiciones)
    2. Si ya pasó por IA empática y ahora sí quiere soporte humano
    3. Keywords de soporte (botón de pánico) → IA empática primero
    
    Returns:
        tuple: (debe_procesar_normal: bool, respuesta_interceptada: str or None)
        - Si debe_procesar_normal=False, enviar respuesta_interceptada y DETENER
        - Si debe_procesar_normal=True, continuar con flujo normal
    """
    logger.info(f"🔍 Interceptando mensaje de {estudiante.nombre}")
    
    # 1. PRIORIDAD MÁXIMA: Verificar Habeas Data
    acepto, respuesta_terminos = verificar_terminos(estudiante, mensaje_texto)
    if not acepto:
        # Usuario no ha aceptado términos - BLOQUEAR todo procesamiento
        logger.warning(f"🛡️ Bloqueado por Habeas Data: {estudiante.nombre}")
        return False, respuesta_terminos
    
    if respuesta_terminos:
        # Acaba de aceptar - enviar bienvenida y DETENER (no procesar el "sí")
        logger.info(f"✅ Usuario aceptó términos, enviando bienvenida")
        return False, respuesta_terminos
    
    # 1.5 Si ya pasó por IA empática y ahora pide soporte explícitamente
    if estudiante.contexto_temporal and estudiante.contexto_temporal.get('tipo') == 'post_ia_empatica':
        from .ia_empatica import debe_escalar_a_soporte
        if debe_escalar_a_soporte(mensaje_texto):
            logger.info(f"🆘 Usuario persiste después de IA empática → Escalando a soporte")
            es_soporte, keyword = verificar_keyword_soporte(mensaje_texto)
            respuesta_soporte = procesar_solicitud_soporte(estudiante, mensaje_texto, 'soporte persistente')
            # Limpiar contexto
            estudiante.contexto_temporal = None
            estudiante.save()
            return False, respuesta_soporte
        else:
            # Si no es escalación, limpiar contexto y continuar normal
            estudiante.contexto_temporal = None
            estudiante.save()
    
    # 2. Verificar keywords de soporte
    es_soporte, keyword = verificar_keyword_soporte(mensaje_texto)
    if es_soporte:
        # NUEVO: Primero intentar con IA empática
        from .ia_empatica import responder_con_empatia, generar_respuesta_empatica_fallback, debe_escalar_a_soporte
        
        # Si explícitamente pide soporte humano, escalar directamente
        if debe_escalar_a_soporte(mensaje_texto):
            logger.info(f"🆘 Escalando directo a soporte humano")
            respuesta_soporte = procesar_solicitud_soporte(estudiante, mensaje_texto, keyword)
            return False, respuesta_soporte
        
        # Intentar con IA empática primero
        logger.info(f"💚 Respondiendo con IA empática antes de escalar")
        respuesta_ia = responder_con_empatia(mensaje_texto, estudiante.nombre)
        
        if not respuesta_ia:
            # Si falla IA, usar fallback empático
            respuesta_ia = generar_respuesta_empatica_fallback(mensaje_texto, estudiante.nombre)
        
        # Agregar opción de escalar al final
        respuesta_ia += "\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        respuesta_ia += "🆘 *Si aún necesitas soporte humano*, escribe:\n"
        respuesta_ia += "• \"Quiero soporte\"\n"
        respuesta_ia += "• \"Necesito hablar con alguien\"\n"
        respuesta_ia += "\nY te conectaremos con nuestro equipo. 💚"
        
        # Guardar en contexto temporal que ya pasó por IA empática (por si vuelve a pedir)
        estudiante.contexto_temporal = {
            'tipo': 'post_ia_empatica',
            'mensaje_original': mensaje_texto,
            'timestamp': timezone.now().isoformat()
        }
        estudiante.save()
        
        return False, respuesta_ia
    
    # 3. Todo OK - continuar con flujo normal
    logger.info(f"✅ Sin intercepciones - continuar flujo normal")
    return True, None


def verificar_seguridad_completa(estudiante, mensaje_texto, telefono=None):
    """
    Función principal para webhooks: maneja estudiante None y habeas data.
    
    Args:
        estudiante: Objeto Estudiante o None
        mensaje_texto: Mensaje recibido
        telefono: Teléfono del usuario (requerido si estudiante es None)
    
    Returns:
        tuple: (bloqueado: bool, respuesta: str or None, estudiante: Estudiante or None)
        - bloqueado=True: Enviar respuesta y detener procesamiento
        - bloqueado=False: Continuar con flujo normal
        - estudiante: El estudiante (puede ser recién creado)
    """
    # Si estudiante es None, necesitamos crear uno para habeas data
    if estudiante is None:
        if not telefono:
            logger.error("❌ Se requiere teléfono para crear estudiante")
            return True, "Error del sistema. Por favor intenta de nuevo.", None
        
        mensaje_lower = mensaje_texto.lower().strip()
        
        # Verificar si está aceptando términos para crear el estudiante
        if any(keyword in mensaje_lower for keyword in KEYWORDS_ACEPTACION):
            # ✅ Usuario aceptó términos - CREAR estudiante
            try:
                # Verificar si ya existe un estudiante con ese teléfono o cédula temporal
                estudiante_existente = Estudiante.objects.filter(
                    telefono=telefono
                ).first() or Estudiante.objects.filter(
                    cedula=f'TEMP_{telefono}'
                ).first()
                
                if estudiante_existente:
                    # Ya existe, actualizar estado
                    estudiante = estudiante_existente
                    if not estudiante.acepto_terminos:
                        estudiante.acepto_terminos = True
                        estudiante.fecha_aceptacion_terminos = timezone.now()
                        estudiante.estado_onboarding = 'esperando_tipo_doc'
                        estudiante.save()
                    logger.info(f"✅ Estudiante existente actualizado: {telefono}")
                else:
                    # Crear estudiante nuevo con estado inicial de habeas data
                    estudiante = Estudiante.objects.create(
                        telefono=telefono,
                        nombre='Usuario',  # Se actualizará en onboarding
                        cedula=f'TEMP_{telefono}',  # Temporal hasta que den la real
                        acepto_terminos=True,
                        fecha_aceptacion_terminos=timezone.now(),
                        estado_onboarding='esperando_tipo_doc',
                        activo=True
                    )
                    logger.info(f"✅ Nuevo estudiante creado: {telefono}")
                
                mensaje_pedir_tipo = (
                    "✅ ¡Perfecto!\n\n"
                    "📋 Para completar tu registro, necesito saber:\n\n"
                    "*¿Qué tipo de documento tienes?*\n\n"
                    "1️⃣ CC - Cédula de Ciudadanía\n"
                    "2️⃣ TI - Tarjeta de Identidad\n"
                    "3️⃣ CE - Cédula de Extranjería\n"
                    "4️⃣ PP - Pasaporte\n\n"
                    "👉 *Escribe el número* de tu tipo de documento\n"
                    "Ejemplo: 1"
                )
                return True, mensaje_pedir_tipo, estudiante
                
            except Exception as e:
                logger.error(f"❌ Error creando estudiante: {e}")
                return True, "Error del sistema. Por favor intenta de nuevo.", None
        else:
            # Mostrar mensaje de bienvenida y pedir aceptación
            mensaje_inicial = (
                "👋 *¡Bienvenido a Eki!*\n\n"
                "🚜 Tu plataforma de educación agrícola por WhatsApp\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "📜 *Protección de Datos Personales*\n\n"
                "Antes de comenzar, necesitamos que aceptes nuestra política de tratamiento de datos personales "
                "de acuerdo con la Ley 1581 de 2012.\n\n"
                f"🔗 Lee nuestra política completa aquí:\n{URL_POLITICA_DATOS}\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "*¿Aceptas el tratamiento de tus datos?*\n\n"
                "👉 Escribe *SÍ* para aceptar y continuar\n"
                "👉 Escribe *NO* si no deseas continuar"
            )
            return True, mensaje_inicial, None
    
    # Si estudiante existe, usar interceptor normal
    debe_procesar, respuesta = interceptar_mensaje(estudiante, mensaje_texto)
    return not debe_procesar, respuesta, estudiante


# ========== HELPERS PARA ADMIN ==========

def marcar_solicitud_resuelta(solicitud_id, respuesta, atendido_por):
    """
    Marca una solicitud como resuelta y envía respuesta al usuario
    """
    try:
        solicitud = SolicitudSoporte.objects.get(id=solicitud_id)
        solicitud.estado = 'resuelta'
        solicitud.respuesta = respuesta
        solicitud.atendido_por = atendido_por
        solicitud.fecha_resolucion = timezone.now()
        solicitud.save()
        
        # Enviar respuesta al usuario
        mensaje = (
            f"✅ *Respuesta de Soporte*\n\n"
            f"Hola {solicitud.estudiante.nombre},\n\n"
            f"{respuesta}\n\n"
            "Si necesitas más ayuda, no dudes en escribirnos.\n"
            "Estamos aquí para apoyarte 🙌"
        )
        
        enviar_whatsapp(solicitud.estudiante.telefono, mensaje)
        logger.info(f"✅ Solicitud {solicitud_id} resuelta y respuesta enviada")
        return True
    except Exception as e:
        logger.error(f"❌ Error marcando solicitud resuelta: {e}")
        return False
