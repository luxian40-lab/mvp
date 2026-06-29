from core.admin._common import *  # noqa: F401,F403

# ========== PLANTILLA ==========
@admin.register(Plantilla)
class PlantillaDashboardAdmin(admin.ModelAdmin):
    """Gestión de plantillas de mensajes"""
    list_display = ('nombre_con_emoji', 'categoria_display', 'estado_template', 'activa', 'veces_usada', 'fecha_modificacion')
    list_filter = ('activa', 'categoria', 'aprobada_twilio', 'fecha_modificacion')
    search_fields = ('nombre_interno', 'cuerpo_mensaje', 'twilio_template_sid')
    list_per_page = 50
    actions = ['crear_template_en_twilio', 'sincronizar_templates_twilio']

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
        ('� Twilio (Opcional - Para Casos Avanzados)', {
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
            return format_html('<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    total_plantillas.short_description = "📄 Plantillas"
    
    def total_campanas(self, obj):
        count = obj.campanas.count()
        if count > 0:
            return format_html('<span style="background:#2196f3;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    total_campanas.short_description = "📢 Campañas"
    
    @admin.action(description='🔧 Crear Template en Twilio')
    def crear_template_en_twilio(self, request, queryset):
        """Crea automáticamente un Content Template en Twilio para las plantillas seleccionadas"""
        from core.enviar_plantillas import crear_template_twilio
        
        creados = 0
        errores = []
        
        for plantilla in queryset:
            # Verificar que no tenga ya un template
            if plantilla.twilio_template_sid:
                errores.append(f"{plantilla.nombre_interno}: Ya tiene un template configurado")
                continue
            
            # Crear template en Twilio
            # Convertir {nombre} a {{1}} para Twilio
            contenido_twilio = plantilla.cuerpo_mensaje.replace('{nombre}', '{{1}}')
            
            resultado = crear_template_twilio(
                nombre=f"eki_{plantilla.nombre_interno.lower().replace(' ', '_')}",
                contenido=contenido_twilio,
                variables=['nombre']
            )
            
            if resultado['success']:
                # Guardar el Content SID en la plantilla
                plantilla.twilio_template_sid = resultado['content_sid']
                plantilla.twilio_template_nombre = f"eki_{plantilla.nombre_interno.lower().replace(' ', '_')}"
                plantilla.save()
                creados += 1
                logger.info(f"✅ Template creado para {plantilla.nombre_interno}: {resultado['content_sid']}")
            else:
                errores.append(f"{plantilla.nombre_interno}: {resultado['response']}")
        
        # Mensajes al usuario
        if creados > 0:
            self.message_user(
                request,
                f"✅ {creados} template(s) creado(s) en Twilio. "
                f"IMPORTANTE: Debes ir a Twilio Console para aprobar los templates antes de usarlos.",
                level=messages.SUCCESS
            )
        
        if errores:
            self.message_user(
                request,
                f"⚠️ Errores: {', '.join(errores)}",
                level=messages.WARNING
            )
    
    @admin.action(description='🔄 Sincronizar con Twilio')
    def sincronizar_templates_twilio(self, request, queryset):
        """Obtiene la lista de templates de Twilio y actualiza el estado de aprobación"""
        from core.enviar_plantillas import listar_templates_twilio
        
        # Obtener templates de Twilio
        templates_twilio = listar_templates_twilio()
        
        if not templates_twilio:
            self.message_user(
                request,
                "⚠️ No se pudieron obtener los templates de Twilio. Verifica las credenciales.",
                level=messages.WARNING
            )
            return
        
        # Crear diccionario de SIDs para búsqueda rápida
        sids_twilio = {t['sid']: t for t in templates_twilio}
        
        actualizados = 0
        for plantilla in queryset:
            if plantilla.twilio_template_sid and plantilla.twilio_template_sid in sids_twilio:
                # Template existe en Twilio - marcarlo como aprobado
                if not plantilla.aprobada_twilio:
                    plantilla.aprobada_twilio = True
                    plantilla.save()
                    actualizados += 1
                    logger.info(f"✅ Template aprobado: {plantilla.nombre_interno}")
        
        self.message_user(
            request,
            f"🔄 Sincronización completa. {actualizados} template(s) marcado(s) como aprobado(s). "
            f"Total templates en Twilio: {len(templates_twilio)}",
            level=messages.SUCCESS
        )


