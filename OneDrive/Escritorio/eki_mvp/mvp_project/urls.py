from django.contrib import admin
from django.urls import path
from core.views import dashboard_view

urlpatterns = [
    path('admin/dashboard/', dashboard_view, name='dashboard'),
    path('admin/', admin.site.urls),
]