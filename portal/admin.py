from django.contrib import admin
from .models import PortalUsuario


@admin.register(PortalUsuario)
class PortalUsuarioAdmin(admin.ModelAdmin):
    list_display = ['user', 'organizacion', 'rol']
    list_filter = ['rol', 'organizacion']
    search_fields = ['user__username', 'organizacion__nombre']
    autocomplete_fields = ['user', 'organizacion']
