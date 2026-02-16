from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from core.views import (
    dashboard_view, 
    whatsapp_webhook, 
    descargar_reportes, 
    importar_estudiantes,
    calendario_campanas_view,
    conversaciones_view,
    instrucciones_view,
    obtener_archivos_modulo_view,
    descargar_archivo_multimedia,
    stream_media,
    test_email_gmail_view,
    subir_documento_curso,
    vista_previa_curso_ia,
    serve_media_proxy,
    dashboard_unificado
)
from core.api import api_estudiante, api_estudiante_progreso, api_estudiante_siguiente_tarea
from core.dashboard_avanzado import dashboard_metricas, dashboard_gerencial
from core.views_certificados import verificar_certificado_view, descargar_certificado_view
from core.views_analytics import dashboard_analytics, exportar_metricas_csv, api_metricas_json, detalle_estudiante
from core.views_reportes import dashboard_reportes_avanzados, descargar_reporte_xlsx


def root_redirect(request):
    """Redirige a la página de administración principal"""
    return redirect('/admin/')


def health_check(request):
    """Health check para AWS Elastic Beanstalk"""
    return HttpResponse("OK", content_type="text/plain")


urlpatterns = [
    # Health check (DEBE estar primero)
    path('health/', health_check, name='health_check'),
    
    # Vistas personalizadas ANTES del admin para que no sean capturadas por catch-all
    path('admin/dashboard/', dashboard_unificado, name='dashboard_unificado'),  # Dashboard único
    path('admin/dashboard-antiguo/', dashboard_view, name='dashboard_antiguo'),  # Dashboard antiguo
    path('admin/descargar-reportes/', descargar_reportes, name='descargar_reportes'),
    path('admin/importar-estudiantes/', importar_estudiantes, name='importar_estudiantes'),
    path('admin/calendario/', calendario_campanas_view, name='calendario_campanas'),
    path('admin/conversaciones/', conversaciones_view, name='conversaciones'),
    path('admin/instrucciones/', instrucciones_view, name='instrucciones'),
    path('admin/test-email/', test_email_gmail_view, name='test_email_gmail'),
    
        # Dashboard ejecutivo (metrics)
        path('admin/dashboard-metrics/', dashboard_metricas, name='dashboard_metrics'),
        # Dashboard analytics (avanzado)
        path('admin/dashboard-analytics/', dashboard_analytics, name='dashboard_analytics_view'),
    # Dashboard de Analíticas Educativas
    path('admin/analytics/', dashboard_analytics, name='dashboard_analytics'),
    path('admin/analytics/export/', exportar_metricas_csv, name='exportar_metricas_csv'),
    path('admin/analytics/api/', api_metricas_json, name='api_metricas_json'),
    path('admin/analytics/estudiante/<int:estudiante_id>/', detalle_estudiante, name='detalle_estudiante'),
    
    # Dashboard de Reportes Avanzados (Municipios y Canales)
    path('admin/reportes-avanzados/', dashboard_reportes_avanzados, name='dashboard_reportes_avanzados'),
    path('admin/reportes-avanzados/descargar/', descargar_reporte_xlsx, name='descargar_reporte_xlsx'),
    
    # Generación de cursos con IA
    path('admin/crear-curso-ia/', subir_documento_curso, name='subir_documento_curso'),
    path('admin/vista-previa-curso-ia/', vista_previa_curso_ia, name='vista_previa_curso_ia'),
    
    # Dashboard gerencial
    path('admin/dashboard-gerencial/', dashboard_gerencial, name='dashboard_gerencial'),
    
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Webhook y APIs
    path('webhook/whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    
    # API REST para progreso
    path('api/estudiante/<str:telefono>/', api_estudiante, name='api_estudiante'),
    path('api/estudiante/<str:telefono>/progreso/', api_estudiante_progreso, name='api_estudiante_progreso'),
    path('api/estudiante/<str:telefono>/siguiente-tarea/', api_estudiante_siguiente_tarea, name='api_estudiante_siguiente_tarea'),
    
    # Certificados públicos (sin autenticación)
    path('verificar-certificado/<str:codigo_verificacion>/', verificar_certificado_view, name='verificar_certificado'),
    path('descargar-certificado/<str:codigo_verificacion>/', descargar_certificado_view, name='descargar_certificado'),
    
    # Archivos multimedia de módulos
    path('media/modulo/<int:modulo_id>/archivos/', obtener_archivos_modulo_view, name='obtener_archivos_modulo'),
    path('media/stream/', stream_media, name='stream_media'),
    path('media/descargar-archivo/<int:archivo_id>/', descargar_archivo_multimedia, name='descargar_archivo_multimedia'),
    
    # Proxy para archivos multimedia
    path('media-proxy/<str:filename>', serve_media_proxy, name='media_proxy'),
    
    # Raíz
    path('', root_redirect),
]

# Servir archivos estáticos Y multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
