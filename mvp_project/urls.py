from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse


def root_redirect(request):
    """Redirige a la página de administración principal"""
    return redirect('/admin/')


def health_check(request):
    """Health check para AWS Elastic Beanstalk"""
    return HttpResponse("OK", content_type="text/plain")


urlpatterns = [
    # Health check (DEBE estar primero)
    path('health/', health_check, name='health_check'),

    # Rutas funcionales separadas por dominio
    path('', include('core.urls.admin_urls')),
    path('', include('core.urls.webhook_urls')),
    path('', include('integrations.urls')),
    path('', include('core.urls.certificados_urls')),
    path('', include('core.urls.media_urls')),

    # Admin de Django
    path('admin/', admin.site.urls),

    # Raíz
    path('', root_redirect),
]

# Servir archivos estáticos Y multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
