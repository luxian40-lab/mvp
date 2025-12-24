from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
import re
import openpyxl # <--- Nueva librería
import os
from django.db import IntegrityError

# 1. ESTUDIANTE
class Estudiante(models.Model):
    nombre = models.CharField(max_length=100, db_index=True)  # Índice para búsquedas
    telefono = models.CharField(max_length=20, unique=True, db_index=True)  # Índice único
    activo = models.BooleanField(default=True, db_index=True)  # Filtrar activos rápido
    fecha_registro = models.DateTimeField(auto_now_add=True, db_index=True)
    etiquetas = models.ManyToManyField('Etiqueta', blank=True, related_name='estudiantes', verbose_name='Etiquetas')

    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'
        ordering = ['-fecha_registro']
        indexes = [
            models.Index(fields=['telefono', 'activo']),  # Búsquedas comunes
            models.Index(fields=['activo', '-fecha_registro']),  # Dashboard
        ]

    def clean(self):
        """Limpieza y validación de teléfono para producción"""
        # Limpieza de teléfono
        numero = re.sub(r'\D', '', str(self.telefono))
        
        # Agregar código de país si es número colombiano de 10 dígitos
        if len(numero) == 10:
            numero = f"57{numero}"
        
        # Validación estricta para producción
        if not (10 <= len(numero) <= 15):
            raise ValidationError(f"Teléfono inválido: {numero}. Debe tener entre 10 y 15 dígitos.")
        
        self.telefono = numero

    def save(self, *args, **kwargs):
        """Guardar con validación automática"""
        if not kwargs.pop('skip_validation', False):
            self.clean()
        super().save(*args, **kwargs)

    def __str__(self): 
        return f"{self.nombre} ({self.telefono})"


# 1b. ETIQUETA (para segmentación)
class Etiqueta(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    color = models.CharField(max_length=50, default='#667eea', verbose_name='Color')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    
    class Meta:
        verbose_name = 'Etiqueta'
        verbose_name_plural = 'Etiquetas'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre

# 2. PLANTILLA
class Plantilla(models.Model):
    """
    Plantilla de mensajes para WhatsApp/SMS.
    Usado SOLO para mensajes formales de entrada (bienvenida, notificaciones).
    Las conversaciones reales se manejan con el Agente IA.
    """
    nombre_interno = models.CharField(max_length=100, verbose_name='Nombre interno')
    cuerpo_mensaje = models.TextField(verbose_name='Contenido del mensaje', help_text='Usa {{nombre}} para personalizar')
    
    # Proveedor de mensajería
    PROVEEDOR_CHOICES = [
        ('meta', 'Meta WhatsApp Cloud API'),
        ('twilio', 'Twilio WhatsApp'),
    ]
    proveedor = models.CharField(
        max_length=20, 
        choices=PROVEEDOR_CHOICES, 
        default='twilio',
        help_text='Selecciona el proveedor de mensajería',
        verbose_name='Proveedor'
    )
    
    # Template SID de Twilio (Content Template)
    twilio_template_sid = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='Content Template SID de Twilio (ej: HXb4df6277ff3ad9a5b6c68993fed6ced8)',
        verbose_name='Content SID (Twilio)'
    )
    
    # Variables para Content Templates
    twilio_variables = models.JSONField(
        blank=True,
        null=True,
        help_text='Variables del template en formato JSON: {"1": "nombre", "2": "materia"}',
        verbose_name='Variables del template'
    )
    
    # Tipo de contenido
    TIPO_CONTENIDO_CHOICES = [
        ('texto', '📝 Solo Texto'),
        ('imagen', '🖼️ Con Imagen'),
        ('video', '🎥 Con Video'),
        ('archivo', '📎 Con Archivo'),
    ]
    tipo_contenido = models.CharField(
        max_length=20,
        choices=TIPO_CONTENIDO_CHOICES,
        default='texto',
        verbose_name='Tipo de contenido'
    )
    
    # Media (imagen, video, archivo)
    url_media = models.URLField(
        max_length=500, 
        blank=True, 
        null=True, 
        help_text="URL del archivo multimedia (imagen, video, documento)",
        verbose_name='URL de media'
    )
    
    # Mantener compatibilidad con código antiguo
    @property
    def tiene_imagen(self):
        return self.tipo_contenido in ['imagen', 'video']
    
    @property
    def url_imagen(self):
        return self.url_media
    
    # Metadata
    activa = models.BooleanField(default=True, verbose_name='Activa', help_text='¿Esta plantilla está activa?')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name='Última modificación')
    
    class Meta:
        verbose_name = 'Plantilla de Mensaje'
        verbose_name_plural = 'Plantillas de Mensajes'
        ordering = ['-fecha_modificacion']
    
    def __str__(self): 
        emoji = {
            'texto': '📝',
            'imagen': '🖼️',
            'video': '🎥',
            'archivo': '📎'
        }.get(self.tipo_contenido, '📝')
        return f"{emoji} {self.nombre_interno} ({self.get_proveedor_display()})"

