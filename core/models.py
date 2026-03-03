from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
import re
import openpyxl # <--- Nueva librería
import os
from django.db import IntegrityError

# 0. TEMA DE CAMPAÑA (para organizar plantillas y campañas)
class TemaCampana(models.Model):
    """Temas/etiquetas para organizar plantillas y campañas (ej: café, aguacate, maíz)"""
    nombre = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Nombre del tema",
        help_text="Ej: Café, Aguacate, Maíz, Motivación General"
    )
    emoji = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Emoji",
        help_text="Copia y pega uno: ☕ 🥑 🌽 🍌 🍊 🍇 🥔 🥕 🧅 🌶️ 🫘 🥬 🍅 🥒 🥦 🐄 🐔 🐷 🐑 🌱 🌾 🌳 🚜 💧 🌤️"
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción",
        help_text="Descripción opcional del tema"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está desactivado, no aparecerá en las opciones"
    )
    
    class Meta:
        verbose_name = 'Tema de Campaña'
        verbose_name_plural = 'Temas de Campaña'
        ordering = ['nombre']
    
    def __str__(self):
        if self.emoji:
            return f"{self.emoji} {self.nombre}"
        return self.nombre


# 0b. CLIENTE (Organización/Empresa que usa la plataforma)
class Cliente(models.Model):
    """Cliente/Organización que usa la plataforma (cooperativa, empresa, ONG)"""
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del Cliente",
        help_text="Ej: Cooperativa Cafetera del Valle, Fundación Agrícola"
    )
    nit = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="NIT/RUT",
        help_text="Número de identificación tributaria"
    )
    contacto_principal = models.CharField(
        max_length=100,
        verbose_name="Contacto Principal",
        help_text="Nombre de la persona de contacto"
    )
    email = models.EmailField(
        verbose_name="Email",
        help_text="Email de contacto del cliente"
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono"
    )
    numero_whatsapp_autorizado = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Número WhatsApp Autorizado en Meta",
        help_text="Número autorizado en Meta Business para envío masivo (ej: 573001234567)"
    )
    enviar_certificados_email = models.BooleanField(
        default=True,
        verbose_name="Enviar Certificados por Email",
        help_text="Si está activado, se enviarán los certificados de sus estudiantes al email del cliente"
    )
    enlace_grupo_whatsapp = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Enlace de Grupo de WhatsApp",
        help_text="Enlace de invitación al grupo de WhatsApp del cliente (ej: https://chat.whatsapp.com/xxxxx)"
    )
    usar_gamificacion = models.BooleanField(
        default=True,
        verbose_name="Usar Gamificación",
        help_text="Si está activado, los estudiantes de este cliente podrán ver puntos, badges y recompensas. Si está desactivado, solo verán el contenido educativo."
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está inactivo, sus estudiantes no recibirán mensajes"
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name="Notas Internas",
        help_text="Notas para uso interno de eki (no visibles para el cliente)"
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro"
    )
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes (Organizaciones)'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
    
    def total_estudiantes(self):
        """Retorna total de estudiantes activos del cliente"""
        return self.estudiantes.filter(activo=True).count()
    
    def total_cursos(self):
        """Retorna total de cursos asignados al cliente"""
        return self.cursos.count()


