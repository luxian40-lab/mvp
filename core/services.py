import time
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
import logging

from .models import EnvioLog
from .utils import enviar_whatsapp, enviar_sms_twilio, enviar_whatsapp_twilio

logger = logging.getLogger(__name__)

def ejecutar_campana_servicio(campana):
    """
    Envía mensajes (con o sin imagen) y guarda el registro (Log).
    Soporta múltiples proveedores: Meta WhatsApp, Twilio SMS, Twilio WhatsApp.
    Usa el proveedor configurado en la plantilla.
    Aplica filtro de etiquetas si están configuradas.
    """
    # Obtener destinatarios base (activos)
    destinatarios = campana.destinatarios.filter(activo=True)
    
    # Aplicar filtro de etiquetas si existen
    etiquetas_filtro = campana.filtro_etiquetas.all()
    if etiquetas_filtro.exists():
        # Filtrar estudiantes que tengan AL MENOS UNA de las etiquetas seleccionadas
        destinatarios = destinatarios.filter(etiquetas__in=etiquetas_filtro).distinct()
        print(f"🏷️ Filtrando por etiquetas: {', '.join([e.nombre for e in etiquetas_filtro])}")
    
    mensaje_base = campana.plantilla.cuerpo_mensaje
    
    # Obtener URL de imagen si la plantilla la tiene
    url_imagen = None
    if campana.plantilla.tiene_imagen and campana.plantilla.url_imagen:
        url_imagen = campana.plantilla.url_imagen
    
    # Determinar proveedor (de la plantilla o de la campaña)
    proveedor = campana.plantilla.proveedor if hasattr(campana.plantilla, 'proveedor') else campana.proveedor
    twilio_template_sid = getattr(campana.plantilla, 'twilio_template_sid', None)
    
    resultados = {
        "total": destinatarios.count(),
        "exitosos": 0,
        "fallidos": 0
    }

    print(f"🚀 INICIANDO CAMPAÑA: {campana.nombre}")
    print(f"📱 Proveedor: {campana.plantilla.get_proveedor_display() if hasattr(campana.plantilla, 'get_proveedor_display') else proveedor}")
    if url_imagen:
        print(f"📸 Con imagen: {url_imagen}")
    if twilio_template_sid:
        print(f"📋 Template SID: {twilio_template_sid}")
    
    for estudiante in destinatarios:
        try:
            # 1. Personalización del mensaje
            mensaje_personalizado = mensaje_base.replace("{nombre}", estudiante.nombre)
            
            # 2. Seleccionar función de envío según proveedor
            if proveedor == 'twilio':
                # Si tiene template_sid, usar template
                if twilio_template_sid:
                    from twilio.rest import Client
                    import os
                    
                    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
                    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
                    client = Client(account_sid, auth_token)
                    
                    telefono = estudiante.telefono
                    if not telefono.startswith('+'):
                        telefono = f'+{telefono}'
                    if not telefono.startswith('whatsapp:'):
                        telefono = f'whatsapp:{telefono}'
                    
                    message = client.messages.create(
                        content_sid=twilio_template_sid,
                        from_="whatsapp:+14155238886",
                        to=telefono
                    )
                    resultado = {
                        'success': True,
                        'mensaje_id': message.sid,
                        'response': {'status': message.status}
                    }
                else:
                    # Mensaje libre con Twilio
                    resultado = enviar_whatsapp_twilio(
                        telefono=estudiante.telefono,
                        texto=mensaje_personalizado,
                        url_imagen=url_imagen
                    )
            else:  # meta (default)
                resultado = enviar_whatsapp(
                    telefono=estudiante.telefono,
                    texto=mensaje_personalizado,
                    url_imagen=url_imagen
                )
            
            if resultado['success']:
                # 3. Guardar Log de Éxito
                EnvioLog.objects.create(
                    campana=campana,
                    estudiante=estudiante,
                    estado='ENVIADO',
                    respuesta_api=f"Message ID: {resultado.get('mensaje_id', 'N/A')}"
                )
                resultados["exitosos"] += 1
                print(f"✅ Enviado a {estudiante.nombre}")
            else:
                raise Exception(str(resultado.get('response', 'Error desconocido')))

        except Exception as e:
            # 4. Guardar Log de Fallo
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='FALLIDO',
                respuesta_api=str(e)
            )
            resultados["fallidos"] += 1
            print(f"❌ {estudiante.nombre}: {str(e)}")

    print(f"\n✅ CAMPAÑA COMPLETADA: {campana.nombre}")
    print(f"   Total: {resultados['total']} | Exitosos: {resultados['exitosos']} | Fallidos: {resultados['fallidos']}")
    return resultados


# ============================================================
# FUNCIONES PARA MENSAJES PROACTIVOS (NUEVO)
# ============================================================

