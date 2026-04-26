"""
Wrapper module para endpoints de analytics admin.
"""

from core.views_analytics import (
    api_metricas_json,
    dashboard_analytics,
    detalle_estudiante,
    exportar_metricas_csv,
)

__all__ = [
    "dashboard_analytics",
    "exportar_metricas_csv",
    "api_metricas_json",
    "detalle_estudiante",
]