# 1. ESTUDIANTE
class Estudiante(models.Model):
    TIPO_DOCUMENTO_CHOICES = [
        ('CC', 'Cédula de Ciudadanía'),
        ('TI', 'Tarjeta de Identidad'),
        ('CE', 'Cédula de Extranjería'),
        ('PP', 'Pasaporte'),
    ]
    
    RANGO_EDAD_CHOICES = [
        ('18-30', '18 a 30 años'),
        ('31-50', '31 a 50 años'),
        ('50+', 'Mayor de 50 años'),
    ]
    
    # === ESTADOS DEL CHAT (Máquina de Estados B2B) ===
    ESTADO_CHAT_CHOICES = [
        ('ESPERANDO_HABEAS_DATA', 'Esperando Habeas Data'),
        ('ESPERANDO_CEDULA', 'Esperando Cédula (2FA)'),
        ('CONFIRMANDO_DATOS', 'Confirmando Datos'),
        ('ESPERANDO_AYUDA_MODIFICAR', 'Esperando Ayuda Modificar Datos'),
        ('ESPERANDO_CORRECCION_DATOS', 'Esperando Corrección Datos'),
        ('ACTIVO', 'Activo'),
        # Estados legacy del onboarding anterior
        ('nuevo', 'Nuevo (legacy)'),
        ('esperando_tipo_doc', 'Esperando tipo doc (legacy)'),
        ('esperando_cedula_legacy', 'Esperando cédula (legacy)'),
        ('esperando_nombre', 'Esperando nombre (legacy)'),
        ('esperando_respuesta_modulo', 'Esperando respuesta módulo'),
        ('esperando_respuesta_tutor_ia', 'Esperando respuesta tutor IA'),
        ('esperando_respuesta_progreso', 'Esperando respuesta progreso'),
        ('esperando_seleccion_curso', 'Esperando selección curso'),
        ('completado', 'Completado (legacy)'),
    ]
    
    tipo_documento = models.CharField(
        max_length=2,
        choices=TIPO_DOCUMENTO_CHOICES,
        default='CC',
        verbose_name='Tipo de Documento',
        help_text='Tipo de documento de identificación'
    )
    cedula = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número de Documento',
        help_text='Número de identificación único (limpio, sin puntos ni espacios)'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre Completo')
    telefono = models.CharField(max_length=20, unique=True, verbose_name='Teléfono WhatsApp')
    
    # UBICACIÓN GEOGRÁFICA
    municipio = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Municipio',
        help_text='Municipio donde reside el estudiante'
    )
    departamento = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Departamento',
        help_text='Departamento de Colombia (Ej: Antioquia, Cundinamarca)'
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Región',
        help_text='Región geográfica (Ej: Zona Norte, Magdalena Medio)'
    )
    ubicacion_detalle = models.TextField(
        blank=True,
        verbose_name='Ubicación Detalle',
        help_text='Vereda, barrio o información adicional de ubicación'
    )
    
    # DATOS DEMOGRÁFICOS
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
        ('NR', 'No Reporta'),
    ]
    genero = models.CharField(
        max_length=2,
        choices=GENERO_CHOICES,
        blank=True,
        default='',
        verbose_name='Género',
        help_text='Género del estudiante'
    )
    edad = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Edad',
        help_text='Edad del estudiante en años'
    )
    rango_edad = models.CharField(
        max_length=10,
        choices=RANGO_EDAD_CHOICES,
        blank=True,
        verbose_name='Rango de Edad',
        help_text='Rango de edad del estudiante (se calcula automáticamente si se proporciona edad)'
    )
    
    # ORGANIZACIÓN (Multi-tenant B2B)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='estudiantes',
        verbose_name='Organización',
        help_text='Organización/Empresa B2B a la que pertenece este estudiante'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    
    # HABEAS DATA - Proteccion de datos personales (Ley 1581 de 2012 - Colombia)
    acepto_terminos = models.BooleanField(
        default=False,
        verbose_name='Aceptó Términos y Condiciones',
        help_text='Indica si el estudiante aceptó la política de tratamiento de datos'
    )
    fecha_aceptacion_terminos = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Aceptación',
        help_text='Fecha y hora en que aceptó los términos'
    )
    
    # MÁQUINA DE ESTADOS B2B (estado_chat reemplaza estado_onboarding)
    estado_chat = models.CharField(
        max_length=50,
        choices=ESTADO_CHAT_CHOICES,
        default='ESPERANDO_HABEAS_DATA',
        verbose_name='Estado del Chat',
        help_text='Estado actual en la máquina de estados B2B del onboarding'
    )
    
    # ONBOARDING LEGACY - mantener para retrocompatibilidad
    estado_onboarding = models.CharField(
        max_length=50,
        default='nuevo',
        verbose_name='Estado Onboarding (Legacy)',
        help_text='nuevo, esperando_tipo_doc, esperando_cedula, esperando_nombre, esperando_respuesta_modulo, completado'
    )
    
    # ANTI-ABUSO IA
    preguntas_ia_restantes = models.IntegerField(
        default=3,
        verbose_name='Preguntas IA Restantes',
        help_text='Máximo de preguntas libres a la IA por módulo (se resetea al completar módulo)'
    )
    
    # CONTEXTO TEMPORAL - Para preguntas de modulo
    contexto_temporal = models.JSONField(
        null=True,
        blank=True,
        help_text='Guarda el módulo_id y pregunta_id actual cuando está respondiendo mini examen'
    )

    @property
    def organizacion(self):
        """Alias para acceder al cliente como 'organizacion' (B2B)"""
        return self.cliente
    
    @organizacion.setter
    def organizacion(self, value):
        self.cliente = value

    def clean(self):
        # Limpieza de teléfono
        numero = re.sub(r'\D', '', str(self.telefono))
        if len(numero) == 10: numero = f"57{numero}"
        
        # Validación
        if not (10 <= len(numero) <= 15):
            pass 
        self.telefono = numero
        
        # Limpieza de cédula (sanitización B2B)
        if self.cedula and not self.cedula.startswith('TEMP_'):
            self.cedula = re.sub(r'[\s\.\-]', '', str(self.cedula))
        
        # Capitalizar nombre
        if self.nombre and self.nombre != 'Usuario':
            self.nombre = self.nombre.strip().title()
        
        # Auto-calcular rango_edad si se proporciona edad
        if self.edad:
            if self.edad < 18:
                self.rango_edad = '18-30'  # Menores se agrupan en el primer rango
            elif 18 <= self.edad <= 30:
                self.rango_edad = '18-30'
            elif 31 <= self.edad <= 50:
                self.rango_edad = '31-50'
            else:
                self.rango_edad = '50+'

    def save(self, *args, **kwargs):
        self.clean() # Forzamos limpieza antes de guardar
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['cedula']),
            models.Index(fields=['telefono']),
        ]

    def __str__(self): 
        return f"{self.nombre} (CC: {self.cedula})"

