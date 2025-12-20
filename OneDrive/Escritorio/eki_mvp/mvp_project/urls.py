from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from core.views import dashboard_view, whatsapp_webhook, descargar_reportes, importar_estudiantes
from core.api import api_estudiante, api_estudiante_progreso, api_estudiante_siguiente_tarea


def root_redirect(request):
    """Redirige a la página de administración principal"""
    return redirect('/admin/')


urlpatterns = [
    # Vistas personalizadas ANTES del admin para que no sean capturadas por catch-all
    path('admin/dashboard/', dashboard_view, name='dashboard'),
    path('admin/descargar-reportes/', descargar_reportes, name='descargar_reportes'),
    path('admin/importar-estudiantes/', importar_estudiantes, name='importar_estudiantes'),
    
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Webhook y APIs
    path('webhook/whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    
    # API REST para progreso
    path('api/estudiante/<str:telefono>/', api_estudiante, name='api_estudiante'),
    path('api/estudiante/<str:telefono>/progreso/', api_estudiante_progreso, name='api_estudiante_progreso'),
    path('api/estudiante/<str:telefono>/siguiente-tarea/', api_estudiante_siguiente_tarea, name='api_estudiante_siguiente_tarea'),
    
    # Raíz
    path('', root_redirect),
]

# Servir archivos estáticos en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
