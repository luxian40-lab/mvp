from core.admin._common import *  # noqa: F401,F403

# ========== CLIENTE (NUEVO) ==========
class ConfiguracionDripClienteInline(admin.TabularInline):
    """Override de días entre módulos por curso (misma fila = un curso por cliente)."""
    model = ConfiguracionDripCliente
    extra = 0
    fields = ('curso', 'dias_espera_entre_modulos', 'activo')
    autocomplete_fields = ('curso',)
    verbose_name = 'Drip curso'
    verbose_name_plural = '⏱️ Ritmo drip por curso (override)'


class HabilitacionModuloEstudianteInline(admin.TabularInline):
    model = HabilitacionModuloEstudiante
    extra = 1
    fields = ('curso', 'modulo', 'habilitado_desde', 'activo', 'notas')
    autocomplete_fields = ('curso', 'modulo')
    verbose_name = 'Módulo individual'
    verbose_name_plural = (
        'Módulos habilitados solo para este estudiante '
        '(requiere «solo por lista» activo en el cliente)'
    )

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
    fields = ('curso', 'modulo', 'habilitado_desde', 'activo')
    autocomplete_fields = ('curso', 'modulo')
    verbose_name = 'Calendario módulo'
    verbose_name_plural = '📅 Habilitación de módulos por calendario'


class ProductoCatalogoInline(admin.TabularInline):
    model = ProductoCatalogo
    extra = 0
    fields = (
        'nombre', 'categoria', 'cultivos_objetivo',
        'precio_cop', 'unidad', 'url_producto', 'activo',
    )
    show_change_link = True


class PortalUsuarioInline(admin.TabularInline):
    model = PortalUsuario
    extra = 0
    fields = ('user', 'rol', 'portal_user_link')
    readonly_fields = ('portal_user_link',)
    autocomplete_fields = ('user',)
    verbose_name = 'Usuario del portal'
    verbose_name_plural = 'Usuarios del portal'

    def portal_user_link(self, obj):
        if not obj or not obj.user_id:
            return '-'
        url = reverse('admin:auth_user_change', args=[obj.user_id])
        return format_html('<a href="{}">Editar usuario / contraseña</a>', url)
    portal_user_link.short_description = 'Acceso'


class CrearUsuarioPortalForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=150)
    first_name = forms.CharField(label='Nombre', max_length=150, required=False)
    last_name = forms.CharField(label='Apellido', max_length=150, required=False)
    email = forms.EmailField(label='Email', required=False)
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput)
    rol = forms.ChoiceField(label='Rol', choices=PortalUsuario.ROL_CHOICES, initial='viewer')
    is_active = forms.BooleanField(label='Usuario activo', required=False, initial=True)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        User = get_user_model()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ya existe un usuario con ese username.')
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned

    def save(self, cliente):
        User = get_user_model()
        user = User(
            username=self.cleaned_data['username'],
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            email=self.cleaned_data.get('email', ''),
            is_staff=False,
            is_superuser=False,
            is_active=self.cleaned_data.get('is_active', True),
        )
        user.set_password(self.cleaned_data['password1'])
        user.save()
        PortalUsuario.objects.create(
            user=user,
            organizacion=cliente,
            rol=self.cleaned_data['rol'],
        )
        return user


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
    list_display = ('nombre', 'contacto_principal', 'email', 'numero_meta_badge', 'estudiantes_activos', 'cursos_asignados', 'activo', 'fecha_registro')
    list_filter = ('activo', 'enviar_certificados_email', 'fecha_registro')
    search_fields = ('nombre', 'nit', 'contacto_principal', 'email')
    list_per_page = 50
    ordering = ('-fecha_registro',)
    readonly_fields = (
        'portal_usuarios_acciones',
        'cobertura_y_drip_acciones',
        'empleabilidad_kpis_resumen',
        'usar_gamificacion',
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
        ('Portal B2B', {
            'fields': (
                'tipo_proyecto',
                'portal_modulos',
                'fecha_inicio_suscripcion',
                'fecha_fin_suscripcion',
                'logo_url',
                'portal_subtitulo',
                'portal_usuarios_acciones',
                'whatsapp_numero',
                'twilio_account_sid',
                'twilio_auth_token',
                'twilio_whatsapp_from',
            ),
            'description': (
                'Acceso web, branding y credenciales Twilio del cliente. '
                'Logo y subtítulo también en <code>/portal/perfil/</code> (rol admin).'
            ),
        }),
        ('WhatsApp, legal y grupo', {
            'fields': (
                'numero_whatsapp_autorizado',
                'enlace_habeas_data',
                'content_sid_habeas_data_twilio',
                'modo_avance_modulo',
                'content_sid_boton_listo',
                'enlace_grupo_whatsapp',
            ),
            'description': (
                'Número autorizado en Meta Business; política de datos (Habeas) y plantilla Twilio propia; '
                'avance por texto o botón «Listo» al cerrar cada módulo; enlace de invitación al grupo.'
            ),
        }),
        ('Certificados, drip y gamificación', {
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
                'Certificados por email y nota mínima; drip por estudiante (ver tablas al final); '
                'modo puntos o calificación 1–5.'
            ),
        }),
        ('Ventanas por fechas', {
            'fields': (
                'habilitar_pregunta_abierta_final',
                'fecha_inicio_pregunta_abierta_final',
                'fecha_fin_pregunta_abierta_final',
                'habilitar_gamificacion_proximidad',
                'fecha_inicio_gamificacion_proximidad',
                'fecha_fin_gamificacion_proximidad',
            ),
            'description': (
                'Cuándo se activa la pregunta abierta final y el radar de empleabilidad por proximidad.'
            ),
        }),
        ('Empleabilidad, IA y bot comercial', {
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
                'KPIs de exploración territorial (retención, misiones, oportunidades georreferenciadas). '
                'Exploración WhatsApp, nombres de agentes educativos y bot Nat/comercial. '
                'Catálogo e inlines al final del formulario.'
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

    def portal_usuarios_acciones(self, obj):
        if not obj or not obj.pk:
            return 'Guarda el cliente para crear usuarios del portal.'

        crear_url = reverse('admin:core_cliente_crear_usuario_portal', args=[obj.pk])
        usuarios_url = (
            reverse('admin:portal_portalusuario_changelist')
            + f'?organizacion__id__exact={obj.pk}'
        )
        portal_url = '/portal/login/'
        total = obj.usuarios_portal.count()

        return format_html(
            '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
            '<a class="button" href="{}">➕ Crear usuario portal</a>'
            '<a class="button" href="{}">Ver usuarios ({})</a>'
            '<a class="button" href="{}" target="_blank" rel="noopener">Abrir portal</a>'
            '</div>'
            '<p style="margin:8px 0 0;color:#666;">'
            'Crea aquí usuarios no-staff para esta organización. '
            'La contraseña queda en Django Auth; el rol y la organización quedan en PortalUsuario.'
            '</p>',
            crear_url,
            usuarios_url,
            total,
            portal_url,
        )
    portal_usuarios_acciones.short_description = 'Accesos portal'

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

        initial = {
            'email': cliente.email,
            'first_name': cliente.contacto_principal,
            'is_active': True,
        }
        if request.method == 'POST':
            form = CrearUsuarioPortalForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    user = form.save(cliente)
                self.message_user(
                    request,
                    f'Usuario portal "{user.username}" creado para {cliente.nombre}.',
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

    actions = ['copiar_todos_cursos_a_analytics_pruebas']

    @admin.action(description='📋 Copiar todos los cursos → Analytics (Pruebas)')
    def copiar_todos_cursos_a_analytics_pruebas(self, request, queryset):
        from core.copiar_cursos import (
            ClienteAnalyticsNoEncontrado,
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