# 2. PLANTILLA
class Plantilla(models.Model):
    """Plantillas de mensajes personalizables para campañas"""

    CATEGORIA_CHOICES = [
        ('cultivos', 'Cultivos'),
        ('ganaderia', 'Ganadería'),
        ('general_agricola', 'General Agrícola'),
        ('educacion', 'Educación'),
        ('gestion', 'Gestión'),
        ('otro', 'Otro'),
    ]

    nombre_interno = models.CharField(
        max_length=100,
        verbose_name="Nombre de la plantilla",
        help_text="Nombre interno para identificar la plantilla (ej: 'Recordatorio Riego Café')"
    )

    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='cultivos',
        verbose_name="Categoría",
        help_text="Categoría principal de la plantilla"
    )

    emoji = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Emoji",
        help_text="Emoji que representa esta plantilla (se autocompletará según la categoría)"
    )

    cuerpo_mensaje = models.TextField(
        verbose_name="Mensaje",
        help_text="Contenido del mensaje. Usa {nombre} para personalizar con el nombre del estudiante."
    )

    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si está desactivada, no aparecerá en las opciones de campaña"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_modificacion = models.DateTimeField(auto_now=True, null=True, blank=True)

    veces_usada = models.IntegerField(
        default=0,
        verbose_name="Veces usada",
        help_text="Contador automático de veces que se ha usado"
    )
    
    # ==========================================
    # 🔵 TWILIO CONTENT TEMPLATES
    # ==========================================
    twilio_template_sid = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Twilio Content SID",
        help_text="Content SID de Twilio (ej: HX1234...). Obtén esto desde Twilio Console después de crear tu plantilla aprobada."
    )
    twilio_template_nombre = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nombre en Twilio",
        help_text="Nombre de la plantilla en Twilio Console (para referencia)"
    )
    aprobada_twilio = models.BooleanField(
        default=False,
        verbose_name="Aprobada en Twilio",
        help_text="Marca esto cuando tu plantilla esté aprobada en Twilio Console"
    )
    
    # ==========================================
    # Meta WhatsApp (Deprecated - Usando solo Twilio)
    # ==========================================
    meta_template_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="[Deprecated] ID de Plantilla en Meta",
        help_text="No usar - Solo Twilio"
    )
    meta_template_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ('PENDING', 'Pendiente de Revisión'),
            ('APPROVED', 'Aprobada'),
            ('REJECTED', 'Rechazada'),
            ('DISABLED', 'Deshabilitada'),
        ],
        verbose_name="[Deprecated] Estado en Meta",
        help_text="No usar - Solo Twilio"
    )
    meta_template_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="[Deprecated] Nombre en Meta",
        help_text="No usar - Solo Twilio"
    )
    enviada_a_meta = models.BooleanField(
        default=False,
        verbose_name="[Deprecated] Enviada a Meta",
        help_text="No usar - Solo Twilio"
    )
    
    class Meta:
        verbose_name = 'Plantilla de Mensaje'
        verbose_name_plural = 'Plantillas de Mensaje'
        ordering = ['-fecha_modificacion']
    
    def __str__(self):
        emoji = self.emoji or self.get_default_emoji()
        return f"{emoji} {self.nombre_interno}"

    def get_default_emoji(self):
        """Retorna emoji por defecto según la categoría"""
        defaults = {
            'cultivos': '',
            'ganaderia': '',
            'general_agricola': '',
            'educacion': '',
            'gestion': '',
            'otro': ''
        }
        return defaults.get(self.categoria, '')

    def save(self, *args, **kwargs):
        """Autocompletar emoji si está vacío"""
        if not self.emoji:
            self.emoji = self.get_default_emoji()
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        import re
        
        # Validar longitud máxima de WhatsApp (1600 caracteres)
        if len(self.cuerpo_mensaje) > 1600:
            raise ValidationError({
                'cuerpo_mensaje': f'El mensaje es demasiado largo ({len(self.cuerpo_mensaje)} caracteres). WhatsApp tiene un límite de 1600 caracteres.'
            })
        
        # Advertir si usa variables que no existen
        variables_validas = ['{nombre}', '{telefono}', '{curso}']
        variables_encontradas = re.findall(r'\{(\w+)\}', self.cuerpo_mensaje)
        
        for var in variables_encontradas:
            if f'{{{var}}}' not in variables_validas:
                raise ValidationError({
                    'cuerpo_mensaje': f'Variable desconocida: {{{var}}}. Variables válidas: {", ".join(variables_validas)}'
                })
    
    def vista_previa(self):
        """Retorna una vista previa del mensaje"""
        return self.cuerpo_mensaje[:100] + '...' if len(self.cuerpo_mensaje) > 100 else self.cuerpo_mensaje
    
    def incrementar_uso(self):
        """Incrementa el contador de uso"""
        self.veces_usada += 1
        self.save(update_fields=['veces_usada'])

