from django.db import models
from django.db.models import Q
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import re
import openpyxl # <--- Nueva librería
import os
from django.db import IntegrityError

from core.documento_identidad import TIPO_DOCUMENTO_CHOICES
from core.models.opciones import PLAN_CHOICES as PLAN_LINEA_CHOICES
from core.webhook_evento import WebhookEventoProcesado, WebhookFallido  # noqa: F401

from core.models.clientes import (  # noqa: F401
    TemaCampana,
    Cliente,
    FaqOrganizacion,
    MetaMetricaEmpresa,
    MetaMetricaNati,
)


from core.models.estudiantes import (  # noqa: F401
    Estudiante,
)

from core.models.mensajeria import (  # noqa: F401
    Plantilla,
    Campana,
    Linea,
    EnvioLog,
    WhatsappLog,
    SesionComercial,
    procesar_excel_campana,
)


from core.models.cursos import (  # noqa: F401
    Curso,
    ConfiguracionDripCliente,
    HabilitacionModuloDripCliente,
    HabilitacionModuloEstudiante,
)


from core.models.conocimiento import (  # noqa: F401
    DocumentoRAG,
    DocumentoRAGComercial,
    BibliotecaConocimiento,
    ProductoComercial,
    ProductoCatalogo,
)


from core.models.modulos import (  # noqa: F401
    Modulo,
    SeccionModulo,
    PasoModulo,
    ModuloPublicacionEvent,
    ProgresoEstudiante,
    PreguntaModulo,
    ModuloCompletado,
)


from core.models.aprendizaje import (  # noqa: F401
    EstudianteEventoAprendizaje,
    Examen,
    PreguntaExamen,
    ResultadoExamen,
    ObjetivoCurso,
    RubricaEvaluacion,
    EjercicioPractico,
    RespuestaEjercicio,
)


from core.models.soporte import (  # noqa: F401
    InteraccionLog,
    SolicitudSoporte,
)


# ========== GAMIFICACIÓN ==========
# Importar modelos de gamificación desde archivo separado
from core.gamificacion import (
    PerfilGamificacion,
    Badge,
    BadgeEstudiante,
    TransaccionPuntos,
    EvaluacionNotaGamificacion,
)

# ========== CERTIFICADOS ==========
# Importar modelos de certificados desde archivo separado
from core.models_certificados import Certificado, PlantillaCertificado
from core.models_notas import NotaEstudiante

# ========== AUDITORÍA ==========
# Importar modelos de auditoría desde archivo separado
from core.models_audit import AuditLog

# ========== NUEVAS FUNCIONALIDADES ==========
# Importar modelos adicionales
from core.models_extras import (
    GrupoEstudiantes, EnvioProgramado, PQRS, 
    ArchivoModulo, GrupoWhatsApp, InvitacionGrupo,
    MensajePush, EnvioMensajePush,
)
from core.models_media_entrega import MediaPaqueteEntrega
from core.models_campana_meta import PlantillaMeta, TarjetaPlantillaMeta, CampanaMeta, EnvioCampanaMeta
from core.models_meta_webhook import MetaWebhookEvento
from core.models_video import VideoEnlace, VideoView
from core.models_agentes import ConocimientoAgente, PruebaAgente
from core.models_uso_llm import UsoLLM
from core.lineas.modelo import LineaWhatsapp
from core.conversacion.estado_linea import EstadoLinea

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


