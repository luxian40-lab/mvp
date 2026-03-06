
def enviar_video_whatsapp(to, video_url):
    pass


# ====================================================
# 🚀 FUNCIÓN MAESTRA: Enviar Content Templates de Twilio
# ====================================================
import json
import logging
from twilio.rest import Client
from django.conf import settings
from .models_extras import ArchivoModulo
from .models import WhatsappLog
from django.utils import timezone

logger = logging.getLogger(__name__)

# ====================================================
# Content SIDs de Twilio (Plantillas Aprobadas)
# ====================================================
TWILIO_CONTENT_SIDS = {
    'habeas_data': 'HX579c4e36ab20209afa55742f6e3c0c55',
    'confirmar_datos': 'HXbb0358bcb33c46a521e392f8e7dcca7a',
    'confirmar_datos_v2': 'HXa252d102417aefd5ff15e11694e9fb1e',
    'menu_principal': 'HXc9027f1ab8cdf781fafa1096c9010d5d',
    'listadocursos1': 'HX6a31cb9924af620e3dc914b71e95fd20',
    'listadocursos2': 'HXcb7abe9df97c2e3085b862523a5a1d8b',
    'listadocursos3': 'HX09b9105e5698450aeec07965832b183c',
    'listadocursos4': 'HX9484a11d743ed99add4b6039286ff763',
}


def enviar_template_twilio(telefono, content_sid, variables=None):
    """
    Función maestra para enviar mensajes con Content Templates de Twilio.
    
    Args:
        telefono (str): Número destino (ej: +573001234567)
        content_sid (str): El Content SID del template (HX...)
        variables (dict): Variables del template (ej: {'1': 'Juan', '2': 'CC 12345'})
    
    Returns:
        dict: {'success': bool, 'mensaje_id': str|None, 'response': str}
    """
    try:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        twilio_number = 'whatsapp:+573202948806'
        
        if not account_sid or not auth_token:
            return {'success': False, 'mensaje_id': None, 'response': 'Twilio credentials missing'}
        
        # Formatear teléfono
        telefono_limpio = str(telefono).replace('whatsapp:', '').strip()
        if not telefono_limpio.startswith('+'):
            telefono_limpio = f'+{telefono_limpio}'
        destino = f'whatsapp:{telefono_limpio}'
        
        client = Client(account_sid, auth_token)
        
        msg_params = {
            'from_': twilio_number,
            'content_sid': content_sid,
            'to': destino,
        }
        
        if variables:
            msg_params['content_variables'] = json.dumps(variables)
        
        message = client.messages.create(**msg_params)
        
        # Log
        WhatsappLog.objects.create(
            telefono=telefono_limpio.replace('+', ''),
            mensaje=f"[TEMPLATE:{content_sid}] vars={variables}",
            mensaje_id=message.sid,
            estado='SENT',
            tipo='SENT',
            fecha=timezone.now()
        )
        
        logger.info(f"✅ Template {content_sid} enviado a {destino}: {message.sid}")
        return {'success': True, 'mensaje_id': message.sid, 'response': f'Sent: {message.status}'}
        
    except Exception as e:
        logger.error(f"❌ Error enviando template: {e}")
        return {'success': False, 'mensaje_id': None, 'response': str(e)}


def enviar_habeas_data(telefono):
    """Paso 1: Enviar mensaje de Habeas Data con botones [Acepto] [No acepto]"""
    return enviar_template_twilio(
        telefono,
        TWILIO_CONTENT_SIDS['habeas_data']
    )


def enviar_confirmacion_datos(telefono, nombre, cedula, organizacion, edad=None, municipio=None):
    """Paso 2: Verificación exitosa — confirmar datos con 5 variables
    Template: 👤 Verificación Exitosa
    {{1}} = Nombre, {{2}} = Cédula, {{3}} = Empresa, {{4}} = Edad, {{5}} = Municipio
    """
    return enviar_template_twilio(
        telefono,
        TWILIO_CONTENT_SIDS['confirmar_datos_v2'],
        variables={
            '1': nombre or 'No registrado',
            '2': cedula or 'No registrada',
            '3': organizacion or 'eki',
            '4': str(edad) if edad else 'No registrada',
            '5': municipio or 'No registrado',
        }
    )


def enviar_menu_principal(telefono, nombre):
    """Paso 3: Menú principal con botones [Mis cursos] [Mis puntos] [Ayuda]"""
    return enviar_template_twilio(
        telefono,
        TWILIO_CONTENT_SIDS['menu_principal'],
        variables={'1': nombre}
    )