# 3. CAMPAÑA
class Campana(models.Model):
    nombre = models.CharField(max_length=100)
    
    # NUEVO CAMPO: Subir Excel
    archivo_excel = models.FileField(
        upload_to='excels/', 
        blank=True, null=True,
        help_text="Sube un archivo .xlsx con columnas: 'Nombre' y 'Telefono'. Se agregarán automáticamente."
    )
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT)
    destinatarios = models.ManyToManyField(Estudiante, blank=True) # blank=True para permitir guardar sin seleccionar manual
    
    # Filtro por etiquetas
    filtro_etiquetas = models.ManyToManyField('Etiqueta', blank=True, related_name='campanas', verbose_name='Filtrar por etiquetas',
                                              help_text='Si seleccionas etiquetas, solo se enviarán mensajes a estudiantes con AL MENOS UNA de estas etiquetas')

    # Canal de envío (sms, email, voz, whatsapp)
    CANAL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('voz', 'Voz'),
    ]
    canal_envio = models.CharField(max_length=20, choices=CANAL_CHOICES, default='whatsapp')
    
    # Proveedor de envío
    PROVEEDOR_CHOICES = [
        ('meta', 'Meta WhatsApp Cloud API'),
        ('twilio_sms', 'Twilio SMS'),
        ('twilio_whatsapp', 'Twilio WhatsApp'),
    ]
    proveedor = models.CharField(max_length=20, choices=PROVEEDOR_CHOICES, default='meta', help_text='Proveedor de mensajería')

    # Línea de origen (opcional)
    linea_origen = models.ForeignKey('Linea', null=True, blank=True, on_delete=models.SET_NULL)

    # Envío programado
    fecha_programada = models.DateTimeField(blank=True, null=True)

    ejecutada = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Campaña'
        verbose_name_plural = 'Campañas'


# 3b. LINEAS (líneas de envío, e.g., cuentas de WhatsApp)
class Linea(models.Model):
    nombre = models.CharField(max_length=100, help_text='Etiqueta de la línea, p.ej. FKWhatsapp')
    numero = models.CharField(max_length=30, help_text='Número de la línea, p.ej. +573208198063')

    def __str__(self):
        return f"{self.nombre} ({self.numero})"

# 4. LOGS
class EnvioLog(models.Model):
    campana = models.ForeignKey(Campana, on_delete=models.CASCADE)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, default='PENDIENTE')
    
    # 👇 ESTA ES LA LÍNEA QUE FALTABA, AGRÉGALA:
    respuesta_api = models.TextField(blank=True, null=True, help_text="Respuesta del servidor")
    
    fecha_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.estado}"


# Registro de mensajes enviados/recibidos por WhatsApp
class WhatsappLog(models.Model):
    """Registro REAL de todos los mensajes de WhatsApp (enviados y recibidos)"""
    TIPO_CHOICES = [
        ('SENT', 'Enviado'),
        ('INCOMING', 'Recibido'),
    ]
    
    telefono = models.CharField(max_length=30)
    mensaje = models.TextField(blank=True, null=True)
    mensaje_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='SENT')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje WhatsApp"
        verbose_name_plural = "💬 Mensajes WhatsApp (REAL)"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.telefono} - {self.tipo} ({self.fecha.strftime('%d/%m %H:%M')})"


# Procesar Excel subido: crear Estudiantes y agregarlos a la campaña
@receiver(post_save, sender=Campana)
def procesar_excel_campana(sender, instance, created, **kwargs):
    # Si hay un archivo y no hay destinatarios, intentamos cargarlo
    if instance.archivo_excel and instance.destinatarios.count() == 0:
        try:
            file_path = instance.archivo_excel.path
            if os.path.exists(file_path):
                wb = openpyxl.load_workbook(file_path)
                sheet = wb.active
                # Esperamos: columna A = Nombre, columna B = Telefono
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if not row: 
                        continue
                    nombre = str(row[0]).strip() if row[0] is not None else ''
                    telefono = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
                    if not telefono:
                        continue
                    # Normalizamos y creamos/obtenemos estudiante
                    try:
                        estudiante, created_est = Estudiante.objects.get_or_create(telefono=telefono, defaults={'nombre': nombre})
                    except IntegrityError:
                        # Si falla por formato, intentamos limpiar y reintentar
                        telefono_clean = re.sub(r'\D', '', telefono)
                        if len(telefono_clean) == 10:
                            telefono_clean = f"57{telefono_clean}"
                        estudiante, created_est = Estudiante.objects.get_or_create(telefono=telefono_clean, defaults={'nombre': nombre})
                    # Añadimos a destinatarios
                    instance.destinatarios.add(estudiante)
                # Guardar para asegurar M2M
                instance.save()
        except Exception:
            # Si falla la lectura del excel no queremos romper el flujo de guardado
            pass