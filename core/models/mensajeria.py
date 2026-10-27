"""Modelos de mensajeria (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import openpyxl
import os
from django.db import IntegrityError
from core.models.clientes import Cliente
from core.models.estudiantes import Estudiante


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
    
    # CAMPAÑA DE CURSO: Al ejecutar, pone estudiantes en flujo habeas data → curso
    es_campana_curso = models.BooleanField(
        default=False,
        verbose_name="¿Es campaña de inicio de curso (WhatsApp + habeas)?",
        help_text=(
            'SÍ: reinicia onboarding (Habeas → verificación → *listo*). '
            'Para cursos normales por WhatsApp. '
            'NO: solo aviso (ideal 10x / modo Clases). Si hay «Curso destino», '
            'igual se inscribe en Aprende sin tocar Habeas.'
        ),
    )
    curso_destino = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campanas_curso',
        verbose_name='Curso destino',
        help_text=(
            'Al enviar, inscribe al estudiante en este curso (ProgresoEstudiante). '
            'Con «inicio de curso» = SÍ también reinicia Habeas. '
            'Con inicio = NO (10x): solo inscripción + plantilla de aviso.'
        ),
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
    canal = models.CharField(
        max_length=16,
        blank=True,
        default='',
        db_index=True,
        help_text='meta o twilio. Vacío en el histórico: no abre la ventana de la línea Meta.',
    )
    phone_id = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Línea Meta',
        help_text='Phone number id de la línea por la que salió o entró. Vacío en el histórico.',
    )
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
    error_codigo = models.CharField(
        max_length=16,
        blank=True,
        null=True,
        help_text='Código de error del proveedor (Graph o Twilio).',
    )
    error_detalle = models.TextField(
        blank=True,
        null=True,
        help_text='Detalle de error Twilio o del envío (código, mensaje, etc.)'
    )

    def __str__(self):
        return f"{self.telefono} - {self.tipo} - {self.estado} ({self.mensaje_id})"

    def save(self, *args, **kwargs):
        # Auto-asignar estudiante por teléfono si el log nace “ciego”.
        if not (self.canal or '').strip():
            from core.wa_canal import canal_actual

            marcado = canal_actual()
            if marcado:
                self.canal = marcado
        if not self.estudiante_id and self.telefono:
            try:
                from core.models.estudiantes import estudiante_por_telefono

                est = estudiante_por_telefono(self.telefono)
                if est:
                    self.estudiante = est
            except Exception:
                pass
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Registro de WhatsApp'
        verbose_name_plural = 'Historial WhatsApp'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['telefono', '-fecha']),
            models.Index(fields=['phone_id'], name='core_wlog_phone_id_idx'),
        ]


class SesionComercial(models.Model):
    """Memoria de conversación del bot comercial por cliente + teléfono."""

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sesiones_comerciales',
        verbose_name='Cliente',
    )
    telefono = models.CharField(max_length=30, db_index=True)
    historial_mensajes = models.JSONField(
        default=list,
        blank=True,
        help_text='Lista de mensajes [{"role": "...", "content": "..."}]. Máximo 10 turnos (20 mensajes).',
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_mensaje = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = 'Sesión comercial'
        verbose_name_plural = 'Sesiones comerciales'
        ordering = ['-fecha_ultimo_mensaje']
        indexes = [
            models.Index(fields=['telefono', '-fecha_ultimo_mensaje']),
            models.Index(fields=['cliente', '-fecha_ultimo_mensaje']),
        ]

    def __str__(self):
        cliente_txt = self.cliente.nombre if self.cliente_id else 'General'
        return f"{self.telefono} ({cliente_txt})"


# Procesar Excel subido: crear Estudiantes y agregarlos a la campaña
@receiver(post_save, sender=Campana)
def procesar_excel_campana(sender, instance, created, **kwargs):
    # Si hay un archivo y no hay destinatarios, intentamos cargarlo
    if instance.archivo_excel and instance.destinatarios.count() == 0:
        try:
            from core.excel_celdas import celda_excel_a_texto
            from core.canal.telefono import validar_telefono_whatsapp

            file_path = instance.archivo_excel.path
            if os.path.exists(file_path):
                wb = openpyxl.load_workbook(file_path)
                sheet = wb.active
                # Esperamos: columna A = Nombre, columna B = Telefono
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if not row:
                        continue
                    nombre = celda_excel_a_texto(row[0]) if row[0] is not None else ''
                    telefono_raw = celda_excel_a_texto(row[1]) if len(row) > 1 and row[1] is not None else ''
                    if not telefono_raw:
                        continue
                    check = validar_telefono_whatsapp(telefono_raw)
                    if not check['ok']:
                        continue
                    telefono_clean = check['telefono']
                    try:
                        estudiante, _created_est = Estudiante.objects.get_or_create(
                            telefono=telefono_clean,
                            defaults={'nombre': nombre or telefono_clean},
                        )
                    except IntegrityError:
                        estudiante = Estudiante.objects.filter(telefono=telefono_clean).first()
                        if not estudiante:
                            continue
                    instance.destinatarios.add(estudiante)
                instance.save()
        except Exception:
            # Si falla la lectura del excel no queremos romper el flujo de guardado
            pass