def enviar_lista_cursos(telefono, estudiante):
    """
    Envía lista dinámica de cursos como texto plano (más confiable).
    Muestra progreso del estudiante en cada curso.
    El estudiante solo necesita escribir el número para seleccionar.
    """
    from .models import Curso, ProgresoEstudiante
    
    org = estudiante.cliente
    
    # Obtener TODOS los cursos activos del estudiante
    if org:
        cursos = Curso.objects.filter(
            cliente=org, activo=True
        ).order_by('orden', 'nombre')
    else:
        cursos = Curso.objects.filter(activo=True).order_by('orden', 'nombre')
    
    cursos_list = list(cursos)
    cantidad = len(cursos_list)
    
    if cantidad == 0:
        from .utils import enviar_whatsapp_twilio
        return enviar_whatsapp_twilio(
            telefono,
            "📚 No hay cursos disponibles en este momento. Escribe *menú* para volver."
        )
    
    # Agregar info de progreso a cada curso
    progresos = ProgresoEstudiante.objects.filter(
        estudiante=estudiante
    ).select_related('curso')
    progreso_map = {p.curso_id: p for p in progresos}
    
    nombre = estudiante.nombre or 'Estudiante'
    org_nombre = org.nombre if org else 'eki'
    
    msg = f"📚 *Cursos disponibles — {org_nombre}*\n"
    msg += f"Hola *{nombre}*, estos son tus cursos:\n\n"
    
    for idx, curso in enumerate(cursos_list, 1):
        emoji = curso.emoji or "📖"
        prog = progreso_map.get(curso.id)
        estado = ""
        if prog:
            if prog.completado:
                estado = " ✅ Completado"
            else:
                porcentaje = prog.porcentaje_avance()
                if porcentaje > 0:
                    estado = f" ⏳ {porcentaje}%"
                else:
                    estado = " 🆕"
        else:
            estado = " 🆕"
        
        msg += f"*{idx}.* {emoji} {curso.nombre}{estado}\n"
    
    msg += "👉 Escribe *tomar 1* para el primer curso\n"
    msg += "     Ejemplo: *tomar 1* o simplemente *1*\n\n"
    msg += "👉 Escribe *menú* para volver"
    
    from .utils import enviar_whatsapp_twilio
    return enviar_whatsapp_twilio(telefono, msg)


def enviar_mensaje_ventas(telefono):
    """
    Fase 0: Mensaje para usuarios no registrados.
    Envía texto plano con 3 opciones de menú.
    """
    msg = (
        "🚜 ¡Hola! Soy eki, la plataforma educativa por WhatsApp "
        "para el sector agrícola.\n\n"
        "Veo que tu número no está registrado en ninguna de nuestras "
        "capacitaciones actuales.\n\n"
        "¿En qué te podemos ayudar?\n\n"
        "1️⃣ 🏢 *eki para mi empresa*\n"
        "   Capacitar trabajadores con nosotros\n\n"
        "2️⃣ 🌐 *Visitar sitio web*\n"
        "   www.eki.com.co\n\n"
        "3️⃣ 🙋‍♂️ *Soy estudiante (Ayuda)*\n"
        "   Si cambiaste de número o necesitas ayuda\n\n"
        "👉 Escribe el número de tu opción"
    )
    
    from .utils import enviar_whatsapp_twilio
    return enviar_whatsapp_twilio(telefono, msg)


