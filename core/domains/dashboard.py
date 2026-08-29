"""
Parte 1 — modelo de dashboards unificados.

Visión de producto (Inicio ≠ Analítica):
- /admin/ (Inicio) = pulso del día + atajos + grafo ecosistema.
- /admin/dashboard/ = analítica profunda por dominio (default: Learning).
- Tab executive = filtros/Excel del pulso (no duplicar Inicio; acceso secundario).

| Tab canónico | Etiqueta UI           | Para qué sirve                              |
|--------------|-----------------------|---------------------------------------------|
| learning     | Cursos y avance       | Reportes B2B, métricas org, embudo, GEI     |
| retencion    | Centro de Éxito       | Riesgo, mapa caídas, consultor              |
| commercial   | Nat / comercial       | Nat, prospectos, campañas                   |
| ai_ops       | IA y Twilio           | Bot, Twilio, activaciones, RAG              |
| executive    | Pulso (filtros)       | KPIs filtrables + Excel (detalle Inicio)    |
"""

from __future__ import annotations

# Default al abrir /admin/dashboard/ sin ?tab= → Learning (no solapa Inicio).
DASHBOARD_DEFAULT_TAB = 'learning'

DASHBOARD_TABS: dict[str, dict] = {
    'executive': {
        'label': 'Pulso (filtros)',
        'panel_id': 'tab-resumen',
        'legacy_aliases': ['resumen'],
        'blurb': 'KPIs filtrables y Excel. El resumen del día vive en Inicio.',
    },
    'learning': {
        'label': 'Cursos y avance',
        'panel_id': None,
        'legacy_aliases': ['reportes', 'metricas_empresa', 'embudo'],
        'sections': ['reportes', 'metricas_empresa', 'embudo', 'gei'],
        'default_section': 'reportes',
        'blurb': 'Reportes B2B, semáforos por empresa, embudo por módulo.',
    },
    'ai_ops': {
        'label': 'IA y Twilio',
        'panel_id': 'tab-auditoria',
        'legacy_aliases': ['auditoria'],
        'blurb': 'Salud del bot, entregas Twilio y activaciones IA.',
    },
    'commercial': {
        'label': 'Nat / comercial',
        'panel_id': 'tab-metricas_nati',
        'legacy_aliases': ['metricas_nati'],
        'blurb': 'Sesiones Nat, catálogo y señal comercial.',
    },
    'retencion': {
        'label': 'Centro de Éxito',
        'panel_id': 'tab-retencion',
        'legacy_aliases': ['retention'],
        'blurb': 'Quién contactar hoy, mapa de caídas, consultor.',
    },
}

LEARNING_SECTION_PANELS = {
    'reportes': 'tab-reportes',
    'metricas_empresa': 'tab-metricas_empresa',
    'embudo': 'tab-embudo-learning',
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
    raw = (tab or DASHBOARD_DEFAULT_TAB).strip().lower()
    for canonical, meta in DASHBOARD_TABS.items():
        if raw == canonical or raw in meta.get('legacy_aliases', []):
            return canonical
    return DASHBOARD_DEFAULT_TAB


def resolve_learning_section(tab: str | None, section: str | None) -> str:
    sec = (section or '').strip().lower()
    learning = DASHBOARD_TABS['learning']
    if sec in learning.get('sections', []):
        return sec
    if tab in LEARNING_SECTION_PANELS:
        return tab
    return learning['default_section']
