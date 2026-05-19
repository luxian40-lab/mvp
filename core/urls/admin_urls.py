from django.urls import path

from core.dashboard_avanzado import exportar_metricas_excel
from core.dashboard_redirects import (
    redirect_dashboard_analytics,
    redirect_dashboard_antiguo,
    redirect_dashboard_gerencial,
    redirect_dashboard_metrics,
    redirect_dashboard_reportes,
)
from core.views import (
    bot_comercial_admin_view,
    calendario_campanas_view,
    conversaciones_view,
    dashboard_unificado,
    dashboard_unificado_resumen_data,
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
    detalle_estudiante,
    exportar_metricas_csv,
)
from core.views_analytics import gei_panel_view
from core.views_eventos_ia import ai_ops_eventos_view, ai_ops_replay_view, api_eventos_ia_json
from core.views_reportes import descargar_reporte_xlsx

urlpatterns = [
    path('admin/dashboard/', dashboard_unificado, name='dashboard_unificado'),
    path(
        'admin/dashboard/resumen-data/',
        dashboard_unificado_resumen_data,
        name='dashboard_unificado_resumen_data',
    ),
    path('admin/dashboard-antiguo/', redirect_dashboard_antiguo, name='dashboard_antiguo'),
    path('admin/descargar-reportes/', descargar_reportes, name='descargar_reportes'),
    path('admin/importar-estudiantes/', importar_estudiantes, name='importar_estudiantes'),
    path('admin/importar-prospectos/', importar_prospectos, name='importar_prospectos'),
    path('admin/calendario/', calendario_campanas_view, name='calendario_campanas'),
    path('admin/conversaciones/', conversaciones_view, name='conversaciones'),
    path('admin/instruccion/', instrucciones_view, name='instruccion_alias'),
    path('admin/instrucciones/', instrucciones_view, name='instrucciones'),
    path('admin/bot-comercial/', bot_comercial_admin_view, name='bot_comercial_admin_view'),
    path('admin/test-email/', test_email_gmail_view, name='test_email_gmail'),
    path('admin/dashboard-metrics/', redirect_dashboard_metrics, name='dashboard_metrics'),
    path('admin/dashboard-metrics/exportar/', exportar_metricas_excel, name='exportar_metricas_excel'),
    path('admin/dashboard-analytics/', redirect_dashboard_analytics, name='dashboard_analytics_view'),
    path('admin/analytics/', redirect_dashboard_analytics, name='dashboard_analytics'),
    path('admin/analytics/export/', exportar_metricas_csv, name='exportar_metricas_csv'),
    path('admin/analytics/api/', api_metricas_json, name='api_metricas_json'),
    path('admin/analytics/estudiante/<int:estudiante_id>/', detalle_estudiante, name='detalle_estudiante'),
    path('admin/reportes-avanzados/', redirect_dashboard_reportes, name='dashboard_reportes_avanzados'),
    path('admin/reportes-avanzados/descargar/', descargar_reporte_xlsx, name='descargar_reporte_xlsx'),
    path('admin/crear-curso-ia/', subir_documento_curso, name='subir_documento_curso'),
    path('admin/vista-previa-curso-ia/', vista_previa_curso_ia, name='vista_previa_curso_ia'),
    path('admin/dashboard-gerencial/', redirect_dashboard_gerencial, name='dashboard_gerencial'),
    path('admin/gei/panel/', gei_panel_view, name='gei_panel'),
    path('admin/ai-ops/eventos/', ai_ops_eventos_view, name='ai_ops_eventos'),
    path('admin/ai-ops/api/eventos/', api_eventos_ia_json, name='api_eventos_ia'),
    path('admin/ai-ops/replay/<uuid:trace_id>/', ai_ops_replay_view, name='ai_ops_replay'),
]