class AliadoEmpleabilidad(models.Model):
    """Empresas aliadas para gamificación geolocalizada de empleabilidad."""
    nombre_empresa = models.CharField(max_length=200, verbose_name='Nombre de la empresa')
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aliados_empleabilidad',
        verbose_name='Cliente asociado',
        help_text='Opcional. Si se define, solo aplica para estudiantes de ese cliente.'
    )
    latitud = models.FloatField(verbose_name='Latitud')
    longitud = models.FloatField(verbose_name='Longitud')
    cupos_disponibles = models.PositiveIntegerField(
        default=0,
        verbose_name='Cupos disponibles',
        help_text='Vacantes disponibles para priorización del radar de empleabilidad.'
    )
    prioridad = models.PositiveSmallIntegerField(
        default=3,
        verbose_name='Prioridad (1-5)',
        help_text='5 = máxima prioridad para aparecer en el radar de oportunidades.'
    )
    vigencia_desde = models.DateField(
        null=True,
        blank=True,
        verbose_name='Vigencia desde',
        help_text='Fecha de inicio de vigencia de la oportunidad.'
    )
    vigencia_hasta = models.DateField(
        null=True,
        blank=True,
        verbose_name='Vigencia hasta',
        help_text='Fecha de fin de vigencia de la oportunidad.'
    )
    vacantes_activas = models.BooleanField(default=True, verbose_name='Vacantes activas')
    codigo_secreto = models.CharField(max_length=120, verbose_name='Código secreto')
    indicacion_sector = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Indicación de sector',
        help_text='Ej: costado oriental del parque principal'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aliado de Empleabilidad'
        verbose_name_plural = 'Aliados de Empleabilidad'
        ordering = ['nombre_empresa']

    def __str__(self):
        return self.nombre_empresa


