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
import re

logger = logging.getLogger(__name__)


# ========== PARSER INTELIGENTE DE DATOS DE REGISTRO ==========

# Tipos de documento válidos (incluye variantes y números del menú)
TIPOS_DOC_MAP = {
    'CC': 'CC', 'CEDULA': 'CC', 'CÉDULA': 'CC', 'CEDULA DE CIUDADANIA': 'CC',
    'TI': 'TI', 'TARJETA': 'TI', 'TARJETA DE IDENTIDAD': 'TI',
    'CE': 'CE', 'EXTRANJERIA': 'CE', 'EXTRANJERÍA': 'CE', 'CEDULA DE EXTRANJERIA': 'CE',
    'PP': 'PP', 'PASAPORTE': 'PP',
    '1': 'CC', '2': 'TI', '3': 'CE', '4': 'PP',
}


def _parsear_datos_registro(mensaje_texto, estudiante=None):
    """
    Parsea datos de registro del usuario de forma flexible.
    Soporta:
    - 4 líneas separadas (nombre, municipio, tipo_doc, número)
    - Todo en una línea separado por comas
    - Todo en una línea sin separador claro
    - Datos en cualquier orden
    
    Returns:
        tuple (nombre, municipio, tipo_doc, cedula) o None si no se puede parsear
    """
    texto = mensaje_texto.strip()
    
    # ---- PASO 1: Separar en tokens ----
    # Intentar primero por líneas
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    
    if len(lineas) >= 4:
        # Formato de 4+ líneas
        return _intentar_parseo_ordenado(lineas)
    
    # Si hay menos de 4 líneas, intentar separar por comas
    if ',' in texto:
        partes = [p.strip() for p in texto.split(',') if p.strip()]
        if len(partes) >= 4:
            return _intentar_parseo_ordenado(partes)
        # Si hay 3 partes con coma, tal vez falta separar alguna
        if len(partes) >= 2:
            resultado = _intentar_parseo_flexible(partes)
            if resultado:
                return resultado
    
    # Si es una sola línea, intentar parseo inteligente
    return _parsear_linea_unica(texto)


def _intentar_parseo_ordenado(tokens):
    """Intenta parsear tokens en orden: nombre, municipio, tipo_doc, numero"""
    if len(tokens) < 4:
        return None
    
    nombre = tokens[0].strip().strip('_').strip('*')
    municipio = tokens[1].strip().strip('_').strip('*')
    tipo_doc_raw = tokens[2].strip().strip('_').strip('*').upper()
    cedula_raw = tokens[3].strip().strip('_').strip('*')
    
    tipo_doc = TIPOS_DOC_MAP.get(tipo_doc_raw, None)
    cedula = ''.join(filter(str.isdigit, cedula_raw))
    
    if _validar_datos(nombre, municipio, tipo_doc, cedula):
        return nombre, municipio, tipo_doc, cedula
    
    # Si el orden no funcionó, intentar detectar automáticamente
    return _intentar_parseo_desordenado(tokens)


def _intentar_parseo_desordenado(tokens):
    """Detecta cada campo automáticamente sin importar el orden"""
    nombre = None
    municipio = None
    tipo_doc = None
    cedula = None
    nombre_parts = []
    
    for token in tokens:
        t = token.strip().strip('_').strip('*')
        t_upper = t.upper()
        
        # ¿Es un tipo de documento?
        if not tipo_doc and t_upper in TIPOS_DOC_MAP:
            tipo_doc = TIPOS_DOC_MAP[t_upper]
            continue
        
        # ¿Es un número de documento? (6-15 dígitos)
        digits = ''.join(filter(str.isdigit, t))
        if not cedula and len(digits) >= 6 and len(digits) <= 15:
            cedula = digits
            continue
        
        # ¿Es texto? (nombre o municipio)
        if not t.isdigit() and len(t) >= 2:
            if not nombre:
                nombre = t
            elif not municipio:
                municipio = t
            else:
                nombre_parts.append(t)
    
    # Si tenemos partes extra, tal vez son parte del nombre
    if nombre_parts and nombre:
        nombre = nombre + ' ' + ' '.join(nombre_parts)
    
    if _validar_datos(nombre, municipio, tipo_doc, cedula):
        return nombre, municipio, tipo_doc, cedula
    
    return None


