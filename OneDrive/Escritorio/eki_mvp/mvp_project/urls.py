from django.contrib import admin
from django.urls import path
from core.views import dashboard_view, whatsapp_webhook

urlpatterns = [
    path('admin/dashboard/', dashboard_view, name='dashboard'),
    path('webhook/whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('admin/', admin.site.urls),
]