def enviar_gamificacion_visual(telefono, estudiante):
    """
    Envía estado visual de gamificación al estudiante.
    Barra de progreso emoji + nivel + puntos.
    """
    from .gamificacion import PerfilGamificacion
    
    try:
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
    except PerfilGamificacion.DoesNotExist:
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    
    # Generar barra de progreso
    barra = generar_barra_progreso_emoji(perfil.porcentaje_nivel())
    
    # Nombres de nivel temáticos del campo
    NOMBRES_NIVEL = {
        1: '🌱 Semilla', 2: '🌿 Brote', 3: '🌾 Sembrador',
        4: '🌻 Cultivador', 5: '🌳 Agricultor',
        6: '🚜 Tractorista', 7: '🏅 Capataz',
        8: '⭐ Mayordomo', 9: '👑 Hacendado',
        10: '🏆 Leyenda del Campo'
    }
    
    nombre_nivel = NOMBRES_NIVEL.get(perfil.nivel, f'Nivel {perfil.nivel}')
    
    msg = (
        f"¡Vas volando, *{estudiante.nombre}*! 🚀\n\n"
        f"\n\n"
        f"🏆 *Nivel:* {nombre_nivel}\n"
        f"⭐ *Puntos:* {perfil.puntos_totales} pts\n"
        f"🎯 *Avance:* {barra} {perfil.porcentaje_nivel()}%\n"
        f"🔥 *Racha:* módulo {perfil.racha_dias_actual}\n\n"
    )
    
    if perfil.puntos_para_siguiente_nivel() > 0:
        msg += f"📈 Faltan *{perfil.puntos_para_siguiente_nivel()} pts* para el siguiente nivel\n\n"
    
    msg += "¡Sigue así! 💪\n\n"
    msg += "Escribe *menú* para volver"
    
    from .utils import enviar_whatsapp_twilio
    return enviar_whatsapp_twilio(telefono, msg)


def generar_barra_progreso_emoji(porcentaje, longitud=10):
    """
    Genera una barra de progreso con emojis.
    
    Args:
        porcentaje (int): 0-100
        longitud (int): Cantidad total de bloques
    
    Returns:
        str: Ej. '🟩🟩🟩🟩⬜⬜⬜⬜⬜⬜'
    """
    porcentaje = max(0, min(100, porcentaje))
    llenos = round((porcentaje / 100) * longitud)
    vacios = longitud - llenos
    return '🟩' * llenos + '⬜' * vacios

def enviar_archivo_modulo_whatsapp(telefono, archivo_modulo, texto_extra=None):
    """
    Envía cualquier archivo de ArchivoModulo por WhatsApp usando Twilio.
    Args:
        telefono (str): Número destino en formato internacional (ej: +573001234567)
        archivo_modulo (ArchivoModulo): Instancia de ArchivoModulo
        texto_extra (str): Texto adicional a enviar junto con el archivo (opcional)
    Returns:
        dict: {'success': bool, 'mensaje_id': str|None, 'response': str}
    """
    url_envio = archivo_modulo.get_url_para_envio()
    if not url_envio:
        return {'success': False, 'mensaje_id': None, 'response': 'No hay URL pública para el archivo'}

    # Descripción según tipo
    tipo = archivo_modulo.get_tipo_display() if hasattr(archivo_modulo, 'get_tipo_display') else archivo_modulo.tipo
    titulo = archivo_modulo.titulo or ''
    descripcion = f"{tipo}: {titulo}"
    if texto_extra:
        descripcion = f"{descripcion}\n{texto_extra}"

    # Preparar log preliminar
    log = WhatsappLog.objects.create(
        telefono=telefono.replace('whatsapp:', '').replace('+', ''),
        mensaje=descripcion,
        estado='PENDING',
        tipo='SENT',
        fecha=timezone.now()
    )

    try:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        whatsapp_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
        if not all([account_sid, auth_token, whatsapp_number]):
            raise ValueError("Faltan credenciales de Twilio en settings.py")

        # Formato correcto para Twilio
        to = telefono
        if not to.startswith('whatsapp:'):
            if not to.startswith('+'):
                to = f'+{to}'
            to = f'whatsapp:{to}'

        # Formatear número FROM correctamente (evitar doble whatsapp:)
        from_number = str(whatsapp_number).strip()
        if not from_number.startswith('whatsapp:'):
            if not from_number.startswith('+'):
                from_number = f'+{from_number}'
            from_number = f'whatsapp:{from_number}'

        client = Client(account_sid, auth_token)
        # Agregar status_callback para rastreo
        status_callback_url = getattr(settings, 'TWILIO_STATUS_CALLBACK', None)
        message_params = {
            'from_': from_number,
            'to': to,
            'body': descripcion,
            'media_url': [url_envio]
        }
        if status_callback_url:
            message_params['status_callback'] = status_callback_url

        message = client.messages.create(**message_params)
        log.mensaje_id = message.sid
        log.estado = 'SENT'
        log.error_detalle = ''
        log.save()
        return {'success': True, 'mensaje_id': message.sid, 'response': 'Enviado'}
    except Exception as e:
        log.estado = 'ERROR'
        log.error_detalle = str(e)
        log.save()
        return {'success': False, 'mensaje_id': None, 'response': str(e)}
