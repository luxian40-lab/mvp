"""Modelos de soporte (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.models.estudiantes import Estudiante
from core.models.cursos import Curso
from core.models.modulos import Modulo


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

    CATEGORIA_PQRS_CHOICES = [
        ('', '— Sin clasificar'),
        ('acceso', '🔑 Acceso (login, cédula, número)'),
        ('contenido', '📚 Contenido (módulo, video, examen)'),
        ('tecnico', '🛠️ Técnico (errores del sistema)'),
        ('organizacion', '🏢 Organización / cliente (no curso)'),
        ('duda_modulo', 'Duda de módulo'),
        ('problema_acceso', 'Problema de acceso'),
        ('solicitud_certificado', 'Solicitud de certificado'),
        ('consulta_calculo', 'Consulta de cálculo'),
        ('correccion_datos', 'Corrección de datos'),
        ('problema_tecnico', 'Problema técnico'),
        ('conversacion_escalada', 'Conversación escalada'),
        ('pregunta_sin_respuesta', 'Pregunta sin respuesta'),
        ('queja', 'Queja'),
        ('otro', '❓ Otro'),
    ]

    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_PQRS_CHOICES,
        blank=True,
        default='',
        verbose_name='Categoría PQRS',
        help_text='Clasificación automática del agente PQRS (acceso, contenido, técnico, otro).',
    )
    resuelto_por_agente = models.BooleanField(
        default=False,
        verbose_name='Resuelto por agente IA',
        help_text='True si el agente PQRS resolvió en primer nivel; False si quedó escalado.',
    )
    preguntas_realizadas = models.IntegerField(
        default=0,
        verbose_name='Preguntas de clarificación',
        help_text='Preguntas de clarificación del agente PQRS (máximo 2 por ticket).',
    )

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
    respuesta_portal = models.TextField(
        null=True,
        blank=True,
        verbose_name='Respuesta desde portal',
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de respuesta desde portal',
    )
    respondido_por = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='pqrs_respondidas',
        verbose_name='Respondido por',
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
        verbose_name_plural = 'Soporte y PQRS'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado', 'prioridad']),
            models.Index(fields=['estudiante', 'fecha_solicitud']),
            models.Index(fields=['tipo_solicitud', 'estado']),
        ]
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.get_estado_display()} - {self.fecha_solicitud.strftime('%d/%m/%Y')}"