# 3. CAMPAÑA
class Campana(models.Model):
    nombre = models.CharField(max_length=100)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='campanas',
        verbose_name='Cliente',
        help_text='Cliente para el que es esta campaña'
    )
    
    # NUEVO CAMPO: Subir Excel
    archivo_excel = models.FileField(
        upload_to='excels/', 
        blank=True, null=True,
        help_text="Sube un archivo .xlsx con columnas: 'Nombre' y 'Telefono'. Se agregarán automáticamente."
    )
    
    # NUEVO: Categoría de la campaña (para filtrar plantillas)
    CATEGORIA_CHOICES = [
        ('cultivos', 'Cultivos'),
        ('ganaderia', 'Ganadería'),
        ('general_agricola', 'General Agrícola'),
        ('educacion', 'Educación'),
        ('gestion', 'Gestión'),
        ('todas', 'Todas las categorías'),
    ]
    
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='todas',
        verbose_name="Categoría",
        help_text="Filtrar plantillas por categoría. 'Todas' mostrará plantillas de cualquier categoría.",
    )
    
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT, null=True, blank=True)
    
    # Envío directo con Content Template de Twilio (sin Django Plantilla)
    template_twilio_id = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name="Content SID de Twilio",
        help_text="SID del template aprobado en Twilio (ej: HX123abc...). Si se llena, se usa en vez de la plantilla Django."
    )
    
    # NUEVO: Tipo de audiencia (individual o grupo)
    TIPO_AUDIENCIA_CHOICES = [
        ('individual', 'Estudiantes individuales'),
        ('grupo', 'Grupo de estudiantes'),
    ]
    tipo_audiencia = models.CharField(
        max_length=20,
        choices=TIPO_AUDIENCIA_CHOICES,
        default='individual',
        verbose_name='Tipo de audiencia',
        help_text='Selecciona si quieres enviar a estudiantes individuales o a un grupo'
    )
    
    # NUEVO: Grupo de destinatarios (opcional, solo si tipo_audiencia='grupo')
    grupo = models.ForeignKey(
        'GrupoEstudiantes',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Grupo',
        help_text='Selecciona el grupo al que se enviará la campaña',
        related_name='campanas'
    )
    
    destinatarios = models.ManyToManyField(Estudiante, blank=True) # blank=True para permitir guardar sin seleccionar manual

    # Canal de envío (solo WhatsApp)
    CANAL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
    ]
    canal_envio = models.CharField(
        max_length=20, 
        choices=CANAL_CHOICES, 
        default='whatsapp',
        verbose_name='Canal de Envío',
        help_text='Actualmente solo se soporta WhatsApp'
    )

    # Línea de origen (opcional)
    linea_origen = models.ForeignKey('Linea', null=True, blank=True, on_delete=models.SET_NULL)

    # Envío programado
    fecha_programada = models.DateTimeField(blank=True, null=True)

    ejecutada = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    # Estadísticas de envío
    total_enviados = models.IntegerField(default=0, verbose_name="Total enviados")
    respuestas_si = models.IntegerField(default=0, verbose_name="Respuestas SÍ")
    respuestas_no = models.IntegerField(default=0, verbose_name="Respuestas NO")
    
    def get_plantillas_disponibles(self):
        """Retorna plantillas filtradas por el tema de la campaña"""
        if self.tema:
            return Plantilla.objects.filter(temas=self.tema, activa=True)
        return Plantilla.objects.filter(activa=True)

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
    TIPO_CHOICES = [
        ('INCOMING', 'Mensaje Recibido'),
        ('SENT', 'Mensaje Enviado'),
    ]
    
    telefono = models.CharField(max_length=30)
    mensaje = models.TextField(blank=True, null=True)
    mensaje_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    estado = models.CharField(max_length=50, default='PENDING')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='INCOMING')
    fecha = models.DateTimeField(auto_now_add=True)
    estudiante = models.ForeignKey(
        Estudiante, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='mensajes_whatsapp',
        help_text='Estudiante asociado a esta conversación'
    )
    
    # Soporte para mensajes de audio
    es_audio = models.BooleanField(
        default=False,
        help_text='Indica si el mensaje es un audio'
    )
    audio_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='URL del archivo de audio'
    )
    audio_transcripcion = models.TextField(
        blank=True,
        null=True,
        help_text='Transcripción del audio (generada por Whisper)'
    )
    audio_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Ruta local del archivo de audio descargado'
    )
    agente_usado = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Nombre del agente IA que generó la respuesta'
    )
    tema_detectado = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Tema detectado en la conversación (café, aguacate, etc.)'
    )

    # Nuevo: campo para guardar detalles de error Twilio
    error_detalle = models.TextField(
        blank=True,
        null=True,
        help_text='Detalle de error Twilio o del envío (código, mensaje, etc.)'
    )

    def __str__(self):
        return f"{self.telefono} - {self.tipo} - {self.estado} ({self.mensaje_id})"
    
    class Meta:
        verbose_name = 'Registro de WhatsApp'
        verbose_name_plural = 'Historial WhatsApp'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['telefono', '-fecha']),
        ]


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


# ==========================================
# SISTEMA EDUCATIVO DE CURSOS
# ==========================================

class Curso(models.Model):
    """Curso completo (ej: Café, Aguacate, Ganadería)"""
    nombre = models.CharField(max_length=200, help_text="Ej: Café Arábigo")
    descripcion = models.TextField(help_text="Descripción completa del curso")
    emoji = models.CharField(max_length=10, default="", blank=True, help_text="Emoji representativo (opcional)")
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cursos',
        verbose_name='Cliente Específico',
        help_text='Si es para un cliente específico. Dejar vacío = curso general de eki disponible para todos'
    )
    duracion_semanas = models.IntegerField(default=5, help_text="Duración estimada en semanas")
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(default=0, help_text="Orden de visualización")
    
    # GAMIFICACION OPCIONAL
    usar_gamificacion = models.BooleanField(
        default=True,
        verbose_name='Usar Gamificación',
        help_text='Si está activado, se otorgan puntos y badges en este curso'
    )
    
    # GRUPO DE WHATSAPP
    enlace_grupo_whatsapp = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Enlace de Grupo de WhatsApp',
        help_text='Enlace de invitación al grupo de WhatsApp del curso (ej: https://chat.whatsapp.com/xxxxx)'
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self):
        return f"{self.emoji} {self.nombre}"

    def total_modulos(self):
        return self.modulos.count()


