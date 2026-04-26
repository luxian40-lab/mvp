from django.urls import path

from core.dashboard_avanzado import dashboard_metricas, dashboard_gerencial
from core.views import (
    bot_comercial_admin_view,
    calendario_campanas_view,
    conversaciones_view,
    dashboard_unificado,
    dashboard_unificado_resumen_data,
    dashboard_view,
    descargar_reportes,
    importar_estudiantes,
    importar_prospectos,
    instrucciones_view,
    subir_documento_curso,
    test_email_gmail_view,
    vista_previa_curso_ia,
)
from core.views_admin_analytics import (
    api_metricas_json,
    dashboard_analytics,
    detalle_estudiante,
    exportar_metricas_csv,
)
from core.views_analytics import gei_panel_view
from core.views_reportes import dashboard_reportes_avanzados, descargar_reporte_xlsx

urlpatterns = [
    path('admin/dashboard/', dashboard_unificado, name='dashboard_unificado'),
    path(
        'admin/dashboard/resumen-data/',
        dashboard_unificado_resumen_data,
        name='dashboard_unificado_resumen_data',
    ),
    path('admin/dashboard-antiguo/', dashboard_view, name='dashboard_antiguo'),
    path('admin/descargar-reportes/', descargar_reportes, name='descargar_reportes'),
    path('admin/importar-estudiantes/', importar_estudiantes, name='importar_estudiantes'),
    path('admin/importar-prospectos/', importar_prospectos, name='importar_prospectos'),
    path('admin/calendario/', calendario_campanas_view, name='calendario_campanas'),
    path('admin/conversaciones/', conversaciones_view, name='conversaciones'),
    path('admin/instruccion/', instrucciones_view, name='instruccion_alias'),
    path('admin/instrucciones/', instrucciones_view, name='instrucciones'),
    path('admin/bot-comercial/', bot_comercial_admin_view, name='bot_comercial_admin_view'),
    path('admin/test-email/', test_email_gmail_view, name='test_email_gmail'),
    path('admin/dashboard-metrics/', dashboard_metricas, name='dashboard_metrics'),
    path('admin/dashboard-analytics/', dashboard_analytics, name='dashboard_analytics_view'),
    path('admin/analytics/', dashboard_analytics, name='dashboard_analytics'),
    path('admin/analytics/export/', exportar_metricas_csv, name='exportar_metricas_csv'),
    path('admin/analytics/api/', api_metricas_json, name='api_metricas_json'),
    path('admin/analytics/estudiante/<int:estudiante_id>/', detalle_estudiante, name='detalle_estudiante'),
    path('admin/reportes-avanzados/', dashboard_reportes_avanzados, name='dashboard_reportes_avanzados'),
    path('admin/reportes-avanzados/descargar/', descargar_reporte_xlsx, name='descargar_reporte_xlsx'),
    path('admin/crear-curso-ia/', subir_documento_curso, name='subir_documento_curso'),
    path('admin/vista-previa-curso-ia/', vista_previa_curso_ia, name='vista_previa_curso_ia'),
    path('admin/dashboard-gerencial/', dashboard_gerencial, name='dashboard_gerencial'),
    path('admin/gei/panel/', gei_panel_view, name='gei_panel'),
]