class MisionEmpleabilidad(models.Model):
    """Misiones de exploración/validación de oportunidades por proximidad."""

    ESTADO_CHOICES = [
        ('descubierta', 'Descubierta'),
        ('reclamada', 'Reclamada'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    FLUJO_CHOICES = [
        ('descubierto', 'Descubierto'),
        ('interesado', 'Interesado'),
        ('postulado', 'Postulado'),
        ('entrevista', 'Entrevista'),
        ('vinculado', 'Vinculado'),
        ('descartado', 'Descartado'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='misiones_empleabilidad',
        verbose_name='Cliente'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='misiones_empleabilidad',
        verbose_name='Estudiante'
    )
    aliado = models.ForeignKey(
        AliadoEmpleabilidad,
        on_delete=models.CASCADE,
        related_name='misiones_empleabilidad',
        verbose_name='Aliado'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='descubierta', verbose_name='Estado')
    latitud = models.FloatField(null=True, blank=True, verbose_name='Latitud referencia')
    longitud = models.FloatField(null=True, blank=True, verbose_name='Longitud referencia')
    distancia_metros = models.FloatField(null=True, blank=True, verbose_name='Distancia en metros')
    codigo_validado = models.BooleanField(default=False, verbose_name='Código validado')
    puntos_otorgados = models.IntegerField(default=0, verbose_name='Puntos otorgados')
    estado_flujo = models.CharField(
        max_length=20,
        choices=FLUJO_CHOICES,
        default='descubierto',
        verbose_name='Estado del embudo'
    )
    puntaje_prioridad = models.FloatField(
        default=0,
        verbose_name='Puntaje de priorización',
        help_text='Score calculado para priorizar oportunidades en el radar.'
    )
    canal_origen = models.CharField(
        max_length=40,
        default='whatsapp',
        verbose_name='Canal origen'
    )
    metadata = models.JSONField(null=True, blank=True, help_text='Datos adicionales de misión (debug/contexto).')

    fecha_descubierta = models.DateTimeField(auto_now_add=True)
    fecha_reclamada = models.DateTimeField(null=True, blank=True)
    fecha_completada = models.DateTimeField(null=True, blank=True)
    fecha_interes = models.DateTimeField(null=True, blank=True)
    fecha_postulacion = models.DateTimeField(null=True, blank=True)
    fecha_entrevista = models.DateTimeField(null=True, blank=True)
    fecha_vinculacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Misión de Empleabilidad'
        verbose_name_plural = 'Misiones de Empleabilidad'
        ordering = ['-fecha_descubierta']
        indexes = [
            models.Index(fields=['estudiante', 'estado', 'fecha_descubierta']),
            models.Index(fields=['cliente', 'estado', 'fecha_descubierta']),
            models.Index(fields=['aliado', 'estado']),
            models.Index(fields=['cliente', 'estado_flujo', 'fecha_descubierta']),
        ]

    def __str__(self):
        return f"{self.estudiante.nombre} -> {self.aliado.nombre_empresa} ({self.get_estado_display()})"


class PreguntaAbiertaFinalCurso(models.Model):
    """Pregunta abierta opcional al final del curso, evaluada por facilitadora."""
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='preguntas_abiertas_finales'
    )
    orden = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Orden',
        help_text='Orden de la pregunta en el cierre (1 a 3).'
    )
    pregunta = models.TextField(verbose_name='Pregunta abierta final')
    activa = models.BooleanField(default=True, verbose_name='Activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pregunta Abierta Final'
        verbose_name_plural = 'Preguntas Abiertas Finales'
        ordering = ['curso', 'orden', 'id']
        unique_together = ['curso', 'orden']

    def __str__(self):
        return f"Pregunta final #{self.orden} - {self.curso.nombre}"

    def clean(self):
        super().clean()
        if self.orden < 1 or self.orden > 3:
            raise ValidationError({'orden': 'El orden debe estar entre 1 y 3.'})

        existentes = PreguntaAbiertaFinalCurso.objects.filter(curso=self.curso)
        if self.pk:
            existentes = existentes.exclude(pk=self.pk)
        if existentes.count() >= 3:
            raise ValidationError('Cada curso permite máximo 3 preguntas abiertas finales.')


class RespuestaAbiertaFinal(models.Model):
    """Respuesta del estudiante a la pregunta abierta final (calificada por facilitadora)."""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de calificar'),
        ('calificada', 'Calificada'),
    ]

    pregunta = models.ForeignKey(
        PreguntaAbiertaFinalCurso,
        on_delete=models.CASCADE,
        related_name='respuestas'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='respuestas_abiertas_finales'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='respuestas_abiertas_finales'
    )
    progreso = models.ForeignKey(
        ProgresoEstudiante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_abiertas_finales'
    )
    respuesta_texto = models.TextField(verbose_name='Respuesta del estudiante')
    fecha_respuesta = models.DateTimeField(default=timezone.now)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    calificacion = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Calificación (0-100)'
    )
    retroalimentacion = models.TextField(blank=True, default='', verbose_name='Retroalimentación facilitadora')
    calificada_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calificaciones_preguntas_abiertas'
    )
    fecha_calificacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Respuesta Abierta Final'
        verbose_name_plural = 'Respuestas Abiertas Finales'
        ordering = ['-fecha_respuesta']
        unique_together = ['pregunta', 'estudiante']

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.curso.nombre}"


