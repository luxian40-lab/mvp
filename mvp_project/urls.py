from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse


def root_redirect(request):
    """Raíz según subdominio (Cloudflare) o admin por defecto."""
    host = request.get_host().split(':')[0].lower()
    if host == 'app.eki.technology':
        return redirect('/portal/login/')
    if host == 'admin.eki.technology':
        return redirect('/admin/')
    if host in ('aprende.eki.technology', 'aula.eki.technology'):
        return redirect('/aprende/')
    if host == 'studio.eki.technology':
        return redirect('/studio/')
    if host == 'certificados.eki.technology':
        return redirect('/verificar/')
    return redirect('/admin/')


def health_check(request):
    """Health check para AWS Elastic Beanstalk"""
    return HttpResponse("OK", content_type="text/plain")


urlpatterns = [
    # Health check (DEBE estar primero)
    path('health/', health_check, name='health_check'),
    path('healthz/', health_check, name='health_check_z'),

    # Rutas funcionales separadas por dominio
    path('', include('core.urls.admin_urls')),
    path('', include('core.urls.webhook_urls')),
    path('', include('integrations.urls')),
    path('', include('core.urls.certificados_urls')),
    path('', include('core.urls.media_urls')),
    path('portal/', include('portal.urls')),
    path('aprende/', include('aprende.urls')),
    path('studio/', include('studio.urls')),

    # Admin de Django
    path('admin/', admin.site.urls),

    # Raíz
    path('', root_redirect),
]

# Servir archivos estáticos Y multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
