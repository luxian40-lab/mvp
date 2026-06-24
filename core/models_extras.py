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
        verbose_name_plural = 'Grupos de Estudiantes'
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
        verbose_name_plural = 'Envíos Programados'
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
        verbose_name_plural = 'PQRS (Peticiones/Quejas/Reclamos/Sugerencias)'
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

    def log_evento(self, mensaje):
        import logging
        logger = logging.getLogger('archivos_multimedia')
        logger.info(f"[ArchivoModulo] {mensaje} (ID: {getattr(self, 'id', None)})")

    def validar_url_publica(self, url):
        import requests
        try:
            r = requests.head(url, timeout=10)
            return r.status_code == 200 and r.headers.get('Content-Type') is not None
        except Exception:
            return False

    def save(self, *args, **kwargs):
        # Validar url_externa antes de guardar
        if self.url_externa:
            self.log_evento(f"Intentando validar URL externa: {self.url_externa}")
            if not self.validar_url_publica(self.url_externa):
                self.log_evento(f"ERROR: URL pública inválida o sin Content-Type: {self.url_externa}")
                raise ValueError(f'La URL pública no es válida o no tiene Content-Type: {self.url_externa}')
            self.log_evento(f"URL pública válida: {self.url_externa}")
        else:
            self.log_evento("Guardando archivo sin url_externa (usando archivo subido)")
        super().save(*args, **kwargs)
    """Archivos multimedia asociados a módulos"""

    @property
    def url_proxy(self):
        """
        Devuelve la URL proxy para servir el archivo desde el dominio propio si la url_externa es de S3.
        Si no es S3, devuelve la url_externa tal cual.
        """
        if self.url_externa and 's3.amazonaws.com' in self.url_externa:
            filename = self.url_externa.split('/')[-1]
            # Cambia el dominio por el de tu proxy (ajusta si cambia en producción)
            return f"https://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/media-proxy/{filename}"
        return self.url_externa

    def get_url_para_envio(self, usar_proxy=False):
        """
        Devuelve la URL que debe enviarse por WhatsApp (Twilio media_url).
        Twilio requiere URLs públicamente accesibles con Content-Type correcto.
        Usa presigned URLs de S3 para evitar error 63019 (Media download failed).
        
        Prioridad:
        1. url_externa si existe y es pública (si es S3 → presigned)
        2. archivo.url (S3 → presigned)
        3. None si no hay URL disponible
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Prioridad 1: URL externa pública (ya validada al guardar)
        if getattr(self, 'url_externa', None):
            url = self.url_externa
            # Si es S3, convertir a presigned URL
            if 'eki-produccion.s3' in url or 's3.amazonaws.com' in url:
                presigned = self._generar_presigned_url(url)
                if presigned:
                    return presigned
            return url
        
        # Prioridad 2: Archivo subido (generalmente en S3)
        if getattr(self, 'archivo', None) and self.archivo:
            try:
                # Generar presigned URL directamente desde la key del archivo
                key = self.archivo.name.lstrip('/')
                presigned = self._generar_presigned_url_desde_key(key)
                if presigned:
                    return presigned
                
                # Fallback: URL directa
                archivo_url = self.archivo.url
                if 'amazonaws.com' in archivo_url or archivo_url.startswith('http'):
                    return archivo_url
                # Si es URL relativa, construir URL completa
                from django.conf import settings
                base_url = getattr(settings, 'BASE_URL', 'https://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com')
                return f"{base_url}{archivo_url}"
            except Exception as e:
                logger.error(f"Error obteniendo URL de archivo: {e}")
                return None
        
        return None

    @staticmethod
    def _generar_presigned_url_desde_key(key, expires_in=3600):
        """Genera presigned URL de S3 desde una key.
        Incluye ResponseContentType para que Twilio pueda descargar correctamente (evita 63019)."""
        try:
            import boto3
            from botocore.config import Config
            region = 'us-east-2'
            bucket = 'eki-produccion'
            s3_client = boto3.client('s3', config=Config(signature_version='s3v4', region_name=region))
            
            # Determinar ContentType según extensión para evitar error 63019
            params = {'Bucket': bucket, 'Key': key}
            ext = key.rsplit('.', 1)[-1].lower() if '.' in key else ''
            content_types = {
                'mp4': 'video/mp4', 'mov': 'video/quicktime', 'avi': 'video/x-msvideo',
                'mp3': 'audio/mpeg', 'ogg': 'audio/ogg', 'wav': 'audio/wav',
                'm4a': 'audio/mp4', 'aac': 'audio/aac', 'opus': 'audio/opus',
                'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                'gif': 'image/gif', 'webp': 'image/webp',
                'pdf': 'application/pdf',
            }
            if ext in content_types:
                params['ResponseContentType'] = content_types[ext]
            
            url = s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error generando presigned URL para key {key}: {e}")
            return None

    @staticmethod
    def _generar_presigned_url(url, expires_in=3600):
        """Extrae la key de una URL de S3 y genera presigned URL."""
        try:
            from urllib.parse import unquote_plus
            key = unquote_plus(url.split('.amazonaws.com/')[-1].split('?')[0])
            return ArchivoModulo._generar_presigned_url_desde_key(key, expires_in)
        except Exception:
            return None
    
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
    
    # Archivo - Puedes SUBIR archivo desde PC O usar URL externa (elige UNO)
    archivo = models.FileField(
        upload_to='modulos/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Subir Archivo desde PC',
        help_text='Sube imagen, video, PDF o audio desde tu computadora (se guarda en AWS S3)'
    )
    url_externa = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='O usar URL Externa',
        help_text='Alternativa: Pega enlace de YouTube, Google Drive, Imgur, etc. (solo si NO subes archivo)'
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
        verbose_name_plural = 'Archivos Multimedia'
        ordering = ['modulo', 'orden', 'id']
    
    def save(self, *args, **kwargs):
        """Override save para diagnosticar almacenamiento S3, backend, bucket y capturar errores"""
        import logging
        logger = logging.getLogger("models_extras")
        logger.warning("=== SAVE START ===")
        import traceback
        from django.core.files.storage import default_storage
        from django.conf import settings
        try:
            logger.warning("[ARCHIVOMODULO SAVE] DIAGNOSTICO DE ALMACENAMIENTO")
            logger.warning(f"[settings.DEFAULT_FILE_STORAGE] {getattr(settings, 'DEFAULT_FILE_STORAGE', None)}")
            logger.warning(f"[STORAGE BACKEND] {type(default_storage).__name__}")
            logger.warning(f"[STORAGE CLASS] {default_storage.__class__.__module__}.{default_storage.__class__.__name__}")
            # Si es S3, imprime el bucket
            try:
                if hasattr(default_storage, 'bucket'):
                    logger.warning(f"[S3 BUCKET] {getattr(default_storage, 'bucket', None)}")
                elif hasattr(default_storage, 'bucket_name'):
                    logger.warning(f"[S3 BUCKET] {getattr(default_storage, 'bucket_name', None)}")
            except Exception as e:
                logger.warning(f"[S3 BUCKET ERROR] {e}")
            if self.archivo:
                logger.warning(f"[ARCHIVO] {self.archivo.name}")
                try:
                    logger.warning(f"[ARCHIVO STORAGE] {type(self.archivo.storage).__name__}")
                    logger.warning(f"[ARCHIVO STORAGE CLASS] {self.archivo.storage.__class__.__module__}.{self.archivo.storage.__class__.__name__}")
                    # Si es S3, imprime el bucket del archivo
                    if hasattr(self.archivo.storage, 'bucket'):
                        logger.warning(f"[ARCHIVO S3 BUCKET] {getattr(self.archivo.storage, 'bucket', None)}")
                    elif hasattr(self.archivo.storage, 'bucket_name'):
                        logger.warning(f"[ARCHIVO S3 BUCKET] {getattr(self.archivo.storage, 'bucket_name', None)}")
                except Exception as e:
                    logger.warning(f"[ARCHIVO STORAGE ERROR] {e}")
            logger.warning("[STACKTRACE]")
            traceback.print_stack()
            logger.warning("="*70 + "\n")
            super().save(*args, **kwargs)
            logger.warning("=== SAVE END ===")
        except Exception as e:
            logger.warning("EXCEPCIÓN EN SAVE: %s", e)
            traceback.print_exc()
            raise
    
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
        verbose_name_plural = 'Grupos de WhatsApp'
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
        verbose_name_plural = 'Invitaciones a Grupos'
        ordering = ['-fecha_creacion']
        unique_together = ['grupo', 'estudiante']
    
    def __str__(self):
        return f"{self.estudiante.nombre} → {self.grupo.nombre} ({self.get_estado_display()})"


class MensajePush(models.Model):
    """Recordatorio WhatsApp; el estudiante responde *listo* y sigue el curso."""

    TIPO_CHOICES = [
        ('recordatorio_inscripcion', 'Inscrito — aún no inicia'),
        ('recordatorio_avance', 'Curso iniciado — sigue avanzando'),
        ('recordatorio_modulo', 'Módulo disponible'),
        ('personalizado', 'Personalizado'),
    ]

    nombre = models.CharField(max_length=120)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name='mensajes_push', null=True, blank=True,
    )
    curso = models.ForeignKey(
        Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensajes_push',
    )
    plantilla = models.ForeignKey(
        'core.Plantilla', on_delete=models.SET_NULL, null=True, blank=True, related_name='mensajes_push',
    )
    twilio_content_sid = models.CharField(max_length=64, blank=True)
    tipo = models.CharField(max_length=32, choices=TIPO_CHOICES, default='recordatorio_avance')
    cuerpo_fallback = models.TextField(
        blank=True,
        help_text='Texto libre si no hay SID. Variables: {nombre}, {curso}.',
    )
    incluir_boton_continuar = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mensaje push'
        verbose_name_plural = 'Mensajes push'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.nombre

    def render_texto(self, estudiante, curso=None) -> str:
        c = curso or self.curso
        curso_nom = c.nombre if c else 'su curso'
        if self.plantilla_id and self.plantilla.cuerpo_mensaje:
            txt = self.plantilla.cuerpo_mensaje.replace('{nombre}', estudiante.nombre or 'estudiante')
        else:
            txt = (self.cuerpo_fallback or 'Hola {nombre}, le recordamos continuar con {curso}.')
        txt = txt.replace('{nombre}', estudiante.nombre or 'estudiante').replace('{curso}', curso_nom)
        if self.incluir_boton_continuar and 'listo' not in txt.lower():
            txt += '\n\nResponda *listo* para continuar con el curso (sin reiniciar).'
        return txt.strip()


class EnvioMensajePush(models.Model):
    mensaje_push = models.ForeignKey(MensajePush, on_delete=models.CASCADE, related_name='envios')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='envios_push')
    telefono = models.CharField(max_length=20)
    exito = models.BooleanField(default=False)
    detalle = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Envío mensaje push'
        verbose_name_plural = 'Envíos mensajes push'
        ordering = ['-fecha']


class EnlaceFormularioExterno(models.Model):
    """
    Google Form (u otro) → al enviar respuesta, habilita un módulo al estudiante.
    URL webhook: POST /api/integracion/form-externo/<token>/
    """

    CAMPO_CHOICES = [
        ('cedula', 'Solo cédula (menos seguro)'),
        ('telefono', 'Solo teléfono WhatsApp'),
        ('cedula_y_telefono', 'Cédula + teléfono (recomendado)'),
        ('cedula_y_nombre', 'Cédula + nombre completo'),
    ]

    nombre = models.CharField(max_length=120, help_text='Ej: Google Form pre-evaluación M5')
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name='enlaces_formulario_externo',
    )
    curso = models.ForeignKey(
        Curso, on_delete=models.CASCADE, related_name='enlaces_formulario_externo',
    )
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='enlaces_formulario_externo',
        help_text='Vacío = último módulo del curso (mayor número).',
    )
    campo_identificador = models.CharField(
        max_length=24,
        choices=CAMPO_CHOICES,
        default='cedula_y_telefono',
        verbose_name='Validación de identidad',
    )
    token = models.CharField(max_length=64, unique=True, editable=False)
    activo = models.BooleanField(default=True)
    notas = models.TextField(blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Enlace formulario externo'
        verbose_name_plural = 'Enlaces formulario externo (Google Form)'
        ordering = ['-creado_en']

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nombre} · {self.cliente.nombre}'

    def modulo_efectivo(self):
        if self.modulo_id:
            return self.modulo
        return self.curso.modulos.order_by('-numero').first()


class RegistroFormularioExterno(models.Model):
    """Log de cada llamada al webhook (auditoría)."""
    enlace = models.ForeignKey(
        EnlaceFormularioExterno, on_delete=models.CASCADE, related_name='registros',
    )
    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_form_externo',
    )
    identificador_recibido = models.CharField(max_length=80, blank=True, default='')
    exito = models.BooleanField(default=False)
    detalle = models.CharField(max_length=255, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Registro formulario externo'
        verbose_name_plural = 'Registros formulario externo'
        ordering = ['-fecha']