class ConfiguracionGlobal(models.Model):
    """Singleton de configuración general de eki, editable desde el admin.

    Solo debe existir una fila (id=1). El método `get_solo()` la crea si falta.
    """
    content_sid_habeas_data_global = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Habeas Data — Plantilla Twilio general (Content SID)',
        help_text=(
            'Content SID (HX...) de la plantilla Twilio aprobada para el Habeas Data por defecto. '
            'Se usa cuando el cliente no tiene su propio Content SID configurado.'
        ),
    )
    meta_plantilla_diploma = models.CharField(
        max_length=128,
        blank=True,
        default='',
        verbose_name='Diploma — nombre de plantilla Meta',
        help_text=(
            'Nombre de la plantilla aprobada en Meta (no es un HX de Twilio). '
            'Encabezado: imagen. Cuerpo: {{1}} nombre, {{2}} curso, {{3}} código. '
            'Vacío: el diploma se manda como imagen solo si la persona escribió en las últimas 24 horas. '
            'Si META_TEMPLATE_DIPLOMA está en el entorno, ese valor gana.'
        ),
    )
    cursos_linea_2 = models.ManyToManyField(
        'Curso',
        blank=True,
        related_name='en_linea_2',
        verbose_name='Cursos de la línea 2 (opcional)',
        help_text=(
            'La línea 2 no abre carrusel. El curso entra por campaña o inscripción. '
            'Esta lista es opcional para campañas futuras; no cambia el menú de WhatsApp.'
        ),
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Configuración Global'
        verbose_name_plural = 'Configuración Global'

    def __str__(self):
        return 'Configuración Global eki'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class EventoIA(models.Model):
    """Trazabilidad persistente de decisiones IA, checkpoints y RAG (Parte 2A)."""

    TIPO_MODULO_COMPLETADO = 'modulo_completado'
    TIPO_CHECKPOINT_EVALUADO = 'checkpoint_evaluado'
    TIPO_IA_AGENT_TRIGGERED = 'ia_agent_triggered'
    TIPO_RAG_QUERY_EXECUTED = 'rag_query_executed'
    TIPO_WEBHOOK_RECIBIDO = 'webhook_recibido'
    TIPO_INTENT_DETECTADO = 'intent_detectado'
    TIPO_MENSAJE_ENVIADO = 'mensaje_enviado'

    TIPO_CHOICES = [
        (TIPO_MODULO_COMPLETADO, 'Módulo completado'),
        (TIPO_CHECKPOINT_EVALUADO, 'Checkpoint evaluado'),
        (TIPO_IA_AGENT_TRIGGERED, 'Agente IA activado'),
        (TIPO_RAG_QUERY_EXECUTED, 'Consulta RAG'),
        (TIPO_WEBHOOK_RECIBIDO, 'Webhook recibido'),
        (TIPO_INTENT_DETECTADO, 'Intent detectado'),
        (TIPO_MENSAJE_ENVIADO, 'Mensaje enviado'),
    ]

    CANAL_WHATSAPP_EDU = 'whatsapp_edu'
    CANAL_WHATSAPP_COMERCIAL = 'whatsapp_comercial'
    CANAL_ADMIN = 'admin'

    trace_id = models.UUIDField(db_index=True, verbose_name='Trace ID')
    tipo = models.CharField(max_length=40, choices=TIPO_CHOICES, db_index=True)

    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )
    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )

    agente = models.CharField(max_length=60, blank=True, default='')
    canal = models.CharField(max_length=30, default=CANAL_WHATSAPP_EDU, db_index=True)

    facilitador_checkpoint = models.CharField(max_length=10, blank=True, default='')
    regla_aplicada = models.CharField(max_length=60, blank=True, default='', db_index=True)
    es_reto = models.BooleanField(null=True, blank=True)

    modelo = models.CharField(max_length=60, blank=True, default='')
    latencia_ms = models.PositiveIntegerField(null=True, blank=True)
    tokens_in = models.PositiveIntegerField(null=True, blank=True)
    tokens_out = models.PositiveIntegerField(null=True, blank=True)

    input_preview = models.TextField(blank=True, default='')
    output_preview = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Evento IA'
        verbose_name_plural = 'Eventos IA'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'tipo']),
            models.Index(fields=['trace_id', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} · {self.trace_id} · {self.created_at:%Y-%m-%d %H:%M}'


class ContextoAgroSession(models.Model):
    """Contexto agronómico estructurado por sesión Nat (Parte 3)."""

    sesion = models.OneToOneField(
        SesionComercial,
        on_delete=models.CASCADE,
        related_name='contexto_agro',
        verbose_name='Sesión comercial',
    )
    cultivo = models.CharField(max_length=80, blank=True, default='')
    etapa = models.CharField(max_length=80, blank=True, default='', help_text='Ej: floración, desarrollo')
    region = models.CharField(max_length=120, blank=True, default='', help_text='Departamento o zona')
    municipio = models.CharField(max_length=80, blank=True, default='')
    vereda = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Vereda, localidad o zona más exacta dentro del municipio',
    )
    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Latitud geocodificada (Open-Meteo u otra fuente)',
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Longitud geocodificada (Open-Meteo u otra fuente)',
    )
    clima = models.CharField(max_length=80, blank=True, default='', help_text='Ej: alta humedad, sequía')
    problema = models.CharField(max_length=200, blank=True, default='', help_text='Plaga, enfermedad, nutrición')
    notas = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contexto agronómico (Nat)'
        verbose_name_plural = 'Contextos agronómicos (Nat)'

    def campos_llenos(self) -> list[str]:
        out = []
        for k in ('cultivo', 'etapa', 'region', 'municipio', 'clima', 'problema'):
            if (getattr(self, k, '') or '').strip():
                out.append(k)
        return out

    def completitud_pct(self) -> int:
        total = 6
        return int(len(self.campos_llenos()) * 100 / total) if total else 0

    def to_dict(self) -> dict:
        return {
            'cultivo': self.cultivo,
            'etapa': self.etapa,
            'region': self.region,
            'municipio': self.municipio,
            'vereda': self.vereda,
            'latitud': float(self.latitud) if self.latitud is not None else None,
            'longitud': float(self.longitud) if self.longitud is not None else None,
            'clima': self.clima,
            'problema': self.problema,
            'completitud_pct': self.completitud_pct(),
        }

    def __str__(self):
        parts = [p for p in (self.cultivo, self.problema, self.region) if p]
        return ' · '.join(parts) if parts else f'Contexto sesión {self.sesion_id}'


