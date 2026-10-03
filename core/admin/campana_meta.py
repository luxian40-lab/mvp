"""Admin Unfold: plantillas y campañas Meta (Graph API)."""
from django.contrib import admin, messages

from core.admin._common import *  # noqa: F401,F403
from core.models_campana_meta import CampanaMeta, PlantillaMeta, TarjetaPlantillaMeta


class TarjetaPlantillaMetaInline(admin.TabularInline):
    model = TarjetaPlantillaMeta
    extra = 0
    fields = (
        'orden',
        'titulo',
        'cuerpo',
        'boton_ver_texto',
        'boton_info_texto',
        'info_url',
    )


@admin.register(PlantillaMeta)
class PlantillaMetaAdmin(admin.ModelAdmin):
    list_display = ('nombre_interno', 'tipo', 'categoria', 'estado_badge', 'activa')
    inlines = [TarjetaPlantillaMetaInline]
    list_filter = ('estado', 'tipo', 'categoria', 'activa', 'idioma')
    search_fields = ('nombre_interno', 'meta_name', 'meta_template_id', 'cuerpo')
    list_per_page = 50
    actions = ['sincronizar_seleccionadas', 'enviar_a_meta']
    readonly_fields = (
        'meta_template_id',
        'waba_id',
        'rejected_reason',
        'ultimo_error_code',
        'ultimo_error_mensaje',
        'enviada_en',
        'sincronizada_en',
    )

    fieldsets = (
        ('Datos', {
            'classes': ['tab'],
            'fields': ('nombre_interno', 'tipo', 'estado', 'meta_name', 'idioma', 'categoria', 'activa'),
            'description': (
                'Se crea en el WABA de Cloud API (WHATSAPP_BUSINESS_ACCOUNT_ID). '
                'No genera Content SID de Twilio. '
                'El estado se guarda con la ficha: márquelo Aprobada cuando Meta ya la aceptó.'
            ),
        }),
        ('Componentes', {
            'classes': ['tab'],
            'fields': (
                'header_texto',
                'header_ejemplo',
                'cuerpo',
                'ejemplos_cuerpo',
                'footer',
                'boton_1_tipo',
                'boton_1_texto',
                'boton_1_url',
                'boton_1_ejemplo',
                'boton_2_tipo',
                'boton_2_texto',
                'boton_2_url',
                'boton_2_ejemplo',
            ),
        }),
        ('Estado en Meta', {
            'classes': ['tab'],
            'fields': (
                'meta_template_id',
                'waba_id',
                'rejected_reason',
                'ultimo_error_code',
                'ultimo_error_mensaje',
                'enviada_en',
                'sincronizada_en',
            ),
        }),
    )

    @admin.display(description='Aprobación', ordering='estado')
    def estado_badge(self, obj):
        label = obj.get_estado_display()
        if obj.estado == 'APPROVED':
            bg, color = '#e8f5e9', '#2e7d32'
        elif obj.estado in ('REJECTED', 'ERROR', 'DISABLED'):
            bg, color = '#ffebee', '#c62828'
        elif obj.estado in ('PENDING', 'IN_APPEAL'):
            bg, color = '#fff3e0', '#e65100'
        else:
            bg, color = '#f5f5f5', '#424242'
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:700;">{}</span>',
            bg,
            color,
            label,
        )

    @admin.action(description='Sincronizar estado con Meta')
    def sincronizar_seleccionadas(self, request, queryset):
        from core.meta_waba import sincronizar_plantilla

        ok = 0
        for plantilla in queryset:
            resultado = sincronizar_plantilla(plantilla)
            if resultado.get('success'):
                ok += 1
            else:
                self.message_user(
                    request,
                    f'{plantilla.nombre_interno}: {resultado.get("message")}',
                    level=messages.WARNING,
                )
        self.message_user(request, f'{ok} plantilla(s) sincronizada(s).', level=messages.SUCCESS)

    @admin.action(description='Enviar plantilla a Meta para aprobación')
    def enviar_a_meta(self, request, queryset):
        from core.meta_waba import crear_plantilla_en_meta

        for plantilla in queryset:
            resultado = crear_plantilla_en_meta(plantilla)
            nivel = messages.SUCCESS if resultado.get('success') else messages.ERROR
            texto = resultado.get('message') or f'Enviada. ID {resultado.get("template_id")} ({resultado.get("status")})'
            if resultado.get('success'):
                texto = f'{plantilla.nombre_interno}: ID {resultado.get("template_id")} ({resultado.get("status")})'
            else:
                texto = f'{plantilla.nombre_interno}: {resultado.get("message")}'
            self.message_user(request, texto, level=nivel)


@admin.register(CampanaMeta)
class CampanaMetaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'plantilla', 'estado_plantilla', 'conteo_destinatarios', 'ejecutada', 'total_enviados')
    list_filter = ('ejecutada', 'cliente', 'plantilla__estado')
    search_fields = ('nombre', 'plantilla__meta_name', 'plantilla__nombre_interno')
    filter_horizontal = ('destinatarios',)
    autocomplete_fields = ('cliente', 'grupo')
    actions = ['ejecutar_campanas']
    readonly_fields = ('ejecutada', 'total_enviados')

    fieldsets = (
        ('Datos', {
            'classes': ['tab'],
            'fields': ('nombre', 'cliente'),
        }),
        ('Plantilla', {
            'classes': ['tab'],
            'fields': ('plantilla', 'mapeo_header', 'mapeo_body', 'mapeo_boton', 'phone_number_id'),
            'description': (
                'Solo se envía si la plantilla está Aprobada. '
                'El envío sale por Cloud API (phone number ID), no por Twilio.'
            ),
        }),
        ('Audiencia', {
            'classes': ['tab'],
            'fields': ('grupo', 'destinatarios'),
            'description': 'Si elige grupo, se usa el grupo. Si no, los destinatarios marcados.',
        }),
        ('Resultado', {
            'classes': ['tab'],
            'fields': ('ejecutada', 'total_enviados'),
        }),
    )

    def estado_plantilla(self, obj):
        return obj.plantilla.estado if obj.plantilla_id else '—'
    estado_plantilla.short_description = 'Estado plantilla'

    def conteo_destinatarios(self, obj):
        if obj.grupo_id:
            return obj.grupo.estudiantes.filter(activo=True).count()
        return obj.destinatarios.filter(activo=True).count()
    conteo_destinatarios.short_description = 'Destinatarios'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'plantilla':
            kwargs['queryset'] = PlantillaMeta.objects.filter(activa=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.action(description='Ejecutar campañas Meta (envío Cloud API)')
    def ejecutar_campanas(self, request, queryset):
        from core.meta_waba import encolar_campana_meta

        for campana in queryset:
            if campana.plantilla.estado != 'APPROVED':
                self.message_user(
                    request,
                    f'{campana.nombre}: la plantilla está en {campana.plantilla.estado}. '
                    f'Solo se envía Aprobada.',
                    level=messages.ERROR,
                )
                continue
            if campana.grupo_id:
                n = campana.grupo.estudiantes.filter(activo=True).count()
            else:
                n = campana.destinatarios.filter(activo=True).count()
            if n == 0:
                self.message_user(
                    request,
                    f'{campana.nombre}: no tiene destinatarios.',
                    level=messages.WARNING,
                )
                continue
            try:
                modo = encolar_campana_meta(campana.id)
            except Exception as exc:
                self.message_user(request, f'{campana.nombre}: {exc}', level=messages.ERROR)
                continue
            self.message_user(
                request,
                f'{campana.nombre} encolada ({modo}) para {n} destinatario(s).',
                level=messages.SUCCESS,
            )