class DocumentoRAG(models.Model):
    """
    Documento subido para el sistema RAG Multi-Tenant.
    Cada documento se asocia a un Curso (y por extensión a su Cliente).
    Los agentes IA usan estos documentos para responder preguntas.
    
    Aislamiento: Solo el curso al que pertenece puede acceder a este documento.
    """
    TIPO_CHOICES = [
        ('contenido', 'Contenido del Curso'),
        ('manual', 'Manual / Documentación'),
        ('faq', 'Preguntas Frecuentes'),
        ('guia', 'Guía Práctica'),
        ('normativa', 'Normativa / Regulación'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de indexar'),
        ('indexado', 'Indexado en RAG'),
        ('error', 'Error al indexar'),
    ]

    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='documentos_rag',
        verbose_name='Curso',
        help_text='Curso al que pertenece este documento. Los agentes IA SOLO verán documentos de su curso.'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del documento',
        help_text='Identificador único (ej: Manual_Tomates_v1, FAQ_Café)'
    )
    archivo = models.FileField(
        upload_to='documentos_rag/%Y/%m/',
        verbose_name='Archivo (PDF, DOCX, TXT)',
        help_text='Formatos soportados: .pdf, .docx, .txt'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='contenido',
        verbose_name='Tipo de documento'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado RAG'
    )
    chunks_indexados = models.IntegerField(
        default=0,
        verbose_name='Chunks indexados',
        help_text='Cantidad de fragmentos indexados en la BD vectorial'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción opcional del contenido del documento'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_indexado = models.DateTimeField(null=True, blank=True)
    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Subido por'
    )

    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Documento RAG'
        verbose_name_plural = '📚 Documentos RAG (Base de Conocimiento IA)'
        unique_together = ['curso', 'nombre']
        indexes = [
            models.Index(fields=['curso', 'estado']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.curso.nombre})"

    @property
    def cliente_id(self):
        return self.curso.cliente_id if self.curso.cliente_id else 0

    def indexar(self):
        """Indexa este documento en ChromaDB para el cliente+curso."""
        from core.rag_manager import rag_manager
        from django.utils import timezone
        import os

        if not self.archivo:
            self.estado = 'error'
            self.save(update_fields=['estado'])
            return 0

        try:
            ruta = self.archivo.path
            if not os.path.exists(ruta):
                # Intentar descargar desde S3 a temp
                ruta = self._descargar_temp()
                if not ruta:
                    self.estado = 'error'
                    self.save(update_fields=['estado'])
                    return 0

            n_chunks = rag_manager.procesar_documento(
                cliente_id=self.cliente_id,
                curso_id=self.curso_id,
                ruta_archivo=ruta,
                nombre_documento=self.nombre,
                tipo=self.tipo
            )
            self.chunks_indexados = n_chunks
            self.estado = 'indexado' if n_chunks > 0 else 'error'
            self.fecha_indexado = timezone.now()
            self.save(update_fields=['chunks_indexados', 'estado', 'fecha_indexado'])
            return n_chunks
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAG] Error indexando {self.nombre}: {e}")
            self.estado = 'error'
            self.save(update_fields=['estado'])
            return 0

    def _descargar_temp(self):
        """Descarga archivo desde storage (S3) a /tmp para procesamiento."""
        import tempfile
        try:
            ext = os.path.splitext(self.archivo.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in self.archivo.chunks():
                    tmp.write(chunk)
                return tmp.name
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAG] Error descargando {self.nombre}: {e}")
            return None


class Modulo(models.Model):
    """Módulo dentro de un curso (ej: Módulo 1: Siembra)"""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='modulos')
    numero = models.PositiveIntegerField(
        help_text="Número del módulo (solo enteros positivos: 1, 2, 3, ...)"
    )
    titulo = models.CharField(max_length=200, help_text="Ej: Siembra y Establecimiento")
    descripcion = models.TextField(help_text="Breve descripción del módulo")
    contenido = models.TextField(help_text="Contenido educativo completo del módulo")

    # 🎥 SOPORTE DE VIDEOS Y MULTIMEDIA
    video_url = models.URLField(
        max_length=500, 
        blank=True, 
        null=True,
        help_text="URL del video (YouTube, Vimeo, archivo directo)"
    )
    video_archivo = models.FileField(
        upload_to='videos/lecciones/%Y/%m/',
        blank=True,
        null=True,
        help_text="Archivo de video (MP4, baja resolución recomendada para el campo)"
    )
    video_resolucion = models.CharField(
        max_length=20,
        choices=[
            ('360p', '360p - Baja (recomendado campo)'),
            ('480p', '480p - Media'),
            ('720p', '720p - Alta'),
        ],
        default='360p',
        help_text="Resolución del video (baja = menos datos)"
    )
    imagen_portada_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL de la imagen de portada del módulo"
    )

    def get_video_url_publica(self):
        """
        Genera presigned URL de S3 para el video (bucket privado).
        Usa la misma lógica que obtener_video_url() de response_templates.
        """
        if self.video_url and self.video_url.startswith('http'):
            # Si es S3, convertir a presigned
            if 'eki-produccion.s3' in self.video_url:
                try:
                    import boto3
                    from botocore.config import Config
                    key = self.video_url.split('.amazonaws.com/')[-1].split('?')[0]
                    s3_client = boto3.client('s3', config=Config(signature_version='s3v4', region_name='us-east-2'))
                    return s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': 'eki-produccion', 'Key': key},
                        ExpiresIn=3600
                    )
                except Exception:
                    pass
            return self.video_url
        if self.video_archivo:
            try:
                import boto3
                from botocore.config import Config
                key = self.video_archivo.name.lstrip('/')
                s3_client = boto3.client('s3', config=Config(signature_version='s3v4', region_name='us-east-2'))
                return s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': 'eki-produccion', 'Key': key},
                    ExpiresIn=3600
                )
            except Exception:
                pass
        return None

    archivo_pdf_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Material PDF descargable"
    )
    
    # EXAMEN OBLIGATORIO
    examen_obligatorio = models.BooleanField(
        default=False,
        verbose_name='Examen Obligatorio',
        help_text='El estudiante DEBE aprobar el examen para avanzar al siguiente módulo'
    )
    puntaje_minimo_aprobacion = models.IntegerField(
        default=70,
        verbose_name='Puntaje Mínimo (%)',
        help_text='Porcentaje mínimo para aprobar (0-100)'
    )
    
    duracion_dias = models.IntegerField(default=7, help_text="Días estimados para completar")

    class Meta:
        ordering = ['curso', 'numero']
        verbose_name = "Módulo"
        verbose_name_plural = "Módulos"
        unique_together = ['curso', 'numero']

    def __str__(self):
        return f"{self.curso.nombre} - Módulo {self.numero}: {self.titulo}"


class ProgresoEstudiante(models.Model):
    """Progreso del estudiante en los cursos"""
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='progresos')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    modulo_actual = models.ForeignKey(Modulo, on_delete=models.SET_NULL, null=True, blank=True)
    completado = models.BooleanField(default=False)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Progreso de Estudiante"
        verbose_name_plural = "Progreso de Estudiantes"
        unique_together = ['estudiante', 'curso']

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.curso.nombre}"

    def porcentaje_avance(self):
        """Calcula el porcentaje de avance en el curso"""
        total_modulos = self.curso.modulos.count()
        if total_modulos == 0:
            return 0
        modulos_completados = self.modulos_completados.count()
        return int((modulos_completados / total_modulos) * 100)


