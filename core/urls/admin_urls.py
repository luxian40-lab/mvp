from django.urls import path
from django.views.generic import RedirectView

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
    generando_curso_ia,
    api_estado_curso_ia,
    test_email_gmail_view,
    vista_previa_curso_ia,
)
from core.views_admin_analytics import (
    api_metricas_json,
    detalle_estudiante,
    exportar_metricas_csv,
    api_modulos_curso_json,
    api_guardar_metas_empresa,
)
from core.views_analytics import api_grupos_por_empresa, gei_panel_view
from core.views_eventos_ia import ai_ops_eventos_view, ai_ops_replay_view, api_eventos_ia_json
from core.views_knowledge_studio import knowledge_studio_revisar, knowledge_studio_view
from core.views_reportes import descargar_reporte_xlsx
from core.views_cobertura_admin import (
    cobertura_admin_api,
    cobertura_admin_municipios_geojson,
    cobertura_admin_view,
)
from core.views_avance_reset import ajustar_avance_view
from core.views_gamificacion_ajuste import gamificacion_ajuste_view
from core.views_certificados_presenciales import certificados_presenciales_view
from core.views_envio_certificados import envio_certificados_view
from core.views_drip_estudiantes import drip_estudiantes_view
from core.views_push_estudiantes import push_estudiantes_view
from aprende.views_admin import aula_web_admin_view
from core.views_copiar_curso import copiar_curso_cliente_view

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
    path('admin/copiar-curso/', copiar_curso_cliente_view, name='copiar_curso_cliente'),
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
    path('admin/analytics/api/modulos/', api_modulos_curso_json, name='api_modulos_curso'),
    path('admin/analytics/api/metas/', api_guardar_metas_empresa, name='api_guardar_metas_empresa'),
    path('admin/analytics/api/grupos/', api_grupos_por_empresa, name='api_grupos_por_empresa'),
    path('admin/analytics/estudiante/<int:estudiante_id>/', detalle_estudiante, name='detalle_estudiante'),
    path('admin/reportes-avanzados/', redirect_dashboard_reportes, name='dashboard_reportes_avanzados'),
    path('admin/reportes-avanzados/descargar/', descargar_reporte_xlsx, name='descargar_reporte_xlsx'),
    path('admin/crear-curso-ia/', subir_documento_curso, name='subir_documento_curso'),
    path('admin/crear-curso-ia/generando/', generando_curso_ia, name='generando_curso_ia'),
    path('admin/crear-curso-ia/estado/', api_estado_curso_ia, name='api_estado_curso_ia'),
    path('admin/vista-previa-curso-ia/', vista_previa_curso_ia, name='vista_previa_curso_ia'),
    path('admin/dashboard-gerencial/', redirect_dashboard_gerencial, name='dashboard_gerencial'),
    path('admin/gei/panel/', gei_panel_view, name='gei_panel'),
    path('admin/ai-ops/eventos/', ai_ops_eventos_view, name='ai_ops_eventos'),
    path('admin/ai-ops/api/eventos/', api_eventos_ia_json, name='api_eventos_ia'),
    path('admin/ai-ops/replay/<uuid:trace_id>/', ai_ops_replay_view, name='ai_ops_replay'),
    path('admin/cobertura/', cobertura_admin_view, name='admin_cobertura_mapa'),
    path('admin/cobertura/datos.json', cobertura_admin_api, name='admin_cobertura_api'),
    path('admin/cobertura/municipios.geojson', cobertura_admin_municipios_geojson, name='admin_cobertura_geojson'),
    path('admin/drip-estudiantes/', drip_estudiantes_view, name='admin_drip_estudiantes'),
    path('admin/ajustar-avance/', ajustar_avance_view, name='admin_ajustar_avance'),
    path('admin/gamificacion-ajuste/', gamificacion_ajuste_view, name='admin_gamificacion_ajuste'),
    path('admin/certificados-presenciales/', certificados_presenciales_view, name='admin_certificados_presenciales'),
    path('admin/envio-certificados/', envio_certificados_view, name='admin_envio_certificados'),
    path('admin/push-estudiantes/', push_estudiantes_view, name='admin_push_estudiantes'),
    path('admin/aula-web/', aula_web_admin_view, name='admin_aula_web'),
    path('admin/portal-estudio/', RedirectView.as_view(url='/admin/aula-web/', permanent=False), name='admin_portal_estudio'),
    path('admin/knowledge-studio/', knowledge_studio_view, name='knowledge_studio'),
    path(
        'admin/knowledge-studio/revisar/<int:candidata_id>/',
        knowledge_studio_revisar,
        name='knowledge_studio_revisar',
    ),
]
