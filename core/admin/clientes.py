from core.admin._common import *  # noqa: F401,F403

# ========== CLIENTE (NUEVO) ==========
class ConfiguracionDripClienteInline(admin.TabularInline):
    """Override de días entre módulos por curso (misma fila = un curso por cliente)."""
    model = ConfiguracionDripCliente
    extra = 0
    tab = True
    fields = ('curso', 'dias_espera_entre_modulos', 'activo')
    autocomplete_fields = ('curso',)
    verbose_name = 'Drip curso'
    verbose_name_plural = 'Ritmo drip por curso'


class HabilitacionModuloEstudianteInline(admin.TabularInline):
    model = HabilitacionModuloEstudiante
    extra = 1
    tab = True
    fields = ('curso', 'modulo', 'habilitado_desde', 'activo', 'notas')
    autocomplete_fields = ('curso', 'modulo')
    verbose_name = 'Módulo individual'
    verbose_name_plural = 'Módulos habilitados (drip por lista)'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'curso' and request.resolver_match:
            obj_id = request.resolver_match.kwargs.get('object_id')
            if obj_id:
                try:
                    est = Estudiante.objects.only('cliente_id').get(pk=obj_id)
                    kwargs['queryset'] = Curso.objects.filter(cliente_id=est.cliente_id, activo=True)
                except Estudiante.DoesNotExist:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(HabilitacionModuloEstudiante)
class HabilitacionModuloEstudianteAdmin(admin.ModelAdmin):
    """Listado masivo de qué estudiante puede ver qué módulo."""
    list_display = ('estudiante', 'curso', 'modulo', 'habilitado_desde', 'activo', 'notas')
    list_filter = ('activo', 'curso__cliente', 'curso')
    search_fields = (
        'estudiante__nombre', 'estudiante__cedula', 'estudiante__telefono',
        'curso__nombre', 'modulo__nombre',
    )
    autocomplete_fields = ('estudiante', 'curso', 'modulo')
    list_select_related = ('estudiante', 'curso', 'modulo', 'curso__cliente')
    ordering = ('-id',)


class HabilitacionModuloDripClienteInline(admin.TabularInline):
    """Fecha/hora en que un módulo del curso se habilita para este cliente (sustituye la fecha global del módulo)."""
    model = HabilitacionModuloDripCliente
    extra = 0
    tab = True
    fields = ('curso', 'modulo', 'habilitado_desde', 'activo')
    autocomplete_fields = ('curso', 'modulo')
    verbose_name = 'Calendario módulo'
    verbose_name_plural = 'Calendario de módulos'


class ProductoCatalogoInline(admin.TabularInline):
    model = ProductoCatalogo
    extra = 0
    tab = True
    fields = (
        'nombre', 'sku', 'categoria', 'cultivos_objetivo',
        'precio_cop', 'unidad', 'url_producto', 'activo',
    )
    show_change_link = True
    verbose_name_plural = 'Catálogo de productos (Nat)'


class PortalUsuarioInline(admin.TabularInline):
    model = PortalUsuario
    extra = 0
    tab = True
    fields = ('user', 'rol', 'debe_cambiar_credenciales', 'password_temporal', 'portal_user_link')
    readonly_fields = ('password_temporal', 'portal_user_link')
    autocomplete_fields = ('user',)
    verbose_name = 'Usuario del portal'
    verbose_name_plural = 'Usuarios del portal'

    def portal_user_link(self, obj):
        if not obj or not obj.user_id:
            return '-'
        url = reverse('admin:portal_portalusuario_change', args=[obj.pk])
        return format_html('<a href="{}">Ver / resetear</a>', url)
    portal_user_link.short_description = 'Acceso'


