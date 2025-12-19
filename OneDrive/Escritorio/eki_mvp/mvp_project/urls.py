from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from core.views import dashboard_view, whatsapp_webhook, descargar_reportes, importar_estudiantes


def root_redirect(request):
    return redirect('dashboard')


urlpatterns = [
    path('', root_redirect),
    path('admin/dashboard/', dashboard_view, name='dashboard'),
    path('admin/descargar-reportes/', descargar_reportes, name='descargar_reportes'),
    path('admin/importar-estudiantes/', importar_estudiantes, name='importar_estudiantes'),
    path('webhook/whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('admin/', admin.site.urls),
]
