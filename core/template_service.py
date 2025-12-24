"""
Sistema de envío de plantillas de Twilio.
Gestiona Content Templates para mensajes formales (bienvenida, notificaciones).
"""
import os
from twilio.rest import Client
from django.conf import settings
from .models import Plantilla, WhatsappLog, Estudiante


class TwilioTemplateService:
    """Servicio para enviar plantillas de Twilio Content Templates"""
    
    def __init__(self):
        self.account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        self.auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        self.from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError("Faltan credenciales de Twilio en .env")
        
        self.client = Client(self.account_sid, self.auth_token)
    
    def enviar_plantilla(self, telefono: str, plantilla_nombre: str, variables: dict = None):
        """
        Envía una plantilla de Twilio Content Template.
        
        Args:
            telefono: número de destino (formato: 573001234567)
            plantilla_nombre: nombre interno de la plantilla en BD
            variables: dict con variables {"1": "Juan", "2": "Python"}
            
        Returns:
            message_sid del mensaje enviado
            
        Example:
            service = TwilioTemplateService()
            service.enviar_plantilla(
                "573001234567",
                "bienvenida",
                {"1": "Juan"}
            )
        """
        # 1. Buscar plantilla en BD
        try:
            plantilla = Plantilla.objects.get(
                nombre_interno=plantilla_nombre,
                activa=True,
                proveedor='twilio'
            )
        except Plantilla.DoesNotExist:
            raise ValueError(f"Plantilla '{plantilla_nombre}' no existe o no está activa")
        
        if not plantilla.twilio_template_sid:
            raise ValueError(f"Plantilla '{plantilla_nombre}' no tiene Content SID configurado")
        
        # 2. Preparar variables (merge con defaults de la plantilla)
        content_variables = {}
        if plantilla.twilio_variables:
            content_variables = plantilla.twilio_variables.copy()
        
        if variables:
            content_variables.update(variables)
        
        # 3. Formatear número de teléfono
        if not telefono.startswith('+'):
            telefono = f'+{telefono}'
        
        # 4. Enviar mensaje con Twilio
        try:
            message = self.client.messages.create(
                content_sid=plantilla.twilio_template_sid,
                content_variables=content_variables if content_variables else None,
                from_=self.from_number,
                to=f"whatsapp:{telefono}"
            )
            
            # 5. Registrar en log
            WhatsappLog.objects.create(
                telefono=telefono.replace('+', '').replace('whatsapp:', ''),
                mensaje=f"📋 Plantilla: {plantilla.nombre_interno}",
                mensaje_id=message.sid,
                estado='SENT'
            )
            
            print(f"✅ Plantilla enviada: {plantilla.nombre_interno} → {telefono}")
            return message.sid
            
        except Exception as e:
            # Registrar error en log
            WhatsappLog.objects.create(
                telefono=telefono.replace('+', '').replace('whatsapp:', ''),
                mensaje=f"❌ Error plantilla: {plantilla.nombre_interno}",
                estado='ERROR'
            )
            raise Exception(f"Error al enviar plantilla: {str(e)}")
    
    def enviar_bienvenida(self, telefono: str, nombre: str = None):
        """
        Envía plantilla de bienvenida a un nuevo estudiante.
        
        Args:
            telefono: número del estudiante
            nombre: nombre del estudiante (opcional, se busca en BD)
        """
        # Buscar nombre si no se proporciona
        if not nombre:
            try:
                estudiante = Estudiante.objects.get(telefono=telefono)
                nombre = estudiante.nombre
            except Estudiante.DoesNotExist:
                nombre = "Estudiante"
        
        # Enviar plantilla de bienvenida
        return self.enviar_plantilla(
            telefono,
            "bienvenida",  # Nombre interno de la plantilla
            {"1": nombre}
        )
    
    def enviar_notificacion_clase(self, telefono: str, nombre: str, materia: str, duracion: str = "45 minutos"):
        """
        Envía notificación de nueva clase disponible.
        
        Args:
            telefono: número del estudiante
            nombre: nombre del estudiante
            materia: nombre de la materia/clase
            duracion: duración de la clase
        """
        return self.enviar_plantilla(
            telefono,
            "nueva_clase",
            {
                "1": nombre,
                "2": materia,
                "3": duracion
            }
        )
    
    def enviar_recordatorio(self, telefono: str, nombre: str, tarea: str, fecha_vence: str):
        """
        Envía recordatorio de tarea pendiente.
        
        Args:
            telefono: número del estudiante
            nombre: nombre del estudiante
            tarea: descripción de la tarea
            fecha_vence: fecha de vencimiento
        """
        return self.enviar_plantilla(
            telefono,
            "recordatorio",
            {
                "1": nombre,
                "2": tarea,
                "3": fecha_vence
            }
        )
    
    def enviar_mensaje_simple(self, telefono: str, texto: str, media_url: str = None):
        """
        Envía mensaje simple sin plantilla (conversaciones IA).
        
        Args:
            telefono: número de destino
            texto: texto del mensaje
            media_url: URL opcional de imagen/video
        """
        if not telefono.startswith('+'):
            telefono = f'+{telefono}'
        
        try:
            kwargs = {
                'body': texto,
                'from_': self.from_number,
                'to': f"whatsapp:{telefono}"
            }
            
            if media_url:
                kwargs['media_url'] = [media_url]
            
            message = self.client.messages.create(**kwargs)
            
            # Registrar en log
            WhatsappLog.objects.create(
                telefono=telefono.replace('+', '').replace('whatsapp:', ''),
                mensaje=texto,
                mensaje_id=message.sid,
                estado='SENT'
            )
            
            return message.sid
            
        except Exception as e:
            print(f"Error al enviar mensaje: {str(e)}")
            raise


# Funciones helper para uso fácil

def enviar_bienvenida(telefono: str, nombre: str = None):
    """
    Atajo para enviar bienvenida.
    
    Usage:
        from core.template_service import enviar_bienvenida
        enviar_bienvenida("573001234567", "Juan")
    """
    service = TwilioTemplateService()
    return service.enviar_bienvenida(telefono, nombre)


def enviar_plantilla(telefono: str, plantilla: str, variables: dict = None):
    """
    Atajo para enviar cualquier plantilla.
    
    Usage:
        from core.template_service import enviar_plantilla
        enviar_plantilla("573001234567", "recordatorio", {"1": "Juan", "2": "Tarea 1"})
    """
    service = TwilioTemplateService()
    return service.enviar_plantilla(telefono, plantilla, variables)


def enviar_mensaje_ia(telefono: str, texto: str):
    """
    Atajo para enviar respuestas del agente IA.
    
    Usage:
        from core.template_service import enviar_mensaje_ia
        enviar_mensaje_ia("573001234567", "¡Hola! ¿Cómo puedo ayudarte?")
    """
    service = TwilioTemplateService()
    return service.enviar_mensaje_simple(telefono, texto)