# CrearUsuarioPortalForm vive en portal.forms_usuarios (provisión con cupos).


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """Gestión de clientes/organizaciones"""
    change_form_template = 'admin/core/cliente/change_form.html'

    def get_form(self, request, obj=None, **kwargs):
        from portal.forms import ClientePortalAdminForm
        kwargs['form'] = ClientePortalAdminForm
        return super().get_form(request, obj, **kwargs)

    inlines = [
        PortalUsuarioInline,
        ConfiguracionDripClienteInline,
        HabilitacionModuloDripClienteInline,
        ProductoCatalogoInline,
    ]
    # Listado ops: A–Z por nombre; columnas densas fuera (meta/fecha → ficha).
    list_display = (
        'logo_thumb',
        'nombre',
        'activo',
        'estudiantes_activos',
        'cursos_asignados',
        'mapa_cobertura_rapido',
        'contacto_principal',
    )
    list_filter = ('activo',)
    search_fields = ('nombre', 'nit', 'contacto_principal', 'email')
    list_per_page = 50
    ordering = ('nombre',)
    readonly_fields = (
        'portal_usuarios_acciones',
        'cobertura_y_drip_acciones',
        'empleabilidad_kpis_resumen',
        'usar_gamificacion',
        'wallpaper_preview',
    )
    
    fieldsets = (
        ('Datos del cliente', {
            'fields': (
                'nombre',
                'nit',
                'contacto_principal',
                'email',
                'telefono',
                'activo',
                'notas_internas',
            ),
        }),
        ('Aula Aprende — fondo de estudiantes', {
            'fields': (
                'wallpaper_archivo',
                'wallpaper_aula_url',
                'quitar_wallpaper',
                'wallpaper_preview',
            ),
            'description': mark_safe(
                '<p><strong>Cómo poner el fondo de Aprende (ej. Cenipalma)</strong></p>'
                '<ol style="margin:0.35rem 0 0;padding-left:1.25rem;">'
                '<li>En <em>Subir imagen de fondo</em>, elija el JPG/PNG/WebP (máx. 2 MB).</li>'
                '<li>Pulse <strong>Guardar</strong> abajo.</li>'
                '<li>La vista previa aparece aquí; el estudiante lo ve al entrar a '
                '<a href="https://aprende.eki.technology/aprende/estudiante/login/" '
                'target="_blank" rel="noopener">Aprende</a> (sesión logueada).</li>'
                '</ol>'
                '<p style="margin:0.5rem 0 0;">No hace falta pegar URL si sube el archivo. '
                'El fondo es por <strong>organización</strong> (Cliente), no por curso.</p>'
            ),
        }),
        ('Portal B2B', {
            'fields': (
                'tipo_proyecto',
                'portal_modulos',
                'cupos_portal',
                'fecha_inicio_suscripcion',
                'fecha_fin_suscripcion',
                'logo_url',
                'portal_subtitulo',
                'portal_usuarios_acciones',
                'whatsapp_numero',
            ),
            'description': (
                'Acceso web, branding y cupos. Solo eki crea usuarios portal (nunca staff). '
                'Credenciales Twilio van en «WhatsApp y legal» (colapsado).'
            ),
        }),
        ('WhatsApp y legal', {
            'classes': ('collapse',),
            'fields': (
                'numero_whatsapp_autorizado',
                'twilio_account_sid',
                'twilio_auth_token',
                'twilio_whatsapp_from',
                'enlace_habeas_data',
                'content_sid_habeas_data_twilio',
                'modo_avance_modulo',
                'content_sid_boton_listo',
                'enlace_grupo_whatsapp',
            ),
            'description': (
                'Secretos Twilio, número Meta, Habeas y avance «Listo». Solo abrir si vas a configurar canal.'
            ),
        }),
        ('Certificados, drip y gamificación', {
            'classes': ('collapse',),
            'fields': (
                'enviar_certificados_email',
                'exigir_nota_minima_certificado',
                'nota_minima_certificado',
                'drip_modulos_solo_estudiantes_listados',
                'cobertura_y_drip_acciones',
                'modo_gamificacion',
                'usar_gamificacion',
            ),
            'description': (
                'Certificados, drip por lista y modo de puntos. Calendario drip en pestaña al final.'
            ),
        }),
        ('Ventanas por fechas', {
            'classes': ('collapse',),
            'fields': (
                'habilitar_pregunta_abierta_final',
                'fecha_inicio_pregunta_abierta_final',
                'fecha_fin_pregunta_abierta_final',
                'habilitar_gamificacion_proximidad',
                'fecha_inicio_gamificacion_proximidad',
                'fecha_fin_gamificacion_proximidad',
            ),
        }),
        ('Empleabilidad, IA y Nat', {
            'classes': ('collapse',),
            'fields': (
                'empleabilidad_kpis_resumen',
                'empleabilidad_exploracion_activa',
                'empleabilidad_radio_metros',
                'empleabilidad_cooldown_horas',
                'empleabilidad_max_misiones_dia',
                'empleabilidad_puntos_validacion',
                'nombre_agente_tutor',
                'nombre_agente_asistente',
                'nombre_bot',
                'system_prompt_extra',
            ),
            'description': (
                'Exploración territorial, nombres de agentes y prompt Nat. Catálogo en pestaña al final.'
            ),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:cliente_id>/crear-usuario-portal/',
                self.admin_site.admin_view(self.crear_usuario_portal_view),
                name='core_cliente_crear_usuario_portal',
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            from portal.branding import contexto_identidad_org
            extra_context.update(contexto_identidad_org(obj))
            extra_context['eki_org_tipo'] = obj.get_tipo_proyecto_display()
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def logo_thumb(self, obj):
        """Foto/logo de la organización en el listado. Fallback: inicial."""
        url = (getattr(obj, 'logo_url', None) or '').strip() if obj else ''
        inicial = (getattr(obj, 'nombre', '') or '?').strip()[:1].upper()
        if url:
            return format_html(
                '<img class="eki-id-thumb-list" src="{}" alt="" loading="lazy" '
                'referrerpolicy="no-referrer" '
                'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'inline-flex\';">'
                '<span class="eki-id-thumb-list eki-id-thumb-list--ph" style="display:none;">{}</span>',
                url,
                inicial,
            )
        return format_html(
            '<span class="eki-id-thumb-list eki-id-thumb-list--ph">{}</span>',
            inicial,
        )
    logo_thumb.short_description = ''

    def portal_usuarios_acciones(self, obj):
        if not obj or not obj.pk:
            return 'Guarda el cliente para crear usuarios del portal.'

        crear_url = reverse('admin:core_cliente_crear_usuario_portal', args=[obj.pk])
        usuarios_url = (
            reverse('admin:portal_portalusuario_changelist')
            + f'?organizacion__id__exact={obj.pk}'
        )
        portal_url = '/portal/login/'
        from portal.provision import cupos_restantes, cupos_totales, cupos_usados
        usados = cupos_usados(obj)
        total = cupos_totales(obj)
        restan = cupos_restantes(obj)

        return format_html(
            '<div style="margin-bottom:8px;font-weight:600;">Cupos: {} / {} '
            '<span style="color:#666;font-weight:400;">({} disponibles)</span></div>'
            '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
            '<a class="button" href="{}">➕ Crear usuario portal</a>'
            '<a class="button" href="{}">Ver usuarios</a>'
            '<a class="button" href="{}" target="_blank" rel="noopener">Abrir portal</a>'
            '</div>'
            '<p style="margin:8px 0 0;color:#666;">'
            'Solo eki aprovisiona accesos. El usuario nunca es staff/admin Django. '
            'En el primer ingreso cambia nombre y contraseña; la temporal se ve aquí hasta entonces.'
            '</p>',
            usados,
            total,
            restan,
            crear_url,
            usuarios_url,
            portal_url,
        )
    portal_usuarios_acciones.short_description = 'Accesos portal'

    def wallpaper_preview(self, obj):
        url = (getattr(obj, 'wallpaper_aula_url', None) or '').strip() if obj else ''
        if not url:
            return mark_safe(
                '<span style="color:#888;">Sin wallpaper. Suba una imagen arriba y guarde.</span>'
            )
        return format_html(
            '<p style="margin:0 0 8px;"><img src="{}" alt="Wallpaper Aprende" '
            'style="max-width:min(480px,100%);max-height:140px;border-radius:8px;'
            'border:1px solid #ddd;object-fit:cover;background:#f6f4f8;"/></p>'
            '<p style="margin:0;font-size:12px;color:#666;word-break:break-all;">{}</p>',
            url,
            url,
        )
    wallpaper_preview.short_description = 'Vista previa actual'

    def cobertura_y_drip_acciones(self, obj):
        if not obj or not obj.pk:
            return 'Guarde el cliente para ver enlaces.'
        mapa_url = reverse('admin_cobertura_mapa') + f'?cliente={obj.pk}'
        drip_url = reverse('admin_drip_estudiantes') + f'?cliente={obj.pk}'
        avance_url = reverse('admin_ajustar_avance') + f'?cliente={obj.pk}'
        gamif_url = reverse('admin_gamificacion_ajuste') + f'?cliente={obj.pk}'
        cert_url = reverse('admin_certificados_presenciales') + f'?cliente={obj.pk}'
        push_url = reverse('admin_push_estudiantes') + f'?cliente={obj.pk}'
        form_url = reverse('admin:core_enlaceformularioexterno_changelist') + f'?cliente={obj.pk}'
        return format_html(
            '<div style="display:flex;gap:10px;flex-wrap:wrap;">'
            '<a class="button" href="{}">Mapa cobertura</a>'
            '<a class="button" href="{}">Acceso módulos</a>'
            '<a class="button" href="{}">Ajustar avance</a>'
            '<a class="button" href="{}">Gamificación manual</a>'
            '<a class="button" href="{}">Certificados presenciales</a>'
            '<a class="button" href="{}">Push recordatorios</a>'
            '<a class="button" href="{}">Form externo</a>'
            '</div>',
            mapa_url,
            drip_url,
            avance_url,
            gamif_url,
            cert_url,
            push_url,
            form_url,
        )

    cobertura_y_drip_acciones.short_description = 'Mapa y listas'

    @admin.display(description='Cobertura')
    def mapa_cobertura_rapido(self, obj):
        if not obj or not obj.pk:
            return '—'
        url = reverse('admin_cobertura_mapa') + f'?cliente={obj.pk}'
        return format_html(
            '<a href="{}" style="font-weight:600;color:#7A4E8E;">Mapa →</a>',
            url,
        )

    def empleabilidad_kpis_resumen(self, obj):
        if not obj or not obj.pk:
            return 'Guarde el cliente para ver los KPIs de empleabilidad.'

        from portal.capabilities import modulos_portal
        from portal.empleabilidad_metricas import resumen_empleabilidad_portal

        resumen = resumen_empleabilidad_portal(obj)
        mods = modulos_portal(obj)
        misiones_url = (
            reverse('admin:learning_misionempleabilidad_changelist')
            + f'?cliente__id__exact={obj.pk}'
        )
        aliados_url = (
            reverse('admin:learning_aliadoempleabilidad_changelist')
            + f'?cliente__id__exact={obj.pk}'
        )
        portal_url = '/portal/empleabilidad/'

        portal_note = ''
        if not mods.get('empleabilidad'):
            portal_note = (
                '<p style="margin:10px 0 0;color:#b45309;font-size:13px;">'
                'El módulo <strong>Empleabilidad territorial</strong> no está activo en el portal. '
                'Márquelo en «Módulos visibles en portal» (sección Portal B2B).'
                '</p>'
            )

        return format_html(
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));'
            'gap:12px;max-width:760px;">'
            '<div style="background:#eef6ff;border:1px solid #bfdbfe;border-radius:8px;padding:14px;">'
            '<div style="font-size:1.75rem;font-weight:700;color:#1d4ed8;">{}%</div>'
            '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#64748b;">'
            'Retención ({} días)</div>'
            '<div style="font-size:12px;color:#64748b;margin-top:6px;">{} de {} jóvenes activos</div>'
            '</div>'
            '<div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;padding:14px;">'
            '<div style="font-size:1.75rem;font-weight:700;color:#047857;">{}</div>'
            '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#64748b;">'
            'Misiones completadas</div>'
            '<div style="font-size:12px;color:#64748b;margin-top:6px;">Código validado en aliado</div>'
            '</div>'
            '<div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:8px;padding:14px;">'
            '<div style="font-size:1.75rem;font-weight:700;color:#6d28d9;">{}</div>'
            '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#64748b;">'
            'Oportunidades georreferenciadas</div>'
            '<div style="font-size:12px;color:#64748b;margin-top:6px;">Exploraciones con coordenadas</div>'
            '</div>'
            '</div>'
            '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">'
            '<a class="button" href="{}">Ver misiones</a>'
            '<a class="button" href="{}">Ver aliados</a>'
            '<a class="button" href="{}" target="_blank" rel="noopener">Portal empleabilidad</a>'
            '</div>'
            '{}',
            resumen['retencion_pct'],
            resumen['dias_retencion'],
            resumen['jovenes_activos'],
            resumen['total_inscritos'],
            resumen['misiones_completadas'],
            resumen['oportunidades_georef'],
            misiones_url,
            aliados_url,
            portal_url,
            mark_safe(portal_note),
        )

    empleabilidad_kpis_resumen.short_description = 'KPIs empleabilidad'

    def crear_usuario_portal_view(self, request, cliente_id):
        cliente = self.get_object(request, str(cliente_id))
        if not cliente:
            self.message_user(request, 'Cliente no encontrado.', level=messages.ERROR)
            return redirect('admin:core_cliente_changelist')
        if not self.has_change_permission(request, cliente):
            raise PermissionDenied

        from portal.forms_usuarios import CrearUsuarioPortalForm
        from portal.provision import cupos_restantes, cupos_totales, cupos_usados

        initial = {
            'email': cliente.email,
            'first_name': cliente.contacto_principal,
            'is_active': True,
        }
        if request.method == 'POST':
            form = CrearUsuarioPortalForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        user = form.save(cliente)
                except forms.ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    pwd = getattr(user, '_password_plano_provision', '')
                    self.message_user(
                        request,
                        (
                            f'Usuario portal "{user.username}" creado para {cliente.nombre}. '
                            f'Contraseña temporal: {pwd} — el usuario debe cambiarla en el primer ingreso.'
                        ),
                        level=messages.SUCCESS,
                    )
                    return redirect('admin:core_cliente_change', cliente.pk)
        else:
            form = CrearUsuarioPortalForm(initial=initial)

        context = {
            **self.admin_site.each_context(request),
            'title': f'Crear usuario portal para {cliente.nombre}',
            'opts': self.model._meta,
            'original': cliente,
            'cliente': cliente,
            'form': form,
            'cupos_usados': cupos_usados(cliente),
            'cupos_totales': cupos_totales(cliente),
            'cupos_restantes': cupos_restantes(cliente),
            'change_url': reverse('admin:core_cliente_change', args=[cliente.pk]),
        }
        return render(request, 'admin/core/cliente/crear_usuario_portal.html', context)
    
    def estudiantes_activos(self, obj):
        count = obj.total_estudiantes()
        if count > 0:
            return format_html('<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    estudiantes_activos.short_description = "👥 Estudiantes"
    
    def numero_meta_badge(self, obj):
        if obj.numero_whatsapp_autorizado:
            return format_html(
                '<span style="background:#25d366;color:white;padding:4px 10px;border-radius:12px;font-size:11px;font-weight:600;">✅ Meta OK</span><br>'
                '<span style="font-size:10px;color:#666;">{}</span>',
                obj.numero_whatsapp_autorizado
            )
        return format_html('<span style="background:#ff9800;color:white;padding:4px 10px;border-radius:12px;font-size:11px;">⚠️ Sin Meta</span>')
    numero_meta_badge.short_description = "📱 WhatsApp Meta"

    def cursos_asignados(self, obj):
        count = obj.total_cursos()
        if count > 0:
            return format_html('<span style="background:#2196f3;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    cursos_asignados.short_description = "📚 Cursos"

    actions = [
        'copiar_todos_cursos_a_analytics_pruebas',
        'copiar_conocimiento_nati_desde_agronexo',
    ]

    @admin.action(description='📋 Copiar todos los cursos → Analytics (Pruebas)')
    def copiar_todos_cursos_a_analytics_pruebas(self, request, queryset):
        from core.copiar_cursos import (
            ClienteOrigenNoEncontrado,
            copiar_cursos_a_pruebas,
            obtener_cliente_analytics_origen,
        )

        if queryset.count() != 1:
            self.message_user(request, 'Selecciona un solo cliente.', level='error')
            return
        cliente = queryset.first()
        try:
            origen = obtener_cliente_analytics_origen()
        except ClienteOrigenNoEncontrado as e:
            self.message_user(request, str(e), level='error')
            return
        if cliente.pk != origen.pk:
            self.message_user(
                request,
                f'Selecciona el cliente «{origen.nombre}» (origen Alitic).',
                level='error',
            )
            return
        result = copiar_cursos_a_pruebas()
        self.message_user(
            request,
            f'✅ {result.total_copiados} curso(s) copiados a {result.destino.nombre}. '
            f'Omitidos (ya existían): {len(result.omitidos)}.',
        )

    @admin.action(description='🌿 Nati: copiar conocimiento desde Agronexo / general')
    def copiar_conocimiento_nati_desde_agronexo(self, request, queryset):
        """
        Seleccione el/los clientes DESTINO. Copia biblioteca + RAG comercial
        desde Agronexo y documentos generales (cliente vacío), sin re-subir archivos.
        """
        from core.copiar_conocimiento_nati import (
            FuenteConocimientoNoEncontrada,
            copiar_conocimiento_a_cliente,
        )

        if not queryset.exists():
            self.message_user(request, 'Seleccione al menos un cliente destino.', level='error')
            return
        ok = 0
        for destino in queryset:
            try:
                r = copiar_conocimiento_a_cliente(destino)
            except FuenteConocimientoNoEncontrada as e:
                self.message_user(request, f'{destino.nombre}: {e}', level='error')
                continue
            ok += 1
            self.message_user(
                request,
                f'✅ {destino.nombre}: bib +{r.bib_copiados} (omit {r.bib_omitidos}), '
                f'RAG +{r.rag_copiados} (omit {r.rag_omitidos}). Indexación en cola.',
            )
        if ok == 0:
            self.message_user(
                request,
                'Ninguna copia realizada. Suba docs a Agronexo o como RAG general (cliente vacío).',
                level='warning',
            )


