from core.admin._common import *  # noqa: F401,F403
from core.admin.estudiantes import EnvioProgramadoForm

# ========================================
# 👥 ADMIN UNIFICADO DE GRUPOS (TODO EN UNO)
# ========================================

@admin.register(GrupoEstudiantes)
class GrupoEstudiantesAdmin(admin.ModelAdmin):
    """
    📦 GESTIÓN UNIFICADA DE GRUPOS
    Los miembros se gestionan en «Gestionar miembros» (lista/Excel), no con el selector doble.
    """
    list_display = (
        'nombre_completo', 'cliente_nombre', 'cantidad_estudiantes',
        'gestionar_miembros_link', 'cursos_asociados_display',
        'whatsapp_grupos_link', 'invitaciones_link', 'fecha_creacion',
    )
    list_filter = ('cliente', 'activo', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion', 'cliente__nombre')
    filter_horizontal = ('cursos',)
    exclude = ('estudiantes',)
    readonly_fields = ('panel_gestion_miembros',)
    autocomplete_fields = ('cliente',)
    actions = ['crear_grupo_whatsapp', 'enviar_invitaciones']

    fieldsets = (
        ('📋 Información del Grupo', {
            'fields': ('nombre', 'emoji', 'descripcion', 'cliente', 'activo'),
        }),
        ('👥 Miembros del grupo', {
            'fields': ('panel_gestion_miembros',),
            'description': (
                'Use «Gestionar miembros» para pegar cédulas/teléfonos o subir Excel. '
                'Para muchos estudiantes: lista Estudiantes → marcar → acción «Asignar a un grupo».'
            ),
        }),
        ('📚 Cursos asociados (opcional)', {
            'fields': ('cursos',),
            'classes': ('collapse',),
        }),
    )

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/gestionar-miembros/',
                self.admin_site.admin_view(self.gestionar_miembros_view),
                name='core_grupoestudiantes_gestionar_miembros',
            ),
        ]
        return custom + urls

    def gestionar_miembros_view(self, request, object_id):
        from django.contrib import messages
        from django.shortcuts import get_object_or_404, render

        from core.grupos_miembros import (
            agregar_miembros_por_identificadores,
            leer_identificadores_desde_excel,
            parsear_lineas_identificadores,
            quitar_miembros_por_identificadores,
        )

        grupo = get_object_or_404(GrupoEstudiantes, pk=object_id)

        if request.method == 'POST':
            accion = request.POST.get('accion')
            modo = request.POST.get('modo_busqueda', 'auto')
            ids = parsear_lineas_identificadores(request.POST.get('lista_identificadores', ''))

            archivo = request.FILES.get('archivo_excel')
            if archivo and accion == 'agregar':
                try:
                    ids_excel = leer_identificadores_desde_excel(archivo, columna='cedula')
                    if not ids_excel:
                        ids_excel = leer_identificadores_desde_excel(archivo, columna='telefono')
                    ids = list(dict.fromkeys(ids + ids_excel))
                except Exception as exc:
                    messages.error(request, f'No se pudo leer el Excel: {exc}')

            if not ids:
                messages.warning(request, 'No ingresó cédulas, teléfonos ni archivo válido.')
            elif accion == 'agregar':
                r = agregar_miembros_por_identificadores(grupo, ids, modo=modo)
                messages.success(
                    request,
                    f'Agregados: {r["agregados"]}. Ya estaban: {r["ya_estaban"]}. '
                    f'No encontrados: {len(r["no_encontrados"])}.',
                )
                if r['no_encontrados'][:5]:
                    messages.warning(
                        request,
                        'Ejemplos no encontrados: ' + ', '.join(r['no_encontrados'][:5]),
                    )
            elif accion == 'quitar':
                r = quitar_miembros_por_identificadores(grupo, ids, modo=modo)
                messages.success(
                    request,
                    f'Quitados: {r["quitados"]}. No estaban en el grupo: {len(r["no_en_grupo"])}. '
                    f'No encontrados: {len(r["no_encontrados"])}.',
                )

        total = grupo.estudiantes.count()
        miembros = list(
            grupo.estudiantes.order_by('nombre').values('cedula', 'nombre', 'telefono')[:50]
        )
        ctx = {
            'title': f'Gestionar miembros — {grupo.emoji} {grupo.nombre}',
            'grupo': grupo,
            'total_miembros': total,
            'miembros_muestra': miembros,
            'opts': self.model._meta,
        }
        return render(request, 'admin/grupo_gestionar_miembros.html', ctx)

    def panel_gestion_miembros(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<p style="color:#666;">Guarde el grupo primero; luego podrá agregar miembros.</p>'
            )
        n = obj.estudiantes.count()
        url = reverse('admin:core_grupoestudiantes_gestionar_miembros', args=[obj.pk])
        lista_url = (
            f'{reverse("admin:core_estudiante_changelist")}?grupos__id__exact={obj.pk}'
        )
        return format_html(
            '<p><strong>{}</strong> estudiante(s) en este grupo.</p>'
            '<p><a href="{}" class="button" style="background:#1976d2;color:#fff!important;'
            'padding:8px 16px;border-radius:4px;text-decoration:none;margin-right:8px;">'
            'Gestionar miembros (lista / Excel)</a>'
            '<a href="{}" style="margin-left:4px;">Ver en lista de estudiantes</a></p>'
            '<p style="color:#666;font-size:12px;margin-top:12px;">'
            'También: Admin → Estudiantes → filtrar → marcar → acción «Asignar estudiantes a un grupo».</p>',
            n, url, lista_url,
        )
    panel_gestion_miembros.short_description = 'Miembros'

    def gestionar_miembros_link(self, obj):
        if not obj.pk:
            return '-'
        url = reverse('admin:core_grupoestudiantes_gestionar_miembros', args=[obj.pk])
        return format_html(
            '<a href="{}" style="background:#1976d2;color:#fff;padding:5px 10px;'
            'border-radius:6px;text-decoration:none;font-size:11px;">Gestionar</a>',
            url,
        )
    gestionar_miembros_link.short_description = 'Miembros'

    def nombre_completo(self, obj):
        """Muestra el nombre con emoji"""
        return format_html(
            '<span style="font-size:14px;">{} <strong>{}</strong></span>',
            obj.emoji, obj.nombre
        )
    nombre_completo.short_description = "Grupo"
    
    def cliente_nombre(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return format_html('<span style="color:#999;">Sin cliente</span>')
    cliente_nombre.short_description = "🏢 Cliente"
    
    def cantidad_estudiantes(self, obj):
        count = obj.estudiantes.count()
        return format_html(
            '<span style="background:#e3f2fd;padding:4px 10px;border-radius:12px;font-size:11px;">{} estudiante{}</span>',
            count, 's' if count != 1 else ''
        )
    cantidad_estudiantes.short_description = "👥 Estudiantes"
    
    def cursos_asociados_display(self, obj):
        cursos = obj.cursos.all()
        if not cursos:
            return format_html('<span style="color:#999;">Sin cursos</span>')
        
        badges = []
        for curso in cursos[:2]:
            badges.append(f'<span style="background:#fff3e0;color:#e65100;padding:3px 8px;border-radius:8px;font-size:10px;margin-right:3px;">{curso.nombre}</span>')
        
        html = ''.join(badges)
        if cursos.count() > 2:
            html += f' <span style="color:#999;font-size:10px;">+{cursos.count() - 2} más</span>'
        
        return format_html(html)
    cursos_asociados_display.short_description = "📚 Cursos"
    
    def whatsapp_grupos_link(self, obj):
        """Link directo para gestionar grupos de WhatsApp"""
        cursos_ids = obj.cursos.values_list('id', flat=True)
        count = GrupoWhatsApp.objects.filter(curso_id__in=cursos_ids).count()
        
        return format_html(
            '<a href="/admin/core/grupowhatsapp/?curso__id__in={}" style="background:#25d366;color:white;padding:6px 12px;border-radius:12px;text-decoration:none;font-size:11px;font-weight:600;">💬 {} WhatsApp</a>',
            ','.join(map(str, cursos_ids)) if cursos_ids else '0',
            count
        )
    whatsapp_grupos_link.short_description = "Grupos WhatsApp"
    
    def invitaciones_link(self, obj):
        """Link directo para gestionar invitaciones"""
        estudiantes_ids = obj.estudiantes.values_list('id', flat=True)
        count = InvitacionGrupo.objects.filter(estudiante_id__in=estudiantes_ids).count()
        
        return format_html(
            '<a href="/admin/core/invitaciongrupo/?estudiante__id__in={}" style="background:#2196f3;color:white;padding:6px 12px;border-radius:12px;text-decoration:none;font-size:11px;font-weight:600;">✉️ {} Invitaciones</a>',
            ','.join(map(str, estudiantes_ids)) if estudiantes_ids else '0',
            count
        )
    invitaciones_link.short_description = "Invitaciones"
    
    def crear_grupo_whatsapp(self, request, queryset):
        """Acción rápida: Crear grupo de WhatsApp"""
        from django.shortcuts import redirect
        if queryset.count() == 1:
            grupo = queryset.first()
            # Redirigir a crear grupo WhatsApp con el curso preseleccionado
            return redirect(f'/admin/core/grupowhatsapp/add/')
        else:
            self.message_user(request, "Selecciona solo un grupo para crear el grupo de WhatsApp", level='warning')
    crear_grupo_whatsapp.short_description = "➕ Crear grupo de WhatsApp para este grupo"
    
    def enviar_invitaciones(self, request, queryset):
        """Acción rápida: Enviar invitaciones"""
        from django.shortcuts import redirect
        return redirect('/admin/core/invitaciongrupo/add/')
    enviar_invitaciones.short_description = "✉️ Enviar invitaciones a estudiantes"
    enviar_invitaciones.short_description = "✉️ Enviar invitaciones a estudiantes"


@admin.register(EnvioProgramado)
class EnvioProgramadoAdmin(admin.ModelAdmin):
    """Gestión de envíos programados"""
    form = EnvioProgramadoForm
    list_display = ('nombre', 'tipo', 'fecha_programada', 'estado_badge', 'fecha_envio_real')
    list_filter = ('estado', 'tipo', 'fecha_programada')
    search_fields = ('nombre', 'mensaje')
    readonly_fields = ('fecha_envio_real', 'total_destinatarios', 'total_enviados', 'total_fallidos')
    
    fieldsets = (
        ('📋 Información Básica', {
            'fields': ('nombre', 'tipo', 'campana', 'grupo', 'estudiante', 'mensaje')
        }),
        ('📎 Multimedia (Opcional)', {
            'fields': ('incluir_media', 'media_url', 'media_file_upload'),
            'classes': ('collapse',)
        }),
        ('📅 Programación', {
            'fields': ('fecha_programada', 'estado')
        }),
        ('📊 Resultados', {
            'fields': ('fecha_envio_real', 'total_destinatarios', 'total_enviados', 'total_fallidos'),
            'classes': ('collapse',)
        }),
    )
    
    def estado_badge(self, obj):
        colores = {
            'pendiente': ('#fff3e0', '#e65100'),
            'enviando': ('#e3f2fd', '#1976d2'),
            'enviado': ('#e8f5e9', '#2e7d32'),
            'fallido': ('#ffebee', '#c62828'),
            'cancelado': ('#f5f5f5', '#666'),
        }
        bg, color = colores.get(obj.estado, ('#f5f5f5', '#666'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;">{}</span>',
            bg, color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"


class PQRSAdmin(admin.ModelAdmin):
    """Gestión auxiliar de PQRS (Ver principalmente desde Solicitudes de Soporte)"""
    change_list_template = 'admin/core/pqrs/change_list.html'
    list_display = ('tipo_badge', 'estudiante', 'asunto', 'prioridad_badge', 'estado_badge', 'soporte_link', 'fecha_creacion')
    list_filter = ('tipo', 'estado', 'prioridad', 'fecha_creacion')
    search_fields = ('asunto', 'descripcion', 'estudiante__nombre')
    readonly_fields = ('fecha_creacion', 'fecha_respuesta', 'fecha_cierre')
    actions = ['crear_solicitud_soporte']
    
    fieldsets = (
        ('📝 Información', {
            'fields': ('tipo', 'estudiante', 'asunto', 'descripcion', 'curso_relacionado', 'prioridad')
        }),
        ('📊 Estado y Respuesta', {
            'fields': ('estado', 'respuesta', 'notas_internas', 'atendido_por')
        }),
        ('📅 Fechas', {
            'fields': ('fecha_creacion', 'fecha_respuesta', 'fecha_cierre'),
            'classes': ('collapse',)
        }),
        ('⭐ Calificación', {
            'fields': ('calificacion', 'comentario_calificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def tipo_badge(self, obj):
        colores = {
            'peticion': ('#e3f2fd', '#1976d2'),
            'queja': ('#fff3e0', '#e65100'),
            'reclamo': ('#ffebee', '#c62828'),
            'sugerencia': ('#f3e5f5', '#7b1fa2'),
            'felicitacion': ('#e8f5e9', '#2e7d32'),
        }
        bg, color = colores.get(obj.tipo, ('#f5f5f5', '#666'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;">{}</span>',
            bg, color, obj.get_tipo_display()
        )
    tipo_badge.short_description = "Tipo"
    
    def prioridad_badge(self, obj):
        colores = {
            'baja': ('#f5f5f5', '#666'),
            'media': ('#fff3e0', '#e65100'),
            'alta': ('#ffebee', '#c62828'),
            'urgente': ('#b71c1c', '#ffffff'),
        }
        bg, color = colores.get(obj.prioridad, ('#f5f5f5', '#666'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;">{}</span>',
            bg, color, obj.get_prioridad_display()
        )
    prioridad_badge.short_description = "Prioridad"
    
    def estado_badge(self, obj):
        colores = {
            'pendiente': ('#fff3e0', '#e65100'),
            'en_proceso': ('#e3f2fd', '#1976d2'),
            'resuelto': ('#e8f5e9', '#2e7d32'),
            'cerrado': ('#f5f5f5', '#666'),
            'rechazado': ('#ffebee', '#c62828'),
        }
        bg, color = colores.get(obj.estado, ('#f5f5f5', '#666'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;">{}</span>',
            bg, color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"
    
    def soporte_link(self, obj):
        """Link para ver solicitudes de soporte del estudiante"""
        count = SolicitudSoporte.objects.filter(estudiante=obj.estudiante).count()
        
        return format_html(
            '<a href="/admin/core/solicitudsoporte/?estudiante__id__exact={}" style="background:#f44336;color:white;padding:6px 12px;border-radius:12px;text-decoration:none;font-size:11px;font-weight:600;">🆘 {} Soporte</a>',
            obj.estudiante.id,
            count
        )
    soporte_link.short_description = "Solicitudes"
    
    def crear_solicitud_soporte(self, request, queryset):
        """Crear solicitud de soporte desde PQRS urgente"""
        from django.shortcuts import redirect
        if queryset.count() == 1:
            pqrs = queryset.first()
            # Redirigir para crear solicitud de soporte
            return redirect(f'/admin/core/solicitudsoporte/add/?estudiante={pqrs.estudiante.id}')
        else:
            self.message_user(request, "Selecciona solo una PQRS para crear solicitud", level='warning')
    crear_solicitud_soporte.short_description = "🆘 Crear solicitud de soporte urgente"

    def changelist_view(self, request, extra_context=None):
        """Agrega link de vuelta al panel unificado de Soporte y PQRS"""
        extra_context = extra_context or {}
        extra_context['title'] = '📮 PQRS — Parte del panel Soporte y PQRS'
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(ArchivoModulo)
class ArchivoModuloAdmin(admin.ModelAdmin):
    """Gestión de archivos multimedia de módulos"""
    list_display = ('modulo', 'tipo_badge', 'titulo', 'disponible_offline', 'descargar_btn', 'activo')
    list_filter = ('tipo', 'disponible_offline', 'activo', 'modulo__curso')
    search_fields = ('titulo', 'descripcion', 'modulo__titulo')
    readonly_fields = ('preview_archivo', 'fecha_creacion')
    
    fieldsets = (
        ('📁 Información del Archivo', {
            'fields': ('modulo', 'tipo', 'titulo', 'descripcion', 'orden')
        }),
        ('📎 Archivo', {
            'fields': ('archivo', 'preview_archivo', 'url_externa')
        }),
        ('⚙️ Configuración', {
            'fields': ('disponible_offline', 'activo', 'fecha_creacion')
        }),
    )
    
    actions = ['enviar_video_whatsapp_action', 'marcar_disponible_offline', 'marcar_no_disponible_offline']

    @admin.action(description='📤 Enviar video por WhatsApp')
    def enviar_video_whatsapp_action(self, request, queryset):
        from core.whatsapp_service import enviar_video_whatsapp
        from django.contrib import messages
        enviados = 0
        errores = 0
        for archivo in queryset:
            if archivo.tipo == 'video' and archivo.url_externa:
                # Solicitar número destino
                numero = request.POST.get('numero_destino')
                if not numero:
                    self.message_user(request, 'Debes ingresar el número destino en formato internacional (+57...).', level='error')
                    errores += 1
                    continue
                try:
                    enviar_video_whatsapp(numero, archivo.url_externa)
                    enviados += 1
                except Exception as e:
                    self.message_user(request, f'Error enviando video: {e}', level='error')
                    errores += 1
            else:
                self.message_user(request, 'Solo se pueden enviar archivos de tipo video con URL externa.', level='error')
                errores += 1
        if enviados:
            self.message_user(request, f'{enviados} video(s) enviados correctamente por WhatsApp.')
        if errores:
            self.message_user(request, f'{errores} error(es) al intentar enviar videos.', level='error')
    
    def tipo_badge(self, obj):
        colores = {
            'video': ('#f3e5f5', '#7b1fa2'),
            'imagen': ('#e3f2fd', '#1976d2'),
            'infografia': ('#e8f5e9', '#2e7d32'),
            'pdf': ('#ffebee', '#c62828'),
            'audio': ('#fff3e0', '#e65100'),
        }
        bg, color = colores.get(obj.tipo, ('#f5f5f5', '#666'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;">{}</span>',
            bg, color, obj.get_tipo_display()
        )
    tipo_badge.short_description = "Tipo"
    
    def tamanio_display(self, obj):
        if obj.tamano_bytes:
            mb = obj.tamano_bytes / (1024 * 1024)
            return f"{mb:.2f} MB"
        return "N/A"
    tamanio_display.short_description = "Tamaño"
    
    def preview_archivo(self, obj):
        url = obj.get_url_para_envio()
        if not url:
            return format_html('<span style="color:#999;">Sin archivo</span>')
        if obj.tipo == 'imagen':
            return format_html(
                '<img src="{}" style="max-width:400px;max-height:300px;border-radius:8px;border:2px solid #ddd;" />',
                url
            )
        elif obj.tipo == 'video':
            return format_html(
                '<video controls style="max-width:500px;border-radius:8px;"><source src="{}" type="video/mp4"></video>',
                url
            )
        elif obj.tipo == 'pdf':
            return format_html(
                '<a href="{}" target="_blank" class="button" style="background:#dc2626;color:white;padding:10px 20px;text-decoration:none;border-radius:6px;">📄 Abrir PDF</a>',
                url
            )
        else:
            return format_html(
                '<a href="{}" target="_blank">Ver archivo</a>',
                url
            )
    preview_archivo.short_description = "Vista Previa"
    
    def descargar_btn(self, obj):
        if obj.archivo:
            return format_html(
                '<a href="{}" download class="button" style="background:#2563eb;color:white;padding:6px 14px;text-decoration:none;border-radius:6px;font-size:12px;">⬇️ Descargar</a>',
                obj.archivo.url
            )
        return '-'
    descargar_btn.short_description = "Descarga"
    
    def marcar_disponible_offline(self, request, queryset):
        updated = queryset.update(disponible_offline=True)
        self.message_user(request, f'{updated} archivo(s) marcado(s) como disponibles offline')
    marcar_disponible_offline.short_description = "✅ Marcar disponible offline"
    
    def marcar_no_disponible_offline(self, request, queryset):
        updated = queryset.update(disponible_offline=False)
        self.message_user(request, f'{updated} archivo(s) marcado(s) como NO disponibles offline')
    marcar_no_disponible_offline.short_description = "❌ Desactivar descarga offline"


# ⚠️ MODELOS AUXILIARES - NO APARECEN EN EL MENÚ PRINCIPAL
# Estos modelos se gestionan desde "Grupos de Estudiantes"
# Pero los registramos para que estén disponibles via acciones/links

@admin.register(GrupoWhatsApp)
class GrupoWhatsAppAdmin(admin.ModelAdmin):
    """Gestión auxiliar de grupos de WhatsApp (acceso desde Grupos de Estudiantes)"""
    list_display = ('nombre', 'curso', 'link_invitacion_corto', 'ocupacion_badge', 'activo', 'fecha_creacion')
    list_filter = ('activo', 'curso', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    
    def link_invitacion_corto(self, obj):
        if obj.link_invitacion:
            return format_html(
                '<a href="{}" target="_blank" style="color:#25d366;">🔗 Abrir</a>',
                obj.link_invitacion
            )
        return '-'
    link_invitacion_corto.short_description = "Link"
    
    def ocupacion_badge(self, obj):
        porcentaje = obj.porcentaje_ocupacion()
        color = '#4caf50' if porcentaje < 70 else '#ff9800' if porcentaje < 90 else '#f44336'
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:12px;font-size:11px;">{}/{} ({}%)</span>',
            color, obj.miembros_actuales, obj.capacidad_maxima, porcentaje
        )
    ocupacion_badge.short_description = "Ocupación"
    
    class Meta:
        verbose_name = 'Grupo de WhatsApp'
        verbose_name_plural = 'Grupos de WhatsApp (Ver desde Grupos)'

@admin.register(InvitacionGrupo)
class InvitacionGrupoAdmin(admin.ModelAdmin):
    """Gestión auxiliar de invitaciones (acceso desde Grupos de Estudiantes)"""
    list_display = ('estudiante', 'grupo', 'estado_badge', 'fecha_envio', 'fecha_respuesta')
    list_filter = ('estado', 'fecha_envio', 'grupo')
    search_fields = ('estudiante__nombre', 'grupo__nombre')
    readonly_fields = ('fecha_envio', 'fecha_respuesta', 'fecha_creacion')
    
    def estado_badge(self, obj):
        colores = {
            'pendiente': ('#fff3e0', '#e65100'),
            'enviada': ('#e3f2fd', '#1976d2'),
            'aceptada': ('#e8f5e9', '#2e7d32'),
            'rechazada': ('#ffebee', '#c62828'),
            'expirada': ('#f5f5f5', '#666'),
        }
        return format_html(
            '<span style="background:{};color:white;padding:6px 12px;border-radius:12px;font-weight:600;">{}</span>',
            colores.get(obj.estado, '#999'),
            obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"
    
    class Meta:
        verbose_name = 'Invitación a Grupo'
        verbose_name_plural = 'Invitaciones (Ver desde Grupos)'
    
    def estado_badge(self, obj):
        colores = {
            'pendiente': ('#fff3e0', '#e65100'),
            'enviada': ('#e3f2fd', '#1976d2'),
            'aceptada': ('#e8f5e9', '#2e7d32'),
            'rechazada': ('#ffebee', '#c62828'),
            'expirada': ('#f5f5f5', '#666'),
        }
        bg, color = colores.get(obj.estado, ('#f5f5f5', '#666'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;">{}</span>',
            bg, color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"