class ConversacionRAGCandidata(models.Model):
    """Cola HITL: conversación Nat candidata a publicarse como conocimiento validado (Parte 4)."""

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_APROBADA = 'aprobada'
    ESTADO_RECHAZADA = 'rechazada'
    ESTADO_PUBLICADA = 'publicada'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente revisión'),
        (ESTADO_APROBADA, 'Aprobada (sin publicar)'),
        (ESTADO_RECHAZADA, 'Rechazada'),
        (ESTADO_PUBLICADA, 'Publicada en RAG'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_rag',
    )
    sesion = models.ForeignKey(
        SesionComercial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_rag',
    )
    telefono = models.CharField(max_length=30, db_index=True)
    trace_id = models.UUIDField(null=True, blank=True, db_index=True)
    pregunta = models.TextField()
    respuesta_nati = models.TextField()
    respuesta_revisada = models.TextField(blank=True, default='')
    contexto_agro = models.JSONField(default=dict, blank=True)
    chunks_rag = models.JSONField(default=list, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE, db_index=True)
    revisado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_rag_revisadas',
    )
    notas_revisor = models.TextField(blank=True, default='')
    agentes = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Aplica a',
        help_text='Agentes que pueden usar esta respuesta.',
    )
    alcance = models.CharField(
        max_length=16,
        choices=[('todos', 'Todos'), ('cliente', 'Un cliente')],
        default='todos',
        verbose_name='Alcance',
    )
    documento_rag = models.ForeignKey(
        DocumentoRAGComercial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_origen',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Candidata RAG (HITL)'
        verbose_name_plural = 'Candidatas RAG (HITL)'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.get_estado_display()} · {self.pregunta[:60]}'


