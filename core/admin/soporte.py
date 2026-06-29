from core.admin._common import *  # noqa: F401,F403

# ========================================
# 🆘 ADMIN UNIFICADO DE SOPORTE (TODO EN UNO)
# ========================================

@admin.register(SolicitudSoporte)
class SolicitudSoporteAdmin(admin.ModelAdmin):
    """
    🆘 GESTIÓN UNIFICADA DE SOPORTE Y PQRS
    Todo en un solo lugar: soporte técnico + peticiones, quejas, reclamos, sugerencias
    """
    change_list_template = 'admin/core/solicitudsoporte/change_list.html'
    change_form_template = 'admin/core/solicitudsoporte/change_form.html'
    list_display = ('tipo_badge', 'estudiante_info', 'asunto_o_keyword', 'categoria_badge', 'estado_badge', 'prioridad_badge', 'fecha_solicitud', 'tiempo_espera', 'atendido_por_info')
    list_filter = ('tipo_solicitud', 'categoria', 'resuelto_por_agente', 'estado', 'prioridad', 'keyword_usada', 'fecha_solicitud')
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'mensaje_original', 'asunto', 'respuesta')
    readonly_fields = (
        'fecha_solicitud', 'categoria', 'resuelto_por_agente', 'notas_internas',
        'fecha_respuesta', 'respondido_por',
    )
    list_per_page = 50
    ordering = ('-fecha_solicitud',)
    actions = ['marcar_en_atencion', 'marcar_resuelta', 'marcar_prioridad_alta']
    
    fieldsets = (
        ('📋 Tipo y Clasificación', {
            'fields': ('tipo_solicitud', 'asunto', 'curso_relacionado', 'prioridad')
        }),
        ('📞 Información del Estudiante', {
            'fields': ('estudiante', 'keyword_usada', 'fecha_solicitud')
        }),
        ('💬 Mensaje Original', {
            'fields': ('mensaje_original',)
        }),
        ('🎯 Gestión', {
            'fields': ('estado', 'atendido_por', 'categoria', 'resuelto_por_agente'),
            'description': 'Categoría y resuelto_por_agente los completa el agente PQRS automático.',
        }),
        ('Respuesta', {
            'fields': ('respuesta', 'respuesta_portal', 'fecha_atencion', 'fecha_resolucion', 'fecha_respuesta', 'respondido_por'),
            'description': 'Registro interno. Para notificar al estudiante, use el formulario al final de la página.',
        }),
        ('📋 Notas Internas', {
            'fields': ('notas_internas',),
            'classes': ('collapse',),
            'description': 'Estas notas son privadas y no se muestran al estudiante'
        }),
        ('⭐ Calificación del Estudiante', {
            'fields': ('calificacion', 'comentario_calificacion'),
            'classes': ('collapse',),
        }),
    )
    
    def tipo_badge(self, obj):
        colores = {
            'soporte': ('#f44336', '#ffffff'),
            'peticion': ('#e3f2fd', '#1976d2'),
            'queja': ('#fff3e0', '#e65100'),
            'reclamo': ('#ffebee', '#c62828'),
            'sugerencia': ('#f3e5f5', '#7b1fa2'),
            'felicitacion': ('#e8f5e9', '#2e7d32'),
        }
        iconos = {
            'soporte': '🆘', 'peticion': '📋', 'queja': '😤',
            'reclamo': '📢', 'sugerencia': '💡', 'felicitacion': '🌟',
        }
        bg, color = colores.get(obj.tipo_solicitud, ('#f5f5f5', '#666'))
        icono = iconos.get(obj.tipo_solicitud, '')
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;font-weight:600;">'
            '{} {}'
            '</span>',
            bg, color, icono, obj.get_tipo_solicitud_display()
        )
    tipo_badge.short_description = "Tipo"
    
    def asunto_o_keyword(self, obj):
        """Muestra asunto si es PQRS o keyword si es soporte"""
        if obj.asunto:
            return obj.asunto[:50]
        if obj.keyword_usada:
            return format_html(
                '<span style="background:#e3f2fd;color:#1565c0;padding:4px 10px;border-radius:12px;font-size:11px;">'
                '🔑 {}'
                '</span>',
                obj.keyword_usada.upper()
            )
        return format_html('<span style="color:#999;">-</span>')
    asunto_o_keyword.short_description = "Asunto / Keyword"
    
    def estudiante_info(self, obj):
        return format_html(
            '<strong>{}</strong><br>'
            '<small style="color:#666;">📱 +{}</small>',
            obj.estudiante.nombre,
            obj.estudiante.telefono
        )
    estudiante_info.short_description = "Estudiante"
    
    def categoria_badge(self, obj):
        if not obj.categoria:
            return format_html('<span style="color:#bbb;">—</span>')
        colores = {
            'acceso': ('#fff8e1', '#f9a825'),
            'contenido': ('#e3f2fd', '#1565c0'),
            'tecnico': ('#fbe9e7', '#bf360c'),
            'otro': ('#f5f5f5', '#666'),
        }
        bg, color = colores.get(obj.categoria, ('#f5f5f5', '#666'))
        marca = '🤖✓' if obj.resuelto_por_agente else '🆘'
        return format_html(
            '<span title="{}" style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;font-weight:600;">{} {}</span>',
            'Resuelto por agente IA' if obj.resuelto_por_agente else 'Escalado',
            bg, color, marca, obj.get_categoria_display(),
        )
    categoria_badge.short_description = 'Categoría PQRS'

    def estado_badge(self, obj):
        colores = {
            'pendiente': '#ff9800',
            'en_atencion': '#2196f3',
            'resuelta': '#4caf50',
            'cerrada': '#999'
        }
        iconos = {
            'pendiente': '⏳',
            'en_atencion': '👀',
            'resuelta': '✅',
            'cerrada': '🔒'
        }
        return format_html(
            '<span style="background:{};color:white;padding:6px 12px;border-radius:12px;font-weight:600;">'
            '{} {}'
            '</span>',
            colores.get(obj.estado, '#999'),
            iconos.get(obj.estado, ''),
            obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"
    
    def prioridad_badge(self, obj):
        colores = {
            'baja': '#4caf50',
            'media': '#ff9800',
            'alta': '#f44336',
            'critica': '#d32f2f'
        }
        return format_html(
            '<span style="background:{};color:white;padding:6px 12px;border-radius:12px;font-weight:600;">'
            '{}'
            '</span>',
            colores.get(obj.prioridad, '#999'),
            obj.get_prioridad_display()
        )
    prioridad_badge.short_description = "Prioridad"
    
    def tiempo_espera(self, obj):
        """Muestra cuánto tiempo lleva esperando si no ha sido resuelta"""
        if obj.estado in ['resuelta', 'cerrada']:
            return format_html('<span style="color:#4caf50;">✅ Resuelta</span>')
        
        from django.utils import timezone
        tiempo = timezone.now() - obj.fecha_solicitud
        horas = int(tiempo.total_seconds() / 3600)
        
        if horas < 1:
            minutos = int(tiempo.total_seconds() / 60)
            color = '#4caf50'
            texto = f'{minutos} min'
        elif horas < 24:
            color = '#ff9800' if horas > 4 else '#4caf50'
            texto = f'{horas} horas'
        else:
            dias = int(horas / 24)
            color = '#f44336'
            texto = f'{dias} días'
        
        return format_html(
            '<span style="color:{};">⏰ {}</span>',
            color, texto
        )
    tiempo_espera.short_description = "⏰ Tiempo"
    
    def atendido_por_info(self, obj):
        if obj.atendido_por:
            return format_html(
                '<span style="background:#e8f5e9;color:#2e7d32;padding:4px 10px;border-radius:12px;font-size:11px;">'
                '👤 {}'
                '</span>',
                obj.atendido_por
            )
        return format_html('<span style="color:#999;">Sin asignar</span>')
    atendido_por_info.short_description = "Atendido por"
    
    @admin.action(description='👀 Marcar como "En Atención"')
    def marcar_en_atencion(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            estado='en_atencion',
            fecha_atencion=timezone.now()
        )
        self.message_user(request, f"✅ {queryset.count()} solicitud(es) marcada(s) como 'En Atención'")
    
    @admin.action(description='✅ Marcar como "Resuelta"')
    def marcar_resuelta(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            estado='resuelta',
            fecha_resolucion=timezone.now()
        )
        self.message_user(request, f"✅ {queryset.count()} solicitud(es) marcada(s) como 'Resuelta'")
    
    @admin.action(description='🚨 Marcar como "Prioridad Alta"')
    def marcar_prioridad_alta(self, request, queryset):
        queryset.update(prioridad='alta')
        self.message_user(request, f"🚨 {queryset.count()} solicitud(es) marcada(s) como 'Prioridad Alta'")

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        err = request.session.pop('pqrs_envio_error', None)
        if err:
            extra_context['envio_error'] = err
        if request.session.pop('pqrs_envio_ok', False):
            extra_context['envio_ok'] = True

        if request.method == 'POST' and '_enviar_whatsapp' in request.POST and object_id:
            from core.pqrs_respuesta import aplicar_respuesta_pqrs

            obj = self.get_object(request, object_id)
            texto = (
                request.POST.get('respuesta_whatsapp_admin', '').strip()
                or request.POST.get('respuesta', '').strip()
            )
            ok, error = aplicar_respuesta_pqrs(obj, texto, request.user)
            if ok:
                self.message_user(
                    request,
                    f'Respuesta enviada por WhatsApp a {obj.estudiante.nombre}.',
                    messages.SUCCESS,
                )
                request.session['pqrs_envio_ok'] = True
                return redirect(reverse('admin:core_solicitudsoporte_change', args=[obj.pk]))
            request.session['pqrs_envio_error'] = error
            return redirect(reverse('admin:core_solicitudsoporte_change', args=[obj.pk]))

        return super().changeform_view(request, object_id, form_url, extra_context)

    def changelist_view(self, request, extra_context=None):
        """Vista unificada de Soporte y PQRS con estadísticas"""
        extra_context = extra_context or {}
        
        # Estadísticas unificadas
        total = SolicitudSoporte.objects.count()
        pendientes = SolicitudSoporte.objects.filter(estado='pendiente').count()
        en_atencion = SolicitudSoporte.objects.filter(estado='en_atencion').count()
        resueltas = SolicitudSoporte.objects.filter(estado='resuelta').count()
        
        # Por tipo
        soporte_count = SolicitudSoporte.objects.filter(tipo_solicitud='soporte').count()
        pqrs_count = SolicitudSoporte.objects.exclude(tipo_solicitud='soporte').count()
        
        extra_context.update({
            'pqrs_panel_html': format_html('''
                <div style="background:linear-gradient(135deg,#f5f5f5,#e8eaf6);padding:20px;border-radius:12px;margin-bottom:20px;border:1px solid #c5cae9;">
                    <h3 style="margin:0 0 15px 0;color:#283593;">🆘 Panel Unificado: Soporte y PQRS</h3>
                    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px;">
                        <div style="background:#fff;padding:12px 20px;border-radius:8px;border-left:4px solid #ff9800;flex:1;min-width:120px;">
                            <div style="font-size:24px;font-weight:bold;color:#ff9800;">{}</div>
                            <div style="color:#666;font-size:12px;">Pendientes</div>
                        </div>
                        <div style="background:#fff;padding:12px 20px;border-radius:8px;border-left:4px solid #2196f3;flex:1;min-width:120px;">
                            <div style="font-size:24px;font-weight:bold;color:#2196f3;">{}</div>
                            <div style="color:#666;font-size:12px;">En Atención</div>
                        </div>
                        <div style="background:#fff;padding:12px 20px;border-radius:8px;border-left:4px solid #4caf50;flex:1;min-width:120px;">
                            <div style="font-size:24px;font-weight:bold;color:#4caf50;">{}</div>
                            <div style="color:#666;font-size:12px;">Resueltas</div>
                        </div>
                        <div style="background:#fff;padding:12px 20px;border-radius:8px;border-left:4px solid #f44336;flex:1;min-width:120px;">
                            <div style="font-size:24px;font-weight:bold;color:#f44336;">{}</div>
                            <div style="color:#666;font-size:12px;">Soporte Técnico</div>
                        </div>
                        <div style="background:#fff;padding:12px 20px;border-radius:8px;border-left:4px solid #7b1fa2;flex:1;min-width:120px;">
                            <div style="font-size:24px;font-weight:bold;color:#7b1fa2;">{}</div>
                            <div style="color:#666;font-size:12px;">PQRS</div>
                        </div>
                    </div>
                    <p style="color:#666;font-size:12px;margin:0;">Usa los filtros de la derecha para filtrar por tipo (Soporte, Petición, Queja, etc.)</p>
                </div>
            ''', pendientes, en_atencion, resueltas, soporte_count, pqrs_count),
        })
        
        return super().changelist_view(request, extra_context=extra_context)