def enviar_mensaje_proactivo_inteligente(estudiante, tipo_mensaje, **kwargs):
    """
    Envía mensaje proactivo al estudiante respetando reglas de WhatsApp Business API
    
    REGLA IMPORTANTE:
    - Si el usuario NO ha respondido en las últimas 24 horas: Usar Template aprobado
    - Si el usuario SÍ respondió en las últimas 24 horas: Puede ser texto libre
    
    Args:
        estudiante: Objeto Estudiante
        tipo_mensaje: 'bienvenida', 'recordatorio', 'tarea', 'progreso'
        **kwargs: Variables específicas del mensaje
    
    Returns:
        dict con 'exito', 'metodo_usado' ('template' o 'texto_libre'), y 'mensaje_id' o 'error'
    
    Ejemplos:
        # Bienvenida
        enviar_mensaje_proactivo_inteligente(
            estudiante=estudiante,
            tipo_mensaje='bienvenida'
        )
        
        # Recordatorio
        enviar_mensaje_proactivo_inteligente(
            estudiante=estudiante,
            tipo_mensaje='recordatorio',
            materia='Matemáticas',
            hora='10:00am',
            tema='Ecuaciones cuadráticas'
        )
        
        # Nueva tarea
        enviar_mensaje_proactivo_inteligente(
            estudiante=estudiante,
            tipo_mensaje='tarea',
            materia='Historia',
            fecha_entrega='25 de Diciembre',
            dias_restantes='2'
        )
    """
    from .models import WhatsappLog
    from .twilio_templates import (
        enviar_bienvenida, 
        enviar_recordatorio_clase,
        enviar_notificacion_tarea,
        enviar_reporte_progreso,
        enviar_mensaje_proactivo_simple
    )
    
    try:
        # Verificar ventana de 24 horas
        ventana_abierta = verificar_ventana_24h(estudiante.telefono)
        
        if ventana_abierta:
            # PUEDE USAR TEXTO LIBRE
            logger.info(f"Ventana 24h abierta para {estudiante.telefono}. Usando texto libre.")
            
            # Generar mensajes de texto libre según tipo
            if tipo_mensaje == 'bienvenida':
                texto = f"""¡Hola {estudiante.nombre}! 👋 Bienvenido a Eki Educación.

Soy tu asistente virtual inteligente. Puedo ayudarte con:

✅ Consultar tus tareas pendientes
✅ Ver tu horario de clases
✅ Revisar tu progreso académico
✅ Recordatorios importantes

¿En qué puedo ayudarte hoy?"""
            
            elif tipo_mensaje == 'recordatorio':
                materia = kwargs.get('materia', 'tu clase')
                hora = kwargs.get('hora', 'pronto')
                tema = kwargs.get('tema', '')
                
                texto = f"""¡Hola {estudiante.nombre}! 🎓

Recordatorio: Tienes clase de {materia} hoy a las {hora}.

📍 Tema: {tema}

¿Necesitas ayuda con algo antes de la clase?"""
            
            elif tipo_mensaje == 'tarea':
                materia = kwargs.get('materia', 'una materia')
                fecha_entrega = kwargs.get('fecha_entrega', 'pronto')
                dias_restantes = kwargs.get('dias_restantes', 'pocos')
                
                texto = f"""📚 Nueva tarea asignada

Hola {estudiante.nombre},

Se ha asignado una nueva tarea:

📖 Materia: {materia}
📅 Fecha de entrega: {fecha_entrega}
⏰ Faltan {dias_restantes} días

Responde "detalles" para ver más información."""
            
            elif tipo_mensaje == 'progreso':
                semana = kwargs.get('semana', 'esta semana')
                tareas = kwargs.get('tareas_completadas', 'N/A')
                clases = kwargs.get('clases_asistidas', 'N/A')
                promedio = kwargs.get('promedio', 'N/A')
                mensaje_motivacional = kwargs.get('mensaje_motivacional', '¡Sigue así!')
                
                texto = f"""📊 Reporte Semanal - {semana}

Hola {estudiante.nombre},

Tu progreso esta semana:

✅ Tareas completadas: {tareas}
📚 Clases asistidas: {clases}
🎯 Promedio: {promedio}

¡{mensaje_motivacional}!

¿Quieres ver detalles?"""
            
            else:
                texto = f"Hola {estudiante.nombre}, tienes una nueva notificación en Eki Educación."
            
            # Enviar texto libre
            resultado = enviar_mensaje_proactivo_simple(estudiante.telefono, texto)
            resultado['metodo_usado'] = 'texto_libre'
            
            return resultado
        
        else:
            # DEBE USAR TEMPLATE APROBADO
            logger.info(f"Ventana 24h cerrada para {estudiante.telefono}. Usando template.")
            
            if tipo_mensaje == 'bienvenida':
                resultado = enviar_bienvenida(estudiante.telefono, estudiante.nombre)
            
            elif tipo_mensaje == 'recordatorio':
                resultado = enviar_recordatorio_clase(
                    telefono=estudiante.telefono,
                    nombre=estudiante.nombre,
                    materia=kwargs.get('materia', 'tu clase'),
                    hora=kwargs.get('hora', 'pronto'),
                    tema=kwargs.get('tema', 'Revisar contenido')
                )
            
            elif tipo_mensaje == 'tarea':
                resultado = enviar_notificacion_tarea(
                    telefono=estudiante.telefono,
                    nombre=estudiante.nombre,
                    materia=kwargs.get('materia', 'General'),
                    fecha_entrega=kwargs.get('fecha_entrega', 'Próximamente'),
                    dias_restantes=kwargs.get('dias_restantes', 'Pocos')
                )
            
            elif tipo_mensaje == 'progreso':
                resultado = enviar_reporte_progreso(
                    telefono=estudiante.telefono,
                    semana=kwargs.get('semana', 'esta semana'),
                    nombre=estudiante.nombre,
                    tareas_completadas=kwargs.get('tareas_completadas', '0'),
                    clases_asistidas=kwargs.get('clases_asistidas', '0'),
                    promedio=kwargs.get('promedio', 'N/A'),
                    mensaje_motivacional=kwargs.get('mensaje_motivacional', '¡Sigue adelante!')
                )
            
            else:
                return {
                    'exito': False,
                    'error': f'Tipo de mensaje desconocido: {tipo_mensaje}'
                }
            
            resultado['metodo_usado'] = 'template'
            return resultado
    
    except Exception as e:
        logger.error(f"Error en enviar_mensaje_proactivo_inteligente: {str(e)}")
        return {
            'exito': False,
            'error': str(e)
        }