class SandboxCanalSesion(models.Model):
    """Modo sticky del menú sandbox (Nat|agentes|cursos) — solo número Twilio sandbox."""

    MODO_MENU = 'menu'
    MODO_AGENTES = 'agentes'
    MODO_NAT = 'nat'
    MODO_COACH = 'coach'
    MODO_IA_CAMPO = 'ia_campo'
    MODO_VENTAS = 'ventas'
    MODO_CURSOS = 'cursos'
    MODO_CHOICES = [
        (MODO_MENU, 'Menú'),
        (MODO_AGENTES, 'Submenú agentes'),
        (MODO_NAT, 'Agrónomo (Nat)'),
        (MODO_COACH, 'Coach'),
        (MODO_IA_CAMPO, 'IA para el campo'),
        (MODO_VENTAS, 'Ventas y comercialización'),
        ('finanzas', 'Experto en finanzas'),
        ('cafe', 'Experto en café'),
        (MODO_CURSOS, 'Cursos'),
        ('formacion', 'Formación'),
        ('asesoria', 'Asesoría'),
    ]

    telefono = models.CharField(max_length=30, db_index=True)
    phone_id = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Línea Meta',
        help_text='Phone number id de la línea. Vacío = sesión anterior a las dos líneas.',
    )
    modo = models.CharField(max_length=16, choices=MODO_CHOICES, default=MODO_MENU)
    # Historial Nat/BOT_COMERCIAL solo cuenta mensajes posteriores a este corte.
    memoria_corte_en = models.DateTimeField(null=True, blank=True)
    habeas_aceptado = models.BooleanField(
        default=False,
        help_text='Aceptó tratamiento de datos en la línea Meta antes del menú.',
    )
    plan = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=PLAN_LINEA_CHOICES,
        verbose_name='Plan (solo esta persona)',
        help_text='Vacío = usa el plan de su grupo y, si el grupo no tiene, el de su organización.',
    )
    preguntas_mes = models.PositiveIntegerField(default=0, verbose_name='Preguntas al asesor (mes)')
    preguntas_mes_desde = models.DateField(
        null=True,
        blank=True,
        help_text='Primer día del mes al que corresponde el contador de preguntas.',
    )
    racha_actual = models.PositiveIntegerField(default=0, verbose_name='Racha (días seguidos)')
    racha_maxima = models.PositiveIntegerField(default=0, verbose_name='Récord de racha')
    racha_ultimo_dia = models.DateField(null=True, blank=True, verbose_name='Último día activo')
    aviso_pendiente = models.CharField(
        max_length=300,
        blank=True,
        default='',
        help_text='Línea de racha/insignia que va al inicio del próximo mensaje del día.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sesión menú sandbox'
        verbose_name_plural = 'Sesiones menú sandbox'
        constraints = [
            models.UniqueConstraint(
                fields=('telefono', 'phone_id'),
                name='uniq_sandbox_sesion_tel_linea',
            ),
        ]

    def __str__(self):
        return f'{self.telefono} → {self.modo}'


class EventOutbox(models.Model):
    """Outbox transaccional hacia Data Lake raw (Event Engine v0)."""

    event_id = models.UUIDField(unique=True, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    schema_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField(db_index=True)
    ingested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    org_id = models.IntegerField(null=True, blank=True, db_index=True)
    territory_id = models.CharField(max_length=32, blank=True, default='', db_index=True)
    actor_pseudo = models.CharField(max_length=64, blank=True, default='')
    session_or_trace_id = models.CharField(max_length=64, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    correlation_ids = models.JSONField(default=list, blank=True)
    pii_class = models.CharField(max_length=32, default='internal')
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    lake_uri = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        verbose_name = 'Evento outbox'
        verbose_name_plural = 'Eventos outbox'
        ordering = ['-ingested_at']
        indexes = [
            models.Index(fields=['published_at', 'id']),
            models.Index(fields=['event_type', '-occurred_at']),
        ]

    def __str__(self):
        return f'{self.event_type} ({self.event_id})'


class SenalTerritorial(models.Model):
    """Señal tipada para correlación territorial (ej. salud.sintoma.diarrea)."""

    tipo = models.CharField(
        max_length=80,
        db_index=True,
        help_text='Ej: salud.sintoma.diarrea',
    )
    territory_id = models.CharField(max_length=32, db_index=True)
    org_id = models.IntegerField(null=True, blank=True, db_index=True)
    confianza = models.FloatField(default=0.7)
    fuente = models.CharField(max_length=40, default='manual')
    occurred_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Señal territorial'
        verbose_name_plural = 'Señales territoriales'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['territory_id', 'tipo', '-occurred_at']),
        ]

    def __str__(self):
        return f'{self.tipo} @ {self.territory_id}'


class AlertaTerritorial(models.Model):
    """Cluster detectado (density_v0) sobre SenalTerritorial."""

    ESTADO_DETECTADA = 'detectada'
    ESTADO_VALIDADA = 'validada'
    ESTADO_COMUNICADA = 'comunicada'
    ESTADO_ACCIONADA = 'accionada'
    ESTADO_CERRADA = 'cerrada'
    ESTADO_CHOICES = [
        (ESTADO_DETECTADA, 'Detectada'),
        (ESTADO_VALIDADA, 'Validada'),
        (ESTADO_COMUNICADA, 'Comunicada'),
        (ESTADO_ACCIONADA, 'Accionada'),
        (ESTADO_CERRADA, 'Cerrada'),
    ]

    familia = models.CharField(max_length=80, db_index=True)
    subtipo = models.CharField(max_length=80, default='cluster')
    territory_id = models.CharField(max_length=32, db_index=True)
    ventana_horas = models.PositiveIntegerField(default=72)
    conteo = models.PositiveIntegerField(default=0)
    score = models.FloatField(default=0.0)
    min_k = models.PositiveIntegerField(default=3)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_DETECTADA,
        db_index=True,
    )
    explicacion = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alerta territorial'
        verbose_name_plural = 'Alertas territoriales'
        ordering = ['-actualizado_en']
        indexes = [
            models.Index(fields=['territory_id', 'estado', '-score']),
        ]

    def __str__(self):
        return f'{self.familia}.{self.subtipo} @ {self.territory_id} n={self.conteo}'


