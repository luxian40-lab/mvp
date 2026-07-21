"""
Parte 1 — modelo de dashboards unificados.

| Tab canónico | Etiqueta UI           | Contenido legacy                    |
|--------------|-----------------------|-------------------------------------|
| executive    | Executive             | KPIs, semáforos, health (resumen)   |
| learning     | Learning Analytics    | Reportes B2B, métricas empresa, GEI |
| ai_ops       | AI Operations         | Bot, Twilio, activaciones IA, RAG   |
| commercial   | Commercial CRM        | Nati, prospectos, campañas          |
| retencion    | Centro de Éxito       | Riesgo, mapa, embudo, consultor     |
"""

from __future__ import annotations

DASHBOARD_TABS: dict[str, dict] = {
    'executive': {
        'label': 'Executive',
        'panel_id': 'tab-resumen',
        'legacy_aliases': ['resumen'],
    },
    'learning': {
        'label': 'Learning Analytics',
        'panel_id': None,
        'legacy_aliases': ['reportes', 'metricas_empresa'],
        'sections': ['reportes', 'metricas_empresa', 'gei'],
        'default_section': 'reportes',
    },
    'ai_ops': {
        'label': 'AI Operations',
        'panel_id': 'tab-auditoria',
        'legacy_aliases': ['auditoria'],
    },
    'commercial': {
        'label': 'Commercial CRM',
        'panel_id': 'tab-metricas_nati',
        'legacy_aliases': ['metricas_nati'],
    },
    'retencion': {
        'label': 'Retención',
        'panel_id': 'tab-retencion',
        'legacy_aliases': ['retention', 'embudo'],
    },
}

LEARNING_SECTION_PANELS = {
    'reportes': 'tab-reportes',
    'metricas_empresa': 'tab-metricas_empresa',
}

LEGACY_DASHBOARD_REDIRECTS: dict[str, dict[str, str]] = {
    'dashboard_antiguo': {'tab': 'executive'},
    'dashboard_gerencial': {'tab': 'executive'},
    'dashboard_metrics': {'tab': 'ai_ops'},
    'dashboard_analytics': {'tab': 'learning', 'section': 'metricas_empresa'},
    'dashboard_reportes_avanzados': {'tab': 'learning', 'section': 'reportes'},
}

API_TIPO_ALIASES = {
    'learning': 'metricas_empresa',
    'commercial': 'metricas_nati',
}


def resolve_dashboard_tab(tab: str | None) -> str:
    raw = (tab or 'executive').strip().lower()
    for canonical, meta in DASHBOARD_TABS.items():
        if raw == canonical or raw in meta.get('legacy_aliases', []):
            return canonical
    return 'executive'


def resolve_learning_section(tab: str | None, section: str | None) -> str:
    sec = (section or '').strip().lower()
    learning = DASHBOARD_TABS['learning']
    if sec in learning.get('sections', []):
        return sec
    if tab in LEARNING_SECTION_PANELS:
        return tab
    return learning['default_section']
