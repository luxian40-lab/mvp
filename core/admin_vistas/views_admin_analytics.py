"""
Wrapper module para endpoints de analytics admin.
"""

from core.views_analytics import (
    api_grupos_por_empresa,
    api_metricas_json,
    api_modulos_curso_json,
    api_guardar_metas_empresa,
    dashboard_analytics,
    detalle_estudiante,
    exportar_metricas_csv,
)

__all__ = [
    "dashboard_analytics",
    "exportar_metricas_csv",
    "api_metricas_json",
    "api_modulos_curso_json",
    "api_guardar_metas_empresa",
    "detalle_estudiante",
]