__all__ = [
    'TemaCampana', 'Cliente', 'Estudiante', 'Plantilla', 'Linea',
    'Campana', 'EnvioLog', 'WhatsappLog',
    'SesionComercial',
    'Curso', 'ConfiguracionDripCliente', 'HabilitacionModuloDripCliente',
    'HabilitacionModuloEstudiante', 'DocumentoRAG', 'DocumentoRAGComercial', 'Modulo',
    'ProgresoEstudiante', 'ModuloCompletado',
    'Examen', 'PreguntaExamen', 'ResultadoExamen',
    'ObjetivoCurso', 'RubricaEvaluacion', 'EjercicioPractico', 'RespuestaEjercicio',
    'InteraccionLog', 'SolicitudSoporte', 'PreguntaModulo',
    'PerfilGamificacion', 'Badge', 'BadgeEstudiante', 'TransaccionPuntos',
    'EvaluacionNotaGamificacion',
    'Certificado', 'PlantillaCertificado',
    'NotaEstudiante',
    'AuditLog',
    'GrupoEstudiantes', 'EnvioProgramado', 'PQRS',
    'ArchivoModulo', 'GrupoWhatsApp', 'InvitacionGrupo',
    'CampanaUnica', 'RespuestaCampanaUnica',
    'ProspectoB2B', 'CampanaB2B',
    'AliadoEmpleabilidad', 'MisionEmpleabilidad', 'PreguntaAbiertaFinalCurso', 'RespuestaAbiertaFinal',
    'ConfiguracionGlobal',
    'EventoIA',
    'ContextoAgroSession',
    'ConversacionRAGCandidata',
    'ProductoComercial',
    'ProductoCatalogo',
    'SandboxCanalSesion',
    'EventOutbox',
    'SenalTerritorial',
    'AlertaTerritorial',
    'VideoEnlace', 'VideoView',
    'PlantillaMeta',
    'TarjetaPlantillaMeta',
    'CampanaMeta',
    'EnvioCampanaMeta',
    'WebhookEventoProcesado',
    'WebhookFallido',
]
