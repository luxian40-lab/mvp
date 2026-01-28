from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
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
    test_email_gmail_view,
    subir_documento_curso,
    vista_previa_curso_ia
)
from core.api import api_estudiante, api_estudiante_progreso, api_estudiante_siguiente_tarea
from core.dashboard_avanzado import dashboard_metricas
from core.views_certificados import verificar_certificado_view, descargar_certificado_view




# Redirigir la raíz al login del admin
def root_redirect(request):
    return redirect('/admin/login/?next=/admin/')


urlpatterns = [
    # Vistas personalizadas ANTES del admin para que no sean capturadas por catch-all
    path('admin/dashboard/', dashboard_metricas, name='dashboard_metricas'),  # Dashboard excepcional
    path('admin/dashboard-antiguo/', dashboard_view, name='dashboard_antiguo'),  # Dashboard antiguo
    path('admin/descargar-reportes/', descargar_reportes, name='descargar_reportes'),
    path('admin/importar-estudiantes/', importar_estudiantes, name='importar_estudiantes'),
    path('admin/calendario/', calendario_campanas_view, name='calendario_campanas'),
    path('admin/conversaciones/', conversaciones_view, name='conversaciones'),
    path('admin/instrucciones/', instrucciones_view, name='instrucciones'),
    path('admin/test-email/', test_email_gmail_view, name='test_email_gmail'),
    
    # Generación de cursos con IA
    path('admin/crear-curso-ia/', subir_documento_curso, name='subir_documento_curso'),
    path('admin/vista-previa-curso-ia/', vista_previa_curso_ia, name='vista_previa_curso_ia'),
    
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
    path('media/descargar-archivo/<int:archivo_id>/', descargar_archivo_multimedia, name='descargar_archivo_multimedia'),
    
    # Raíz: redirige al login del admin
    path('', root_redirect),
]

# Servir archivos estáticos Y multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