class PreguntaModulo(models.Model):
    """Pregunta de validación al final de cada módulo (mini examen)"""
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='preguntas')
    pregunta = models.TextField(help_text="Pregunta de validación del aprendizaje")
    
    # Opciones de respuesta (opción múltiple)
    opcion_a = models.CharField(max_length=500)
    opcion_b = models.CharField(max_length=500)
    opcion_c = models.CharField(max_length=500, blank=True, null=True)
    opcion_d = models.CharField(max_length=500, blank=True, null=True)
    
    respuesta_correcta = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
        help_text="Letra de la respuesta correcta"
    )
    
    explicacion = models.TextField(
        blank=True,
        help_text="Explicación de la respuesta correcta (opcional)"
    )
    
    activa = models.BooleanField(
        default=True,
        help_text="Si está desactivada, no se mostrará"
    )

    class Meta:
        verbose_name = "Pregunta de Módulo"
        verbose_name_plural = "Preguntas de Módulos"
        ordering = ['modulo', 'id']

    def __str__(self):
        return f"{self.modulo.titulo} - {self.pregunta[:50]}..."


class ModuloCompletado(models.Model):
    """Registro de módulos completados por el estudiante"""
    progreso = models.ForeignKey(ProgresoEstudiante, on_delete=models.CASCADE, related_name='modulos_completados')
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    fecha_completado = models.DateTimeField(auto_now_add=True)
    
    # Respuesta al mini examen
    pregunta_respondida = models.ForeignKey(
        PreguntaModulo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Pregunta que se le hizo al completar"
    )
    respuesta_dada = models.CharField(
        max_length=1, 
        blank=True,
        help_text="A, B, C o D"
    )
    respuesta_correcta = models.BooleanField(
        default=False,
        help_text="Si respondió correctamente"
    )

    class Meta:
        verbose_name = "Módulo Completado"
        verbose_name_plural = "Módulos Completados"
        unique_together = ['progreso', 'modulo']

    def __str__(self):
        return f"{self.progreso.estudiante.nombre} completó {self.modulo.titulo}"


class Examen(models.Model):
    """Examen final del curso"""
    curso = models.OneToOneField(Curso, on_delete=models.CASCADE, related_name='examen')
    instrucciones = models.TextField(default="Responde las siguientes preguntas sobre el curso:")
    puntaje_minimo = models.IntegerField(default=70, help_text="Puntaje mínimo para aprobar (0-100)")

    class Meta:
        verbose_name = "Examen"
        verbose_name_plural = "Exámenes"

    def __str__(self):
        return f"Examen de {self.curso.nombre}"

    def total_preguntas(self):
        return self.preguntas.count()


class PreguntaExamen(models.Model):
    """Pregunta del examen"""
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE, related_name='preguntas')
    numero = models.IntegerField(help_text="Número de la pregunta")
    pregunta = models.TextField(help_text="Texto de la pregunta")
    respuesta_correcta = models.TextField(
        help_text="Palabras clave o conceptos esperados en la respuesta (separados por comas)"
    )
    puntos = models.IntegerField(default=20, help_text="Puntos que vale esta pregunta")

    class Meta:
        ordering = ['examen', 'numero']
        verbose_name = "Pregunta de Examen"
        verbose_name_plural = "Preguntas de Examen"
        unique_together = ['examen', 'numero']

    def __str__(self):
        return f"Pregunta {self.numero} - {self.examen.curso.nombre}"


class ResultadoExamen(models.Model):
    """Resultado del examen del estudiante"""
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='resultados_examenes')
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE)
    puntaje = models.IntegerField(default=0, help_text="Puntaje obtenido (0-100)")
    aprobado = models.BooleanField(default=False)
    respuestas = models.JSONField(default=dict, help_text="Diccionario con las respuestas del estudiante")
    feedback = models.TextField(blank=True, help_text="Retroalimentación generada por IA")
    fecha_realizado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Resultado de Examen"
        verbose_name_plural = "Resultados de Exámenes"
        unique_together = ['estudiante', 'examen']

    def __str__(self):
        estado = "Aprobado" if self.aprobado else "Reprobado"
        return f"{self.estudiante.nombre} - {self.examen.curso.nombre} - {self.puntaje}% {estado}"


# ========== SISTEMA DE EVALUACIÓN EDUCATIVA ==========

class ObjetivoCurso(models.Model):
    """Objetivos de aprendizaje del curso (general y específicos)"""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='objetivos')
    tipo = models.CharField(
        max_length=20,
        choices=[('general', 'General'), ('especifico', 'Específico')],
        default='especifico',
        verbose_name='Tipo de Objetivo'
    )
    orden = models.IntegerField(default=0, help_text='Orden del objetivo')
    descripcion = models.TextField(help_text='Descripción del objetivo de aprendizaje')
    peso_evaluacion = models.IntegerField(
        default=25,
        help_text='Peso porcentual de este objetivo en la evaluación (0-100)'
    )
    
    class Meta:
        verbose_name = 'Objetivo de Curso'
        verbose_name_plural = 'Objetivos de Cursos'
        ordering = ['curso', 'orden']
    
    def __str__(self):
        return f"{self.curso.nombre} - {self.get_tipo_display()}: {self.descripcion[:50]}"


