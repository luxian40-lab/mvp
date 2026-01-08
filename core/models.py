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
        help_text="Emoji representativo (ej: ☕, 🥑, 🌽)"
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
        verbose_name_plural = 'Temas de Campañas'
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
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está inactivo, sus estudiantes no recibirán mensajes"
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name="Notas Internas",
        help_text="Notas para uso interno de Eki (no visibles para el cliente)"
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro"
    )
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
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
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='estudiantes',
        verbose_name='Cliente',
        help_text='Cliente/Organización a la que pertenece este estudiante'
    )
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Limpieza de teléfono
        numero = re.sub(r'\D', '', str(self.telefono))
        if len(numero) == 10: numero = f"57{numero}"
        
        # Validación
        if not (10 <= len(numero) <= 15):
            # Si viene de un Excel, a veces es mejor no romper todo, 
            # pero aquí mantendremos la regla estricta.
            pass 
        self.telefono = numero

    def save(self, *args, **kwargs):
        self.clean() # Forzamos limpieza antes de guardar
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.nombre} ({self.telefono})"

# 2. PLANTILLA
class Plantilla(models.Model):
    """Plantillas de mensajes personalizables para campañas"""
    
    CATEGORIA_CHOICES = [
        ('educativo', '📚 Educativo'),
        ('motivacional', '💪 Motivacional'),
        ('informativo', 'ℹ️ Informativo'),
        ('promocional', '🎁 Promocional'),
        ('recordatorio', '⏰ Recordatorio'),
        ('bienvenida', '👋 Bienvenida'),
        ('otro', '📝 Otro'),
    ]
    
    nombre_interno = models.CharField(
        max_length=100,
        verbose_name="Nombre de la plantilla",
        help_text="Nombre interno para identificar la plantilla (ej: 'Bienvenida Estudiantes')"
    )
    
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='informativo',
        verbose_name="Categoría",
        help_text="Tipo de plantilla"
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
    
    # NUEVO: Temas asociados
    temas = models.ManyToManyField(
        TemaCampana,
        blank=True,
        verbose_name="Temas",
        help_text="Selecciona uno o más temas relacionados (ej: Café, Motivación)",
        related_name='plantillas'
    )
    
    # NUEVO: Integración con Meta WhatsApp Business
    meta_template_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="ID de Plantilla en Meta",
        help_text="ID asignado por Meta al enviar la plantilla para revisión"
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
        verbose_name="Estado en Meta",
        help_text="Estado de aprobación de la plantilla en Meta"
    )
    meta_template_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nombre en Meta",
        help_text="Nombre sanitizado usado en Meta (minúsculas, guiones bajos)"
    )
    enviada_a_meta = models.BooleanField(
        default=False,
        verbose_name="Enviada a Meta",
        help_text="Indica si la plantilla fue enviada a Meta para aprobación"
    )
    
    class Meta:
        verbose_name = 'Plantilla de Mensaje'
        verbose_name_plural = 'Plantillas de Mensajes'
        ordering = ['-fecha_modificacion']
    
    def __str__(self):
        return f"{self.get_categoria_display()} - {self.nombre_interno}"
    
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
    
    # NUEVO: Tema de la campaña (para filtrar plantillas)
    tema = models.ForeignKey(
        TemaCampana,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tema principal",
        help_text="Selecciona el tema (ej: Café, Aguacate). Solo se mostrarán plantillas de este tema.",
        related_name='campanas'
    )
    
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT)
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

    def __str__(self):
        return f"{self.telefono} - {self.tipo} - {self.estado} ({self.mensaje_id})"
    
    class Meta:
        verbose_name = 'Registro de WhatsApp'
        verbose_name_plural = 'Registros de WhatsApp'
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
    emoji = models.CharField(max_length=10, default="📚", help_text="Emoji representativo")
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cursos',
        verbose_name='Cliente Específico',
        help_text='Si es para un cliente específico. Dejar vacío = curso general de Eki disponible para todos'
    )
    duracion_semanas = models.IntegerField(default=5, help_text="Duración estimada en semanas")
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(default=0, help_text="Orden de visualización")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self):
        return f"{self.emoji} {self.nombre}"

    def total_modulos(self):
        return self.modulos.count()


class Modulo(models.Model):
    """Módulo dentro de un curso (ej: Módulo 1: Siembra)"""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='modulos')
    numero = models.IntegerField(help_text="Número del módulo (1-5)")
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
        help_text="Imagen de portada del módulo"
    )
    archivo_pdf_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Material PDF descargable"
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
        verbose_name_plural = "Progresos de Estudiantes"
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


class ModuloCompletado(models.Model):
    """Registro de módulos completados por el estudiante"""
    progreso = models.ForeignKey(ProgresoEstudiante, on_delete=models.CASCADE, related_name='modulos_completados')
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    fecha_completado = models.DateTimeField(auto_now_add=True)

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
        estado = "✅ Aprobado" if self.aprobado else "❌ Reprobado"
        return f"{self.estudiante.nombre} - {self.examen.curso.nombre} - {self.puntaje}% {estado}"


# ========== GAMIFICACIÓN ==========
# Importar modelos de gamificación desde archivo separado
from .gamificacion import PerfilGamificacion, Badge, BadgeEstudiante, TransaccionPuntos

__all__ = [
    'TemaCampana', 'Estudiante', 'Etiqueta', 'Plantilla', 'Linea', 'Canal', 
    'Campana', 'EnvioLog', 'WhatsappLog',
    'Curso', 'Modulo', 'ProgresoEstudiante', 'ModuloCompletado',
    'Examen', 'PreguntaExamen', 'ResultadoExamen',
    'PerfilGamificacion', 'Badge', 'BadgeEstudiante', 'TransaccionPuntos'
]