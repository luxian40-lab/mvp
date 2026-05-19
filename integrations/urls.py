"""
Rutas de integración — fachada hacia core.api (migración gradual a integrations/).

Angular / LXP consumen estas URLs bajo el mismo host de eki.
"""

from django.urls import path

from core.api import (
    api_empleabilidad_claim,
    api_empleabilidad_completar,
    api_empleabilidad_flujo,
    api_empleabilidad_oportunidades,
    api_empleabilidad_resumen,
    api_estudiante,
    api_estudiante_progreso,
    api_estudiante_siguiente_tarea,
    api_integracion_educativa_metricas,
    api_integracion_empleabilidad_metricas,
    api_integracion_gei_detalle,
    api_integracion_gei_exportar,
)

urlpatterns = [
    path('api/estudiante/<str:telefono>/', api_estudiante, name='api_estudiante'),
    path('api/estudiante/<str:telefono>/progreso/', api_estudiante_progreso, name='api_estudiante_progreso'),
    path(
        'api/estudiante/<str:telefono>/siguiente-tarea/',
        api_estudiante_siguiente_tarea,
        name='api_estudiante_siguiente_tarea',
    ),
    path('api/empleabilidad/oportunidades/', api_empleabilidad_oportunidades, name='api_empleabilidad_oportunidades'),
    path('api/empleabilidad/claim/', api_empleabilidad_claim, name='api_empleabilidad_claim'),
    path('api/empleabilidad/completar/', api_empleabilidad_completar, name='api_empleabilidad_completar'),
    path('api/empleabilidad/flujo/', api_empleabilidad_flujo, name='api_empleabilidad_flujo'),
    path('api/empleabilidad/resumen/', api_empleabilidad_resumen, name='api_empleabilidad_resumen'),
    path(
        'api/integracion/educativa/metricas/',
        api_integracion_educativa_metricas,
        name='api_integracion_educativa_metricas',
    ),
    path(
        'api/integracion/empleabilidad/metricas/',
        api_integracion_empleabilidad_metricas,
        name='api_integracion_empleabilidad_metricas',
    ),
    path(
        'api/integracion/gei/detalle/',
        api_integracion_gei_detalle,
        name='api_integracion_gei_detalle',
    ),
    path(
        'api/integracion/gei/exportar/',
        api_integracion_gei_exportar,
        name='api_integracion_gei_exportar',
    ),
]
