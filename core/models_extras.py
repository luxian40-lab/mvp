"""
Modelos adicionales para mejoras solicitadas por el cliente
- Grupos de estudiantes
- Envíos programados
- PQRS
- Archivos multimedia
- Grupos de WhatsApp
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Estudiante, Curso, Modulo, Cliente


# ========== GRUPOS DE ESTUDIANTES ==========

class GrupoEstudiantes(models.Model):
    """Grupo de estudiantes para envíos masivos organizados"""
    
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre del Grupo',
        help_text='Ej: Cafeteros Zona Norte, Aguacateros 2026'
    )
    emoji = models.CharField(
        max_length=10,
        default='👥',
        verbose_name='Emoji',
        help_text='Emoji representativo del grupo'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción del grupo y su propósito'
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='grupos_estudiantes',
        verbose_name='Cliente',
        null=True,
        blank=True,
        help_text='Cliente al que pertenece el grupo (opcional)'
    )
    estudiantes = models.ManyToManyField(
        Estudiante,
        related_name='grupos',
        verbose_name='Estudiantes',
        blank=True
    )
    cursos = models.ManyToManyField(
        Curso,
        related_name='grupos',
        verbose_name='Cursos Asociados',
        blank=True,
        help_text='Cursos relacionados con este grupo (opcional)'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Grupo de Estudiantes'
        verbose_name_plural = '👥 Grupos de Estudiantes'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.nombre} ({self.total_estudiantes()} estudiantes)"
    
    def total_estudiantes(self):
        return self.estudiantes.count()
    
    total_estudiantes.short_description = 'Total'


# ========== ENVÍOS PROGRAMADOS ==========

class EnvioProgramado(models.Model):
    """Envío de mensaje programado para una fecha/hora específica"""
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('enviando', 'Enviando'),
        ('enviado', 'Enviado'),
        ('fallido', 'Fallido'),
        ('cancelado', 'Cancelado'),
    ]
    
    TIPOS = [
        ('individual', 'Individual'),
        ('grupo', 'Grupo Completo'),
        ('campana', 'Campaña Masiva'),
    ]
    
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del Envío',
        help_text='Nombre descriptivo para identificar este envío'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS,
        default='grupo',
        verbose_name='Tipo de Envío'
    )
    
    # Destinatarios
    campana = models.ForeignKey(
        'Campana',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='envios_programados',
        verbose_name='Campaña',
        help_text='Campaña a la que pertenece este envío programado'
    )
    grupo = models.ForeignKey(
        GrupoEstudiantes,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='envios_programados',
        verbose_name='Grupo',
        help_text='Grupo de estudiantes a quien enviar'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='envios_programados',
        verbose_name='Estudiante',
        help_text='Estudiante individual (solo si tipo=individual)'
    )
    
    # Contenido
    mensaje = models.TextField(
        verbose_name='Mensaje',
        help_text='Mensaje a enviar'
    )
    incluir_media = models.BooleanField(
        default=False,
        verbose_name='Incluir Multimedia'
    )
    media_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='URL del Archivo',
        help_text='URL de imagen, video o PDF a adjuntar'
    )
    
    # Programación
    fecha_programada = models.DateTimeField(
        verbose_name='Fecha y Hora Programada',
        help_text='Fecha y hora en la que se debe enviar'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado'
    )
    
    # Resultado
    fecha_envio_real = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Envío Real'
    )
    total_destinatarios = models.IntegerField(
        default=0,
        verbose_name='Total Destinatarios'
    )
    total_enviados = models.IntegerField(
        default=0,
        verbose_name='Total Enviados'
    )
    total_fallidos = models.IntegerField(
        default=0,
        verbose_name='Total Fallidos'
    )
    error = models.TextField(
        blank=True,
        verbose_name='Errores'
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='envios_programados_creados',
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Envío Programado'
        verbose_name_plural = '📅 Envíos Programados'
        ordering = ['-fecha_programada']
        indexes = [
            models.Index(fields=['estado', 'fecha_programada']),
        ]
    
    def __str__(self):
        return f"{self.nombre} - {self.get_estado_display()} ({self.fecha_programada.strftime('%d/%m/%Y %H:%M')})"
    
    def puede_cancelar(self):
        """Verifica si el envío puede ser cancelado"""
        return self.estado in ['pendiente'] and self.fecha_programada > timezone.now()
    
    def porcentaje_exito(self):
        """Calcula el porcentaje de éxito del envío"""
        if self.total_destinatarios == 0:
            return 0
        return int((self.total_enviados / self.total_destinatarios) * 100)


# ========== SISTEMA PQRS ==========

class PQRS(models.Model):
    """Sistema de Peticiones, Quejas, Reclamos y Sugerencias"""
    
    TIPOS = [
        ('peticion', 'Petición'),
        ('queja', 'Queja'),
        ('reclamo', 'Reclamo'),
        ('sugerencia', 'Sugerencia'),
        ('felicitacion', 'Felicitación'),
    ]
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En Proceso'),
        ('resuelto', 'Resuelto'),
        ('cerrado', 'Cerrado'),
        ('rechazado', 'Rechazado'),
    ]
    
    PRIORIDADES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    # Información básica
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS,
        verbose_name='Tipo'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='pqrs',
        verbose_name='Estudiante'
    )
    asunto = models.CharField(
        max_length=200,
        verbose_name='Asunto'
    )
    descripcion = models.TextField(
        verbose_name='Descripción'
    )
    
    # Categorización
    curso_relacionado = models.ForeignKey(
        Curso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Curso Relacionado'
    )
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDADES,
        default='media',
        verbose_name='Prioridad'
    )
    
    # Estado y seguimiento
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado'
    )
    respuesta = models.TextField(
        blank=True,
        verbose_name='Respuesta'
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name='Notas Internas',
        help_text='Notas para uso interno del equipo'
    )
    
    # Fechas
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Respuesta'
    )
    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Cierre'
    )
    
    # Asignación
    atendido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pqrs_atendidos',
        verbose_name='Atendido por'
    )
    
    # Calificación
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
    
    class Meta:
        verbose_name = 'PQRS'
        verbose_name_plural = '📮 PQRS (Peticiones/Quejas/Reclamos/Sugerencias)'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado', 'fecha_creacion']),
            models.Index(fields=['estudiante', 'estado']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.estudiante.nombre} - {self.asunto[:30]}"
    
    def dias_abierto(self):
        """Calcula los días que lleva abierto el caso"""
        if self.fecha_cierre:
            return (self.fecha_cierre - self.fecha_creacion).days
        return (timezone.now() - self.fecha_creacion).days
    
    dias_abierto.short_description = 'Días Abierto'
    
    def tiempo_respuesta_horas(self):
        """Calcula el tiempo de respuesta en horas"""
        if self.fecha_respuesta:
            return int((self.fecha_respuesta - self.fecha_creacion).total_seconds() / 3600)
        return None
    
    def esta_en_sla(self):
        """Verifica si está dentro del SLA (24 horas para respuesta)"""
        if self.estado == 'pendiente':
            return self.dias_abierto() < 1
        return True


# ========== ARCHIVOS MULTIMEDIA ==========

class ArchivoModulo(models.Model):
    """Archivos multimedia asociados a módulos"""
    
    TIPOS = [
        ('video', 'Video'),
        ('imagen', 'Imagen'),
        ('infografia', 'Infografía'),
        ('pdf', 'Documento PDF'),
        ('audio', 'Audio'),
    ]
    
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.CASCADE,
        related_name='archivos_multimedia',
        verbose_name='Módulo'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS,
        verbose_name='Tipo de Archivo'
    )
    titulo = models.CharField(
        max_length=200,
        verbose_name='Título',
        help_text='Ej: Video explicativo sobre riego'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    # Archivo
    archivo = models.FileField(
        upload_to='modulos/%Y/%m/',
        verbose_name='Archivo',
        help_text='Archivo multimedia'
    )
    url_externa = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='URL Externa',
        help_text='URL alternativa (YouTube, etc.)'
    )
    
    # Opciones
    disponible_offline = models.BooleanField(
        default=True,
        verbose_name='Disponible sin Conexión',
        help_text='Si está activado, se puede descargar para ver offline'
    )
    orden = models.IntegerField(
        default=0,
        verbose_name='Orden',
        help_text='Orden de visualización dentro del módulo'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    
    # Metadatos
    tamano_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Tamaño (bytes)'
    )
    duracion_segundos = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Duración (segundos)',
        help_text='Solo para videos/audios'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Archivo Multimedia'
        verbose_name_plural = '📁 Archivos Multimedia'
        ordering = ['modulo', 'orden', 'id']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.titulo}"
    
    def tamano_mb(self):
        """Retorna el tamaño en MB"""
        if self.tamano_bytes:
            return round(self.tamano_bytes / (1024 * 1024), 2)
        return 0
    
    tamano_mb.short_description = 'Tamaño (MB)'


# ========== GRUPOS DE WHATSAPP ==========

class GrupoWhatsApp(models.Model):
    """Grupos de WhatsApp para clases grupales"""
    
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre del Grupo',
        help_text='Ej: Curso de Café - Grupo 1'
    )
    descripcion = models.TextField(
        verbose_name='Descripción',
        help_text='Descripción del grupo y su propósito'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grupos_whatsapp',
        verbose_name='Curso Relacionado'
    )
    link_invitacion = models.URLField(
        max_length=500,
        verbose_name='Link de Invitación',
        help_text='Link de invitación del grupo de WhatsApp (https://chat.whatsapp.com/...)'
    )
    capacidad_maxima = models.IntegerField(
        default=256,
        verbose_name='Capacidad Máxima',
        help_text='Capacidad máxima del grupo (límite de WhatsApp: 1024)'
    )
    miembros_actuales = models.IntegerField(
        default=0,
        verbose_name='Miembros Actuales'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Grupo de WhatsApp'
        verbose_name_plural = '💬 Grupos de WhatsApp'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.nombre} ({self.miembros_actuales}/{self.capacidad_maxima})"
    
    def tiene_espacio(self):
        """Verifica si el grupo tiene espacio disponible"""
        return self.miembros_actuales < self.capacidad_maxima
    
    def porcentaje_ocupacion(self):
        """Calcula el porcentaje de ocupación del grupo"""
        if self.capacidad_maxima == 0:
            return 0
        return int((self.miembros_actuales / self.capacidad_maxima) * 100)
    
    porcentaje_ocupacion.short_description = '% Ocupación'


# ========== INVITACIONES A GRUPOS ==========

class InvitacionGrupo(models.Model):
    """Registro de invitaciones enviadas a estudiantes"""
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('enviada', 'Enviada'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
        ('expirada', 'Expirada'),
    ]
    
    grupo = models.ForeignKey(
        GrupoWhatsApp,
        on_delete=models.CASCADE,
        related_name='invitaciones',
        verbose_name='Grupo de WhatsApp'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='invitaciones_grupo',
        verbose_name='Estudiante'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado'
    )
    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Envío'
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Respuesta'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Invitación a Grupo'
        verbose_name_plural = '✉️ Invitaciones a Grupos'
        ordering = ['-fecha_creacion']
        unique_together = ['grupo', 'estudiante']
    
    def __str__(self):
        return f"{self.estudiante.nombre} → {self.grupo.nombre} ({self.get_estado_display()})"