def _parsear_linea_unica(texto):
    """
    Parsea cuando todo viene en una sola línea.
    Detecta: tipo_doc y número de documento, el resto es nombre + municipio.
    """
    # Buscar tipo de documento en el texto
    tipo_doc = None
    tipo_doc_pos = -1
    texto_upper = texto.upper()
    
    # Buscar tipos de documento como palabras completas
    for patron, tipo in [
        (r'\bCC\b', 'CC'), (r'\bTI\b', 'TI'), (r'\bCE\b', 'CE'), (r'\bPP\b', 'PP'),
        (r'\bCEDULA\b', 'CC'), (r'\bCÉDULA\b', 'CC'), (r'\bPASAPORTE\b', 'PP'),
        (r'\bTARJETA\b', 'TI'), (r'\bEXTRANJERIA\b', 'CE'), (r'\bEXTRANJERÍA\b', 'CE'),
    ]:
        match = re.search(patron, texto_upper)
        if match:
            tipo_doc = tipo
            tipo_doc_pos = match.start()
            break
    
    # Buscar número de documento (secuencia de 6-15 dígitos)
    cedula = None
    cedula_match = re.search(r'\b(\d{6,15})\b', texto)
    if cedula_match:
        cedula = cedula_match.group(1)
    
    if not tipo_doc or not cedula:
        return None
    
    # Quitar tipo_doc y número del texto para obtener nombre y municipio
    texto_limpio = texto
    # Quitar el número
    texto_limpio = re.sub(r'\b' + re.escape(cedula) + r'\b', ' ', texto_limpio)
    # Quitar tipo de documento (con patrones amplios)
    for patron in [
        r'\b[Cc][Cc]\b', r'\b[Tt][Ii]\b', r'\b[Cc][Ee]\b', r'\b[Pp][Pp]\b',
        r'\b[Cc][eéEÉ]dula\b', r'\b[Pp]asaporte\b', r'\b[Tt]arjeta\b',
        r'\b[Ee]xtranjería\b', r'\b[Ee]xtranjeria\b',
        r'\bde ciudadan[ií]a\b', r'\bde identidad\b', r'\bde extranjería\b',
        r'\bde extranjeria\b',
        r'\bcon\b', r'\bdocumento\b', r'\bnum(?:ero)?\b', r'\bnúmero\b',
    ]:
        texto_limpio = re.sub(patron, ' ', texto_limpio, flags=re.IGNORECASE)
    
    # Limpiar espacios múltiples y separadores
    texto_limpio = re.sub(r'[,;:\-/]+', ' ', texto_limpio)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    
    if not texto_limpio or len(texto_limpio) < 3:
        return None
    
    # Separar nombre de municipio:
    # Estrategia: si hay comas -> primer token=nombre, segundo=municipio
    # Si no: buscar la palabra "de" como separador de municipio
    # O: tomar las primeras 2 palabras como nombre y la última como municipio
    palabras = texto_limpio.split()
    
    if len(palabras) >= 3:
        # Heurística: las últimas 1-2 palabras son municipio, el resto nombre
        # Si la penúltima es preposición ("de", "del"), incluirla en el municipio
        if palabras[-2].lower() in ['de', 'del', 'san', 'santa', 'la', 'el', 'los', 'las', 'puerto']:
            municipio = ' '.join(palabras[-2:])
            nombre = ' '.join(palabras[:-2])
        else:
            municipio = palabras[-1]
            nombre = ' '.join(palabras[:-1])
    elif len(palabras) == 2:
        nombre = palabras[0]
        municipio = palabras[1]
    else:
        nombre = texto_limpio
        municipio = 'No especificado'
    
    if _validar_datos(nombre, municipio, tipo_doc, cedula):
        return nombre, municipio, tipo_doc, cedula
    
    return None


def _intentar_parseo_flexible(partes):
    """Intenta parsear cuando hay 2-3 partes separadas por comas"""
    all_tokens = []
    for parte in partes:
        # Subdividir cada parte por espacios si contiene múltiples datos
        sub = parte.strip().split()
        all_tokens.extend(sub)
    
    return _intentar_parseo_desordenado(all_tokens) or _parsear_linea_unica(' '.join(partes))


def _validar_datos(nombre, municipio, tipo_doc, cedula):
    """Valida que todos los campos sean válidos"""
    if not nombre or len(nombre) < 2:
        return False
    if nombre.isdigit():
        return False
    if not municipio or len(municipio) < 2:
        return False
    if not tipo_doc:
        return False
    if not cedula or len(cedula) < 6 or len(cedula) > 15:
        return False
    return True

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

# Link a política de datos (URL general fallback)
URL_POLITICA_DATOS = getattr(settings, 'URL_POLITICA_DATOS', 'https://eki.com.co/#page-home')
EMAIL_SOPORTE = getattr(settings, 'EMAIL_SOPORTE', 'comunidad.educativa@eki.com.co')