def verificar_ventana_24h(telefono):
    """
    Verifica si el usuario ha respondido en las últimas 24 horas
    (ventana de sesión abierta de WhatsApp Business API)
    
    Args:
        telefono: Número de teléfono a verificar
    
    Returns:
        bool: True si la ventana está abierta, False si cerrada
    """
    from .models import WhatsappLog
    
    # Intentar desde cache primero (optimización)
    cache_key = f'ventana_24h_{telefono}'
    resultado_cache = cache.get(cache_key)
    
    if resultado_cache is not None:
        return resultado_cache
    
    # Buscar último mensaje RECIBIDO del usuario
    ultimo_mensaje_recibido = WhatsappLog.objects.filter(
        telefono=telefono,
        tipo_mensaje='recibido'
    ).order_by('-fecha_envio').first()
    
    if not ultimo_mensaje_recibido:
        # Usuario nunca ha respondido
        cache.set(cache_key, False, 300)  # Cache 5 minutos
        return False
    
    # Calcular diferencia de tiempo
    ahora = timezone.now()
    diferencia = ahora - ultimo_mensaje_recibido.fecha_envio
    
    ventana_abierta = diferencia < timedelta(hours=24)
    
    # Cachear resultado (5 minutos)
    cache.set(cache_key, ventana_abierta, 300)
    
    return ventana_abierta


def enviar_bienvenida_nuevo_estudiante(estudiante):
    """
    Envía mensaje de bienvenida a un estudiante recién registrado
    
    Args:
        estudiante: Objeto Estudiante
    
    Returns:
        dict con resultado del envío
    """
    return enviar_mensaje_proactivo_inteligente(
        estudiante=estudiante,
        tipo_mensaje='bienvenida'
    )


def enviar_recordatorio_clase_proxima(estudiante, clase):
    """
    Envía recordatorio de clase próxima
    
    Args:
        estudiante: Objeto Estudiante
        clase: Objeto Clase con información
    
    Returns:
        dict con resultado del envío
    """
    from django.utils.dateformat import format as date_format
    
    hora = date_format(clase.fecha_hora, 'h:ia') if hasattr(clase, 'fecha_hora') else 'pronto'
    
    return enviar_mensaje_proactivo_inteligente(
        estudiante=estudiante,
        tipo_mensaje='recordatorio',
        materia=clase.materia if hasattr(clase, 'materia') else 'tu clase',
        hora=hora,
        tema=clase.tema if hasattr(clase, 'tema') else 'Revisar contenido'
    )


def enviar_notificacion_nueva_tarea(estudiante, tarea):
    """
    Envía notificación de tarea asignada
    
    Args:
        estudiante: Objeto Estudiante
        tarea: Objeto Tarea con información
    
    Returns:
        dict con resultado del envío
    """
    from django.utils.dateformat import format as date_format
    
    fecha_entrega = date_format(tarea.fecha_entrega, 'd \de F') if hasattr(tarea, 'fecha_entrega') else 'pronto'
    
    # Calcular días restantes
    if hasattr(tarea, 'fecha_entrega'):
        dias = (tarea.fecha_entrega - timezone.now().date()).days
        dias_restantes = str(max(0, dias))
    else:
        dias_restantes = 'varios'
    
    return enviar_mensaje_proactivo_inteligente(
        estudiante=estudiante,
        tipo_mensaje='tarea',
        materia=tarea.materia if hasattr(tarea, 'materia') else 'General',
        fecha_entrega=fecha_entrega,
        dias_restantes=dias_restantes
    )