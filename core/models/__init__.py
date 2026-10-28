"""Modelos de core, uno o varios submódulos por dominio (fase H1).

Este archivo solo reexporta, en el orden en que se cargan los modelos.
"""
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
from core.models.avisos import (  # noqa: F401
    AvisoModuloDisponible,
    AvisoModuloEnviado,
    RecordatorioCurso,
    RecordatorioCursoEnviado,
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


from core.models.territorio import (  # noqa: F401
    SenalTerritorial,
    AlertaTerritorial,
)


from core.models.negocio import (  # noqa: F401
    FichaNegocio,
)


__all__ = [
    'TemaCampana', 'Cliente', 'Estudiante', 'Plantilla', 'Linea',
    'Campana', 'EnvioLog', 'WhatsappLog',
    'SesionComercial',
    'Curso', 'ConfiguracionDripCliente', 'HabilitacionModuloDripCliente',
    'HabilitacionModuloEstudiante', 'AvisoModuloDisponible', 'AvisoModuloEnviado',
    'RecordatorioCurso', 'RecordatorioCursoEnviado', 'DocumentoRAG', 'DocumentoRAGComercial', 'Modulo',
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
    'FichaNegocio',
    'VideoEnlace', 'VideoView',
    'PlantillaMeta',
    'TarjetaPlantillaMeta',
    'CampanaMeta',
    'EnvioCampanaMeta',
    'WebhookEventoProcesado',
    'WebhookFallido',
]