class RubricaEvaluacion(models.Model):
    """Rúbrica para evaluar ejercicios y respuestas abiertas"""
    objetivo = models.ForeignKey(
        ObjetivoCurso,
        on_delete=models.CASCADE,
        related_name='rubricas',
        null=True,
        blank=True,
        help_text='Objetivo al que pertenece esta rúbrica'
    )
    nombre = models.CharField(max_length=200, help_text='Nombre de la rúbrica')
    descripcion = models.TextField(help_text='Descripción de qué evalúa')
    criterios = models.JSONField(
        default=dict,
        help_text='Criterios de evaluación en formato JSON: {"criterio1": {"excelente": 100, "bueno": 75, "regular": 50, "insuficiente": 25}}'
    )
    palabras_clave = models.TextField(
        blank=True,
        help_text='Palabras clave esperadas en respuestas correctas (separadas por comas)'
    )
    activa = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Rúbrica de Evaluación'
        verbose_name_plural = 'Rúbricas de Evaluación'
    
    def __str__(self):
        return self.nombre


class EjercicioPractico(models.Model):
    """Ejercicios prácticos y situaciones hipotéticas para evaluación"""
    TIPO_CHOICES = [
        ('numerico', 'Numérico (cálculos)'),
        ('abierto', 'Respuesta Abierta'),
        ('hipotetico', 'Situación Hipotética'),
        ('comprension', '¿Entendiste? (comprensión)'),
    ]
    
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.CASCADE,
        related_name='ejercicios',
        null=True,
        blank=True
    )
    objetivo = models.ForeignKey(
        ObjetivoCurso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ejercicios'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='comprension')
    enunciado = models.TextField(help_text='Texto del ejercicio o situación hipotética')
    contexto_previo = models.TextField(
        blank=True,
        help_text='Contexto o información necesaria para resolver el ejercicio'
    )
    
    # Para ejercicios numéricos
    respuesta_numerica_esperada = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Respuesta numérica correcta (ej: utilidad esperada)'
    )
    tolerancia_porcentual = models.IntegerField(
        default=5,
        help_text='Tolerancia de error aceptable en porcentaje (ej: 5 = ±5%)'
    )
    formula_evaluacion = models.TextField(
        blank=True,
        help_text='Fórmula o criterio para evaluar (ej: "ingresos - costos = utilidad")'
    )
    
    # Para ejercicios abiertos
    rubrica = models.ForeignKey(
        RubricaEvaluacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ejercicios'
    )
    
    puntaje_maximo = models.IntegerField(default=100, help_text='Puntaje máximo del ejercicio')
    tiempo_estimado_minutos = models.IntegerField(
        default=5,
        help_text='Tiempo estimado para completar (minutos)'
    )
    orden = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Ejercicio Práctico'
        verbose_name_plural = 'Ejercicios Prácticos'
        ordering = ['modulo', 'orden']
    
    def __str__(self):
        modulo_str = f"{self.modulo.titulo}" if self.modulo else "Sin módulo"
        return f"{modulo_str} - {self.get_tipo_display()}: {self.enunciado[:50]}"


class RespuestaEjercicio(models.Model):
    """Respuestas de estudiantes a ejercicios prácticos"""
    ejercicio = models.ForeignKey(
        EjercicioPractico,
        on_delete=models.CASCADE,
        related_name='respuestas'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='respuestas_ejercicios'
    )
    intento = models.IntegerField(default=1, help_text='Número de intento')
    
    # Respuesta del estudiante
    respuesta_texto = models.TextField(blank=True, help_text='Respuesta en texto')
    respuesta_numerica = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Respuesta numérica si aplica'
    )
    respuesta_audio_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='URL del audio de respuesta (si respondió por audio)'
    )
    
    # Evaluación
    puntaje_obtenido = models.IntegerField(default=0, help_text='Puntaje obtenido (0-100)')
    es_correcto = models.BooleanField(default=False)
    feedback_ia = models.TextField(
        blank=True,
        help_text='Retroalimentación generada por la IA'
    )
    evaluado_por_ia = models.BooleanField(default=False)
    evaluado_por_docente = models.BooleanField(default=False)
    
    # Metadata
    tiempo_respuesta_segundos = models.IntegerField(
        null=True,
        blank=True,
        help_text='Tiempo que tardó en responder'
    )
    modalidad = models.CharField(
        max_length=10,
        choices=[('texto', 'Texto'), ('audio', 'Audio'), ('mixto', 'Mixto')],
        default='texto'
    )
    fecha_respuesta = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Respuesta a Ejercicio'
        verbose_name_plural = 'Respuestas a Ejercicios'
        ordering = ['-fecha_respuesta']
        unique_together = ['ejercicio', 'estudiante', 'intento']
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.ejercicio.enunciado[:30]} (Intento {self.intento})"


class InteraccionLog(models.Model):
    """Log completo de interacciones para análisis de métricas"""
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='interacciones'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interacciones'
    )
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interacciones'
    )
    
    # Tipo de interacción
    tipo = models.CharField(
        max_length=30,
        choices=[
            ('pregunta', 'Pregunta'),
            ('reto', 'Reto'),
            ('ejercicio', 'Ejercicio'),
            ('examen', 'Examen'),
            ('consulta', 'Consulta General'),
            ('comprension', 'Pregunta de Comprensión'),
        ],
        default='consulta'
    )
    
    # Modalidad y duración
    modalidad = models.CharField(
        max_length=10,
        choices=[('texto', 'Texto'), ('audio', 'Audio'), ('mixto', 'Mixto')],
        default='texto'
    )
    duracion_segundos = models.IntegerField(
        null=True,
        blank=True,
        help_text='Duración de la interacción en segundos'
    )
    
    # Evaluación (si aplica)
    puntaje = models.IntegerField(
        null=True,
        blank=True,
        help_text='Puntaje obtenido (0-100)'
    )
    es_correcto = models.BooleanField(
        null=True,
        blank=True,
        help_text='Si la respuesta fue correcta'
    )
    
    # Contenido
    respuesta_raw = models.TextField(
        blank=True,
        help_text='Respuesta original del estudiante'
    )
    feedback_generado = models.TextField(
        blank=True,
        help_text='Retroalimentación generada'
    )
    intent = models.CharField(
        max_length=50,
        blank=True,
        help_text='Intención detectada (si aplica NLU)'
    )
    
    # Ubicación (para análisis geográfico)
    municipio = models.CharField(
        max_length=100,
        blank=True,
        help_text='Municipio del estudiante'
    )
    
    # Metadata adicional
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Metadata adicional en formato JSON'
    )
    
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Interacción Log'
        verbose_name_plural = 'Logs de Interacciones'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['estudiante', 'fecha']),
            models.Index(fields=['curso', 'fecha']),
            models.Index(fields=['municipio', 'fecha']),
            models.Index(fields=['modalidad', 'fecha']),
        ]
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.get_tipo_display()} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"


