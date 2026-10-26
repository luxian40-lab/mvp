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


from core.models.configuracion import (  # noqa: F401
    ConfiguracionGlobal,
)


from core.models.ia import (  # noqa: F401
    EventoIA,
    ContextoAgroSession,
    ConversacionRAGCandidata,
)


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
