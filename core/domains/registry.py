"""
Registro de bounded contexts — mapa Parte 0 de la hoja de ruta CTO.

| Dominio              | Responsabilidad                                      | Apps / módulos actuales              |
|----------------------|------------------------------------------------------|--------------------------------------|
| core                 | Identidad, clientes, estudiantes, admin base         | core.models, core.views              |
| learning             | Cursos, módulos, progreso, checkpoints, certificados | core.helpers_examenes, drip, tutor   |
| agents_edu           | Darío, Claudia, facilitadora, tutor módulo           | core.agentes_ia, core.tutor_ia_modulo|
| agents_commercial    | Nati, RAG comercial, prospectos                      | core.nati, core.rag_comercial_*      |
| analytics            | KPIs, semáforos, reportes B2B, métricas empresa/Nati | core.metricas_empresa, dashboard   |
| integrations         | Twilio, WhatsApp logs, Celery externos               | core.tasks, webhooks                 |
| formulario           | GEI, encuestas dinámicas                             | formulario.*                         |
"""

from __future__ import annotations

from typing import Any

DOMAIN_REGISTRY: dict[str, dict[str, Any]] = {
    'core': {
        'label': 'Core',
        'django_app': 'core',
        'description': 'Clientes, estudiantes, autenticación admin, utilidades compartidas.',
        'modules': ['core.models', 'core.utils_telefono', 'core.views'],
    },
    'learning': {
        'label': 'Learning',
        'django_app': 'learning',
        'description': 'Cursos, progreso, drip, checkpoints y certificación.',
        'modules': [
            'core.domains.learning.checkpoints',
            'core.drip_schedule',
            'core.module_steps',
        ],
    },
    'agents_edu': {
        'label': 'Agentes educativos',
        'django_app': 'agents_edu',
        'description': 'Darío, Claudia, facilitadora y tutor por módulo.',
        'modules': ['core.agentes_ia', 'core.tutor_ia_modulo'],
    },
    'agents_commercial': {
        'label': 'Agentes comerciales',
        'django_app': 'agents_commercial',
        'description': 'Nati, RAG comercial y bot de ventas.',
        'modules': ['core.nati', 'core.rag_comercial_manager', 'core.knowledge_studio'],
    },
    'analytics': {
        'label': 'Analytics',
        'django_app': 'analytics',
        'description': 'Métricas, semáforos, dashboards y exportaciones.',
        'modules': [
            'core.domains.analytics.metricas',
            'analytics.exports',
            'core.domains.dashboard',
        ],
    },
    'integrations': {
        'label': 'Integraciones',
        'django_app': 'integrations',
        'description': 'API REST LXP / Angular, CORS.',
        'modules': ['integrations.urls', 'core.api'],
    },
    'formulario': {
        'label': 'Formularios',
        'django_app': 'formulario',
        'description': 'GEI y flujos de encuesta WhatsApp.',
        'modules': ['formulario.gei_flujos', 'formulario.agent'],
    },
}


def get_domain(name: str) -> dict[str, Any] | None:
    return DOMAIN_REGISTRY.get(name)
