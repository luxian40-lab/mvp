from core.admin._common import *  # noqa: F401,F403

# ========================================
# 🔐 AUDITORÍA - AUDIT LOG
# ========================================

class AuditLogAdmin(admin.ModelAdmin):
    """Admin para registro de auditoría de certificados"""
    
    list_display = ('get_resumen_corto', 'accion_badge', 'get_exitoso_display', 'fecha_accion', 'usuario')
    list_filter = ('accion', 'exitoso', 'fecha_accion')
    search_fields = ('certificado_codigo', 'estudiante_nombre', 'curso_nombre', 'ip_address')
    readonly_fields = ('fecha_accion', 'ip_address')
    date_hierarchy = 'fecha_accion'
    ordering = ('-fecha_accion',)
    
    fieldsets = (
        ('📋 Información General', {
            'fields': ('accion', 'exitoso', 'usuario', 'fecha_accion')
        }),
        ('📜 Certificado & Estudiante', {
            'fields': ('certificado_codigo', 'estudiante_nombre', 'curso_nombre')
        }),
        ('📝 Detalles', {
            'fields': ('descripcion', 'mensaje_error'),
            'classes': ('collapse',)
        }),
        ('🔍 Auditoría Técnica', {
            'fields': ('ip_address',),
            'classes': ('collapse',)
        }),
    )
    
    def get_resumen_corto(self, obj):
        """Muestra resumen en lista"""
        return f"{obj.get_accion_display()}: {obj.estudiante_nombre or 'Sistema'}"
    get_resumen_corto.short_description = 'Acción'
    
    def accion_badge(self, obj):
        """Muestra acción con badge de color"""
        from django.utils.html import format_html
        
        color_map = {
            'GENERAR': '#28a745',  # Verde
            'ENVIAR': '#17a2b8',   # Azul
            'DESCARGAR': '#007bff', # Azul claro
            'VERIFICAR': '#6c757d',  # Gris
            'MODIFICAR': '#ffc107',  # Amarillo
            'ELIMINAR': '#dc3545',   # Rojo
            'REGENERAR': '#fd7e14',  # Naranja
            'AUTO_GENERAR': '#20c997', # Verde agua
            'ERROR': '#dc3545',      # Rojo
        }
        
        color = color_map.get(obj.accion, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:3px;font-weight:bold;">{}</span>',
            color,
            obj.get_accion_display()
        )
    accion_badge.short_description = 'Acción'
    
    def get_exitoso_display(self, obj):
        """Muestra estado de éxito con icono"""
        from django.utils.html import format_html
        return format_html(
            '<span style="font-size: 18px;">{}</span>',
            '✅' if obj.exitoso else '❌'
        )
    get_exitoso_display.short_description = 'Estado'


# ========================================
# 🎯 CARGAR PERSONALIZACIÓN DEL DASHBOARD
# ========================================

# Importar y ejecutar la personalización del admin
try:
    from core.admin_dashboard import setup_custom_admin_dashboard
    setup_custom_admin_dashboard()
except Exception as e:
    logger.warning(f"No se pudo cargar la personalización del dashboard: {str(e)}")


