from core.admin._common import *  # noqa: F401,F403

# ================================================
# 📊 DASHBOARD DE PLANTILLAS Y TEMPLATES
# ================================================

class PlantillaDashboardAdmin(admin.ModelAdmin):
    """Dashboard para ver el estado de plantillas y Content Templates"""
    list_display = ('nombre_con_emoji', 'categoria_display', 'estado_template', 'activa', 'veces_usada', 'fecha_modificacion')
    list_filter = ('activa', 'categoria', 'aprobada_twilio', 'fecha_modificacion')
    search_fields = ('nombre_interno', 'cuerpo_mensaje', 'twilio_template_sid')
    list_per_page = 50

    fieldsets = (
        ('📝 Información Básica', {
            'fields': ('nombre_interno', 'categoria', 'activa'),
            'description': 'Configura el nombre y categoría de la plantilla'
        }),
        ('🎨 Personalización Visual', {
            'fields': ('emoji',),
            'description': mark_safe('''<div style="background:#f5f5f5;padding:15px;border-radius:8px;margin-top:10px;">
                <strong>💡 El emoji se autocompletará según la categoría seleccionada arriba</strong><br><br>
                <strong>Categorías disponibles:</strong><br>
                🌾 Cultivos • 🐄 Ganadería • 🌱 General Agrícola • 📚 Educación • 💼 Gestión<br><br>
                <em>Puedes cambiar el emoji manualmente si lo deseas</em>
            </div>''')
        }),
        ('📄 Contenido del Mensaje', {
            'fields': ('cuerpo_mensaje',),
            'description': 'Escribe el mensaje. Usa {nombre} para personalizar con el nombre del estudiante.'
        }),
        ('🔗 Twilio Content Template (Opcional)', {
            'fields': ('twilio_template_sid', 'twilio_template_nombre', 'aprobada_twilio'),
            'description': mark_safe('''<div style="background:#fff3e0;padding:15px;border-radius:8px;border-left:4px solid #ff9800;">
                <strong>⚠️ IMPORTANTE: Para campañas con Content Templates</strong><br><br>
                <strong>Flujo correcto:</strong>
                <ol style="margin:10px 0;">
                    <li>🔵 Ve a <a href="https://console.twilio.com/us1/develop/sms/content-editor" target="_blank" style="color:#2196F3;">Twilio Content Editor</a></li>
                    <li>📝 Crea tu plantilla de WhatsApp y obtén el <strong>Content SID</strong> (ej: HX1234...)</li>
                    <li>⚙️ Configura el SID arriba y marca como "Aprobada en Twilio"</li>
                    <li>✅ Las campañas usarán este template automáticamente</li>
                </ol>
                <em>💡 Si no configuras esto, las campañas usarán envío directo (sin template).</em>
            </div>'''),
            'classes': ('collapse',)
        }),
    )

    def nombre_con_emoji(self, obj):
        return str(obj)
    nombre_con_emoji.short_description = "Plantilla"

    def categoria_display(self, obj):
        return obj.get_categoria_display()
    categoria_display.short_description = "Categoría"
    
    def estado_template(self, obj):
        if obj.twilio_template_sid and obj.aprobada_twilio:
            return format_html('<span style="background:#4caf50;color:white;padding:4px 8px;border-radius:12px;font-size:11px;">✅ TWILIO</span>')
        elif obj.twilio_template_sid and not obj.aprobada_twilio:
            return format_html('<span style="background:#ff9800;color:white;padding:4px 8px;border-radius:12px;font-size:11px;">⏳ PENDIENTE</span>')
        else:
            return format_html('<span style="background:#2196f3;color:white;padding:4px 8px;border-radius:12px;font-size:11px;">📱 DIRECTO</span>')
    estado_template.short_description = "Estado"
    
    def total_plantillas(self, obj):
        count = obj.plantillas.count()
        if count > 0:
            return format_html('<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>',
                count
            )
        return format_html('<span style="color:#999;">0</span>')
    total_plantillas.short_description = "📄 Plantillas"
    
    def total_campanas(self, obj):
        count = obj.campanas.count()
        if count > 0:
            return format_html('<span style="background:#2196f3;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>',
                count
            )
        return format_html('<span style="color:#999;">0</span>')
    total_campanas.short_description = "📢 Campañas"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('plantilla-dashboard/', self.admin_site.admin_view(self.plantilla_dashboard_view), name='plantilla_dashboard'),
        ]
        return custom_urls + urls

    def plantilla_dashboard_view(self, request):
        """Vista del dashboard de plantillas"""
        plantillas = Plantilla.objects.all().order_by('categoria', 'nombre_interno')

        # Agrupar por categoría
        categorias = {}
        for plantilla in plantillas:
            cat = plantilla.get_categoria_display()
            if cat not in categorias:
                categorias[cat] = []
            categorias[cat].append(plantilla)

        # Estadísticas
        stats = {
            'total': plantillas.count(),
            'twilio_configuradas': plantillas.filter(twilio_template_sid__isnull=False, aprobada_twilio=True).count(),
            'twilio_pendientes': plantillas.filter(twilio_template_sid__isnull=False, aprobada_twilio=False).count(),
            'directo': plantillas.filter(twilio_template_sid__isnull=True).count(),
        }

        context = {
            'categorias': categorias,
            'stats': stats,
            'title': '📊 Dashboard de Plantillas y Content Templates',
        }

        return render(request, 'admin/plantilla_dashboard.html', context)

    def changelist_view(self, request, extra_context=None):
        """Agregar enlace al dashboard en la lista de plantillas"""
        extra_context = extra_context or {}
        extra_context['dashboard_url'] = 'plantilla-dashboard/'
        return super().changelist_view(request, extra_context)


