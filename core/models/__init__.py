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

from core.models.campanas_b2b import (  # noqa: F401
    CampanaUnica,
    RespuestaCampanaUnica,
    ProspectoB2B,
    CampanaB2B,
)


from core.models.empleabilidad import (  # noqa: F401
    AliadoEmpleabilidad,
    MisionEmpleabilidad,
)


from core.models.pregunta_final import (  # noqa: F401
    PreguntaAbiertaFinalCurso,
    RespuestaAbiertaFinal,
)


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