def _url_politica_datos_cliente(estudiante=None, cliente=None):
    """
    URL de Habeas Data efectiva:
    1) Override por cliente (enlace_habeas_data)
    2) URL general de eki (settings o fallback)
    """
    c = cliente
    if c is None and estudiante is not None:
        c = getattr(estudiante, 'cliente', None)
    if c and getattr(c, 'enlace_habeas_data', None):
        return c.enlace_habeas_data
    return URL_POLITICA_DATOS


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
                f"Ok {estudiante.nombre}, ¿con qué documento te identificas?\n\n"
                "Escribe el número:\n"
                "1. Cédula (CC)\n"
                "2. Tarjeta de Identidad (TI)\n"
                "3. Cédula de Extranjería (CE)\n"
                "4. Pasaporte (PP)"
            )
            
            return False, mensaje_pedir_tipo
        else:
            # ❌ NO HA ACEPTADO - Solicitar aceptación
            logger.warning(f"⚠️ Habeas Data: {estudiante.nombre} no ha aceptado términos")
            
            url_politica = _url_politica_datos_cliente(estudiante=estudiante)
            mensaje_terminos = (
                f"¡Hola {estudiante.nombre}! 👋\n\n"
                "Bienvenido a *eki* 🌱\n"
                "Tu compañero de aprendizaje agrícola por WhatsApp\n\n"
                "Antes de comenzar, necesito tu autorización para usar tus datos personales "
                "(como tu nombre, teléfono y progreso de estudio). "
                "Esto es requerido por la Ley 1581 de 2012 de Colombia.\n\n"
                f"📄 Puedes leer todos los detalles aquí: {url_politica}\n\n"
                "🔒 Tu información está segura con nosotros\n"
                "Solo la usamos para:\n"
                "• Personalizar tu aprendizaje\n"
                "• Darte seguimiento a tu progreso\n"
                "• Enviarte tu certificado al finalizar\n"
                "• Mejorar nuestros cursos\n\n"
                "¿Aceptas? Responde *Sí* para comenzar"
            )
            
            return False, mensaje_terminos
    
    # Si ya aceptó pero falta completar datos
    if estudiante.estado_onboarding == 'esperando_tipo_doc':
        resultado = _parsear_datos_registro(mensaje_texto, estudiante)
        if resultado:
            nombre, municipio, tipo_doc, cedula = resultado
            estudiante.nombre = nombre
            estudiante.municipio = municipio
            estudiante.tipo_documento = tipo_doc
            estudiante.cedula = cedula
            estudiante.estado_onboarding = 'completado'
            estudiante.save()
            
            logger.info(f"✅ Onboarding completado: {nombre} de {municipio} - {tipo_doc}: {cedula}")
            
            mensaje_bienvenida = (
                f"🌱 ¡Bienvenido a eki, {nombre}!\n\n"
                "🚜 *Soluciones educativas a tu alcance*\n\n"
                "Aprende, mejora tu conocimiento y conecta con expertos.\n\n"
                "*¿Qué deseas hacer?*\n\n"
                "1️⃣ Ver mi progreso\n"
                "2️⃣ Explorar cursos\n"
                "3️⃣ Ayuda y soporte\n\n"
                "También puedes hacer preguntas en cualquier momento 💬"
            )
            
            return False, mensaje_bienvenida
        
        # Si no cumple el formato, dar instrucciones
        mensaje_error = (
            "No pude entender tus datos. Por favor responde con:\n\n"
            "1️⃣ Tu nombre completo\n"
            "2️⃣ Tu municipio\n"
            "3️⃣ Tipo de documento (CC, TI, CE o PP)\n"
            "4️⃣ Número de documento\n\n"
            "Puedes escribirlo en varias líneas o todo junto:\n\n"
            "📝 _Ejemplo en líneas separadas:_\n"
            "_María García_\n"
            "_Bogotá_\n"
            "_CC_\n"
            "_52456789_\n\n"
            "📝 _O todo en una línea:_\n"
            "_María García, Bogotá, CC, 52456789_\n\n"
            "📝 _También funciona así:_\n"
            "_María García Bogotá CC 52456789_"
        )
        
        return False, mensaje_error
    
    # Ya no se usan los estados esperando_cedula y esperando_nombre (flujo simplificado)
    # Si llegó a esos estados viejos, resetear al inicio
    if estudiante.estado_onboarding in ['esperando_cedula', 'esperando_nombre']:
        estudiante.estado_onboarding = 'esperando_tipo_doc'
        estudiante.save()
        
        mensaje_reiniciar = (
            "📝 Empecemos de nuevo con el registro:\n\n"
            "Necesito 4 datos:\n\n"
            "1️⃣ Tu nombre completo\n"
            "2️⃣ Tu municipio\n"
            "3️⃣ Tipo de documento (CC, TI, CE o PP)\n"
            "4️⃣ Número de documento\n\n"
            "📝 _Ejemplo:_\n"
            "_María García_\n"
            "_Bogotá_\n"
            "_CC_\n"
            "_52456789_\n\n"
            "También puedes escribirlo todo junto:\n"
            "_María García, Bogotá, CC, 52456789_"
        )
        
        return False, mensaje_reiniciar
    
    # Este código nunca debería ejecutarse ahora
    if estudiante.estado_onboarding == 'esperando_nombre_antiguo':
        # Código viejo mantenido por si acaso
        nombre_limpio = mensaje_texto.strip()
        
        if len(nombre_limpio) >= 2 and not nombre_limpio.isdigit():
            estudiante.nombre = nombre_limpio
            estudiante.estado_onboarding = 'completado'
            estudiante.save()
            
            logger.info(f"✅ Onboarding completado (flujo antiguo): {nombre_limpio}")
            
            mensaje_bienvenida = (
                f"🌱 ¡Bienvenido a eki, {nombre_limpio}!\n\n"
                "🚜 *Soluciones educativas a tu alcance*\n\n"
                "Aprende, mejora tu conocimiento y conecta con expertos.\n\n"
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
        "✏️ *Si solo falló un dato tuyo* (nombre, municipio, documento, etc.), puedes corregirlo "
        "tú mismo sin esperar: escribe *menú* y luego la opción *corregir datos*, "
        "o envía directamente *corregir datos* y sigue las instrucciones. "
        "Tu curso sigue ahí: cuando termines, escribe *continuar* o *menú*.\n\n"
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
        respuesta_ia += "\n\n\n\n"
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


def verificar_seguridad_completa(estudiante, mensaje_texto, telefono=None, numero_destino=None):
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
                
                mensaje_pedir_datos = (
                    "✅ ¡Perfecto!\n\n"
                    "📋 Para completar tu registro, responde estas preguntas en orden:\n\n"
                    "1️⃣ ¿Cómo te llamas? (Nombre completo)\n"
                    "2️⃣ ¿De qué municipio eres?\n"
                    "3️⃣ ¿Qué tipo de documento? (CC, TI, CE o PP)\n"
                    "4️⃣ ¿Número de documento?\n\n"
                    "👉 Ejemplo de respuesta:\n"
                    "_Juan Pérez_\n"
                    "_Popayán_\n"
                    "_CC_\n"
                    "_1234567890_\n\n"
                    "Escríbelo todo junto o línea por línea 📝"
                )
                return True, mensaje_pedir_datos, estudiante
                
            except Exception as e:
                logger.error(f"❌ Error creando estudiante: {e}")
                return True, "Error del sistema. Por favor intenta de nuevo.", None
        else:
            # Mostrar mensaje de bienvenida y pedir aceptación
            url_politica = URL_POLITICA_DATOS
            try:
                if numero_destino:
                    from .models import Cliente
                    import re as _re
                    nd = _re.sub(r'\D', '', numero_destino or '')
                    if nd:
                        cliente_match = None
                        # Búsqueda simple por terminación de dígitos (tolerante a +57 / sin +)
                        if cliente_match is None:
                            for c in Cliente.objects.exclude(numero_whatsapp_autorizado='').only('id', 'numero_whatsapp_autorizado', 'enlace_habeas_data'):
                                cnum = _re.sub(r'\D', '', c.numero_whatsapp_autorizado or '')
                                if cnum and (nd.endswith(cnum) or cnum.endswith(nd)):
                                    cliente_match = c
                                    break
                        if cliente_match and getattr(cliente_match, 'enlace_habeas_data', None):
                            url_politica = cliente_match.enlace_habeas_data
            except Exception:
                url_politica = URL_POLITICA_DATOS

            mensaje_inicial = (
                "👋 *¡Bienvenido a eki!*\n\n"
                "🚜 Tu plataforma de soluciones educativas por WhatsApp\n\n"
                "📜 *Protección de Datos Personales*\n\n"
                "Antes de comenzar, necesitamos que aceptes nuestra política de tratamiento de datos personales "
                "de acuerdo con la Ley 1581 de 2012.\n\n"
                f"🔗 Lee nuestra política completa aquí:\n{url_politica}\n\n"
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