# ========== SOPORTE Y ATENCIÓN AL CLIENTE ==========

class SolicitudSoporte(models.Model):
    """Solicitudes de soporte/ayuda de estudiantes y PQRS unificado"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_atencion', 'En Atención'),
        ('resuelta', 'Resuelta'),
        ('cerrada', 'Cerrada'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('baja', '🟢 Baja'),
        ('media', '🟡 Media'),
        ('alta', '🔴 Alta'),
        ('critica', '🚨 Crítica'),
    ]
    
    TIPO_SOLICITUD_CHOICES = [
        ('soporte', '🆘 Soporte (Botón de Pánico)'),
        ('peticion', '📋 Petición'),
        ('queja', '😤 Queja'),
        ('reclamo', '📢 Reclamo'),
        ('sugerencia', '💡 Sugerencia'),
        ('felicitacion', '🌟 Felicitación'),
    ]
    
    tipo_solicitud = models.CharField(
        max_length=20,
        choices=TIPO_SOLICITUD_CHOICES,
        default='soporte',
        verbose_name='Tipo de Solicitud',
        help_text='Tipo: soporte técnico o PQRS'
    )
    asunto = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Asunto',
        help_text='Asunto de la solicitud (opcional para soporte, recomendado para PQRS)'
    )
    curso_relacionado = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Curso Relacionado',
        help_text='Curso relacionado con la solicitud (opcional)'
    )
    calificacion = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Calificación',
        help_text='Del 1 al 5, otorgada por el estudiante'
    )
    comentario_calificacion = models.TextField(
        blank=True,
        verbose_name='Comentario de Calificación'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='solicitudes_soporte',
        verbose_name='Estudiante'
    )
    mensaje_original = models.TextField(
        verbose_name='Mensaje del Estudiante',
        help_text='El mensaje que envió el estudiante pidiendo ayuda'
    )
    keyword_usada = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Palabra Clave',
        help_text='Keyword que activó el soporte (AYUDA, SOPORTE, HUMANO, etc.)'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado'
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default='media',
        verbose_name='Prioridad'
    )
    respuesta = models.TextField(
        blank=True,
        verbose_name='Respuesta del Equipo',
        help_text='Respuesta que se le dio al estudiante'
    )
    atendido_por = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Atendido Por',
        help_text='Nombre del miembro del equipo que atendió'
    )
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Solicitud'
    )
    fecha_atencion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Atención'
    )
    fecha_resolucion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Resolución'
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name='Notas Internas',
        help_text='Notas privadas del equipo (no visible para el estudiante)'
    )
    
    class Meta:
        verbose_name = 'Solicitud de Soporte y PQRS'
        verbose_name_plural = '🆘 Soporte y PQRS'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado', 'prioridad']),
            models.Index(fields=['estudiante', 'fecha_solicitud']),
            models.Index(fields=['tipo_solicitud', 'estado']),
        ]
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.get_estado_display()} - {self.fecha_solicitud.strftime('%d/%m/%Y')}"


# ========== GAMIFICACIÓN ==========
# Importar modelos de gamificación desde archivo separado
from .gamificacion import PerfilGamificacion, Badge, BadgeEstudiante, TransaccionPuntos

# ========== CERTIFICADOS ==========
# Importar modelos de certificados desde archivo separado
from .models_certificados import Certificado, PlantillaCertificado

# ========== AUDITORÍA ==========
# Importar modelos de auditoría desde archivo separado
from .models_audit import AuditLog

# ========== NUEVAS FUNCIONALIDADES ==========
# Importar modelos adicionales
from .models_extras import (
    GrupoEstudiantes, EnvioProgramado, PQRS, 
    ArchivoModulo, GrupoWhatsApp, InvitacionGrupo
)

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
        verbose_name_plural = '🏢 Prospectos B2B (Leads)'
        ordering = ['-fecha_captura']
    
    def __str__(self):
        return f"{self.telefono} - {self.empresa or 'Sin empresa'} ({self.get_estado_display()})"


__all__ = [
    'TemaCampana', 'Estudiante', 'Etiqueta', 'Plantilla', 'Linea', 'Canal', 
    'Campana', 'EnvioLog', 'WhatsappLog',
    'Curso', 'Modulo', 'ProgresoEstudiante', 'ModuloCompletado',
    'Examen', 'PreguntaExamen', 'ResultadoExamen',
    'SolicitudSoporte', 'PreguntaModulo',
    'PerfilGamificacion', 'Badge', 'BadgeEstudiante', 'TransaccionPuntos',
    'Certificado', 'PlantillaCertificado',
    'AuditLog',
    'GrupoEstudiantes', 'EnvioProgramado', 'PQRS',
    'ArchivoModulo', 'GrupoWhatsApp', 'InvitacionGrupo',
    'CampanaUnica', 'RespuestaCampanaUnica',
    'ProspectoB2B',
]