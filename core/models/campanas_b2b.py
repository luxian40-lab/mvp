"""Modelos de campanas b2b (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.models.clientes import Cliente
from core.models.estudiantes import Estudiante


# ========== CAMPAÑAS ÚNICAS (SÍ/NO) ==========
class CampanaUnica(models.Model):
    """Campañas de una sola vez con botones (sí/no)"""
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
        ('completada', 'Completada'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la campaña")
    contenido = models.TextField(verbose_name="Contenido del mensaje", help_text="Texto que acompaña los botones SÍ/NO")
    template_twilio_id = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name="Content SID de Twilio",
        help_text="El SID del template aprobado en Twilio (ej: HX123abc...)"
    )
    
    # Selección de estudiantes (si vacío = todos los del cliente)
    estudiantes = models.ManyToManyField(
        'Estudiante', blank=True,
        verbose_name="Estudiantes destinatarios",
        help_text="Selecciona estudiantes específicos. Si dejas vacío, se enviará a TODOS los estudiantes activos del cliente."
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de envío")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador', verbose_name="Estado")
    
    # Estadísticas
    total_enviados = models.IntegerField(default=0, verbose_name="Total enviados")
    respuestas_si = models.IntegerField(default=0, verbose_name="Respuestas SÍ")
    respuestas_no = models.IntegerField(default=0, verbose_name="Respuestas NO")
    
    class Meta:
        verbose_name = "Campaña Única"
        verbose_name_plural = "Campañas Únicas"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.nombre} - {self.get_estado_display()}"


class RespuestaCampanaUnica(models.Model):
    """Guarda cada respuesta (sí/no) y el número del estudiante"""
    RESPUESTA_CHOICES = [
        ('si', 'Sí'),
        ('no', 'No'),
    ]
    
    campana = models.ForeignKey(CampanaUnica, on_delete=models.CASCADE, related_name='respuestas', verbose_name="Campaña")
    estudiante = models.ForeignKey(Estudiante, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Estudiante")
    
    numero_telefono = models.CharField(max_length=20, verbose_name="Número de teléfono")
    respuesta = models.CharField(max_length=5, choices=RESPUESTA_CHOICES, verbose_name="Respuesta")
    
    fecha_respuesta = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de respuesta")
    mensaje_sid = models.CharField(max_length=100, null=True, blank=True, verbose_name="Message SID de Twilio")
    
    class Meta:
        verbose_name = "Respuesta Campaña Única"
        verbose_name_plural = "Respuestas Campañas Únicas"
        ordering = ['-fecha_respuesta']
        unique_together = ['campana', 'numero_telefono']  # Un estudiante solo responde una vez
    
    def __str__(self):
        return f"{self.numero_telefono} - {self.get_respuesta_display()}"


# ========== PROSPECTOS B2B (Lead Generation) ==========
class ProspectoB2B(models.Model):
    """Prospectos B2B capturados por el bot cuando un número no registrado escribe."""
    ESTADO_CHOICES = [
        ('nuevo', 'Nuevo'),
        ('contactado', 'Contactado'),
        ('en_negociacion', 'En Negociación'),
        ('convertido', 'Convertido a Cliente'),
        ('descartado', 'Descartado'),
    ]
    
    ORIGEN_CHOICES = [
        ('whatsapp_bot', 'Bot WhatsApp'),
        ('web', 'Sitio Web'),
        ('referido', 'Referido'),
        ('otro', 'Otro'),
    ]
    
    telefono = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Teléfono WhatsApp',
        help_text='Número de teléfono del prospecto'
    )
    nombre_contacto = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre del Contacto'
    )
    email = models.EmailField(
        blank=True,
        verbose_name='Email',
        help_text='Correo electrónico del prospecto'
    )
    empresa = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Empresa',
        help_text='Nombre de la empresa del prospecto'
    )
    mensaje_original = models.TextField(
        blank=True,
        verbose_name='Mensaje Original',
        help_text='Primer mensaje que envió el prospecto'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='nuevo',
        verbose_name='Estado del Lead'
    )
    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_CHOICES,
        default='whatsapp_bot',
        verbose_name='Origen'
    )
    notas = models.TextField(
        blank=True,
        verbose_name='Notas de Seguimiento'
    )
    
    # Estado del chat con el prospecto
    esperando_email = models.BooleanField(
        default=False,
        verbose_name='Esperando Email',
        help_text='Si el bot está esperando que el prospecto envíe su email'
    )
    
    fecha_captura = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Captura'
    )
    fecha_ultimo_contacto = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último Contacto'
    )
    
    class Meta:
        verbose_name = 'Prospecto B2B'
        verbose_name_plural = 'Prospectos B2B (Leads)'
        ordering = ['-fecha_captura']
    
    def __str__(self):
        return f"{self.telefono} - {self.empresa or 'Sin empresa'} ({self.get_estado_display()})"


class CampanaB2B(models.Model):
    """Campañas de envío masivo para prospectos B2B — solo envío, sin registro."""
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
    ]
    
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre de la Campaña',
        help_text='Ej: Propuesta Café Huila 2026'
    )
    mensaje = models.TextField(
        verbose_name='Mensaje de texto',
        help_text='Texto del mensaje a enviar. Usa {nombre} para personalizar con el nombre del prospecto.',
        blank=True,
        default=''
    )
    twilio_template_sid = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Content SID de Twilio (opcional)',
        help_text='Si se especifica, se envía este template en lugar del mensaje de texto.'
    )
    url_media = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='URL del PDF/Media (opcional)',
        help_text='URL pública del PDF o archivo a adjuntar. Debe ser accesible públicamente.'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='borrador'
    )
    total_enviados = models.IntegerField(default=0)
    total_errores = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Campaña B2B'
        verbose_name_plural = 'Campañas B2B'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"
