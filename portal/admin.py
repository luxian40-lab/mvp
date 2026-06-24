from django.contrib import admin
from django.utils.html import format_html

from .models import PortalUsuario


@admin.register(PortalUsuario)
class PortalUsuarioAdmin(admin.ModelAdmin):
    list_display = ['user', 'organizacion', 'rol_badge', 'aula_web']
    list_filter = ['rol', 'organizacion']
    search_fields = ['user__username', 'user__email', 'organizacion__nombre']
    autocomplete_fields = ['user', 'organizacion']
    list_per_page = 50

    @admin.display(description='Rol')
    def rol_badge(self, obj):
        colors = {'admin': '#7c3aed', 'profesor': '#0d9488', 'viewer': '#64748b'}
        color = colors.get(obj.rol, '#64748b')
        return format_html(
            '<span style="background:{}22;color:{};padding:2px 8px;border-radius:6px;font-size:0.8rem;">{}</span>',
            color, color, obj.get_rol_display(),
        )

    @admin.display(description='Aula web')
    def aula_web(self, obj):
        if obj.rol in ('admin', 'profesor'):
            return format_html('<a href="/aprende/profesor/login/" target="_blank">Entrar ↗</a>')
        return '—'
