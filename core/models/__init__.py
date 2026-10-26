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


from core.models.canal import (  # noqa: F401
    SandboxCanalSesion,
    EventOutbox,
)


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
