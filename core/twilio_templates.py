"""
Servicio para enviar Templates de Twilio (mensajes proactivos)
"""

import os
from twilio.rest import Client
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def enviar_template_twilio(telefono, template_name, variables):
    """
    Envía un Content Template de Twilio con variables
    
    Args:
        telefono: Número de WhatsApp (formato: +573001234567)
        template_name: Nombre del template ('bienvenida', 'recordatorio', 'tarea', 'progreso')
        variables: Lista de valores para las variables del template
    
    Returns:
        dict con 'exito' (bool) y 'mensaje_id' o 'error'
    
    Ejemplo:
        enviar_template_twilio(
            telefono="+573001234567",
            template_name="bienvenida",
            variables=["Juan Pérez"]
        )
    """
    try:
        # Configuración Twilio
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
        
        if not account_sid or not auth_token:
            logger.error("Credenciales de Twilio no configuradas")
            return {
                'exito': False,
                'error': 'Credenciales de Twilio no configuradas'
            }
        
        # Mapeo de templates a Content SIDs
        template_sids = {
            'bienvenida': os.getenv('TWILIO_TEMPLATE_BIENVENIDA'),
            'recordatorio': os.getenv('TWILIO_TEMPLATE_RECORDATORIO'),
            'tarea': os.getenv('TWILIO_TEMPLATE_TAREA'),
            'progreso': os.getenv('TWILIO_TEMPLATE_PROGRESO'),
        }
        
        content_sid = template_sids.get(template_name)
        
        if not content_sid:
            logger.error(f"Template '{template_name}' no configurado")
            return {
                'exito': False,
                'error': f'Template {template_name} no configurado en .env'
            }
        
        # Formatear número
        if not telefono.startswith('whatsapp:'):
            telefono = f'whatsapp:{telefono}'
        
        # Cliente Twilio
        client = Client(account_sid, auth_token)
        
        # Construir variables del template
        # Twilio espera formato: {"1": "valor1", "2": "valor2"}
        content_variables = {}
        for i, valor in enumerate(variables, start=1):
            content_variables[str(i)] = str(valor)
        
        # Enviar mensaje con template
        message = client.messages.create(
            from_=from_number,
            to=telefono,
            content_sid=content_sid,
            content_variables=content_variables
        )
        
        logger.info(f"Template '{template_name}' enviado a {telefono}. SID: {message.sid}")
        
        return {
            'exito': True,
            'mensaje_id': message.sid,
            'estado': message.status
        }
        
    except Exception as e:
        logger.error(f"Error enviando template a {telefono}: {str(e)}")
        return {
            'exito': False,
            'error': str(e)
        }


def enviar_mensaje_proactivo_simple(telefono, texto):
    """
    Envía mensaje de texto simple (solo funciona dentro de ventana 24h)
    
    Args:
        telefono: Número de WhatsApp
        texto: Texto del mensaje
    
    Returns:
        dict con 'exito' y 'mensaje_id' o 'error'
    """
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
        
        if not account_sid or not auth_token:
            return {
                'exito': False,
                'error': 'Credenciales de Twilio no configuradas'
            }
        
        # Formatear número
        if not telefono.startswith('whatsapp:'):
            telefono = f'whatsapp:{telefono}'
        
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            from_=from_number,
            body=texto,
            to=telefono
        )
        
        logger.info(f"Mensaje simple enviado a {telefono}. SID: {message.sid}")
        
        return {
            'exito': True,
            'mensaje_id': message.sid
        }
        
    except Exception as e:
        logger.error(f"Error enviando mensaje simple: {str(e)}")
        return {
            'exito': False,
            'error': str(e)
        }


# Funciones helper para templates específicos

def enviar_bienvenida(telefono, nombre):
    """
    Envía mensaje de bienvenida a nuevo estudiante
    
    Args:
        telefono: Número WhatsApp del estudiante
        nombre: Nombre del estudiante
    """
    return enviar_template_twilio(
        telefono=telefono,
        template_name='bienvenida',
        variables=[nombre]
    )


def enviar_recordatorio_clase(telefono, nombre, materia, hora, tema):
    """
    Envía recordatorio de clase
    
    Args:
        telefono: Número WhatsApp
        nombre: Nombre del estudiante
        materia: Nombre de la materia
        hora: Hora de la clase (ej: "10:00am")
        tema: Tema de la clase
    """
    return enviar_template_twilio(
        telefono=telefono,
        template_name='recordatorio',
        variables=[nombre, materia, hora, tema]
    )


def enviar_notificacion_tarea(telefono, nombre, materia, fecha_entrega, dias_restantes):
    """
    Envía notificación de nueva tarea
    
    Args:
        telefono: Número WhatsApp
        nombre: Nombre del estudiante
        materia: Materia de la tarea
        fecha_entrega: Fecha de entrega (ej: "25 de Diciembre")
        dias_restantes: Días hasta entrega (ej: "2")
    """
    return enviar_template_twilio(
        telefono=telefono,
        template_name='tarea',
        variables=[nombre, materia, fecha_entrega, dias_restantes]
    )


def enviar_reporte_progreso(telefono, semana, nombre, tareas_completadas, 
                            clases_asistidas, promedio, mensaje_motivacional):
    """
    Envía reporte semanal de progreso
    
    Args:
        telefono: Número WhatsApp
        semana: Número de semana (ej: "Semana 12")
        nombre: Nombre del estudiante
        tareas_completadas: Cantidad de tareas completadas (ej: "8/10")
        clases_asistidas: Cantidad de clases (ej: "4/5")
        promedio: Promedio (ej: "4.5")
        mensaje_motivacional: Mensaje (ej: "¡Excelente trabajo!")
    """
    return enviar_template_twilio(
        telefono=telefono,
        template_name='progreso',
        variables=[semana, nombre, tareas_completadas, clases_asistidas, 
                  promedio, mensaje_motivacional]
    )
