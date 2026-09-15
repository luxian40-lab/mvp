from core.admin._common import *  # noqa: F401,F403
from core.models import ConfiguracionGlobal as _ConfiguracionGlobal

@admin.register(_ConfiguracionGlobal)
class ConfiguracionGlobalAdmin(admin.ModelAdmin):
    """Singleton: solo permite editar la fila id=1, no agregar ni borrar."""
    list_display = ('__str__', 'content_sid_habeas_data_global', 'fecha_actualizacion')
    readonly_fields = ('fecha_actualizacion',)
    fieldsets = (
        ('🛡️ Habeas Data — Plantilla Twilio general', {
            'fields': ('content_sid_habeas_data_global',),
            'description': (
                'Content SID (HX...) de la plantilla Twilio aprobada que se usa por defecto '
                'para enviar el Habeas Data cuando un cliente no tiene la suya propia. '
                'Cada Cliente puede sobrescribir este valor desde su ficha en '
                '"Habeas Data → Plantilla Twilio (Content SID del cliente)".'
            ),
        }),
        ('Auditoría', {
            'fields': ('fecha_actualizacion',),
        }),
    )

    def has_add_permission(self, request):
        return not _ConfiguracionGlobal.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        from django.urls import reverse
        obj = _ConfiguracionGlobal.get_solo()
        return redirect(reverse('admin:core_configuracionglobal_change', args=[obj.pk]))


class EventoIAAdmin(admin.ModelAdmin):
    """Solo lectura — audit trail IA (Parte 2A/2B)."""

    list_display = (
        'created_at', 'tipo', 'trace_id', 'estudiante', 'regla_aplicada',
        'agente', 'es_reto', 'canal',
    )
    list_filter = ('tipo', 'canal', 'regla_aplicada', 'created_at')
    search_fields = ('trace_id', 'input_preview', 'output_preview', 'agente')
    readonly_fields = [
        f.name for f in EventoIA._meta.fields
    ]
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class ContextoAgroSessionAdmin(admin.ModelAdmin):
    list_display = ('sesion', 'cultivo', 'etapa', 'region', 'problema', 'updated_at')
    list_filter = ('cultivo', 'region')
    search_fields = ('sesion__telefono', 'cultivo', 'problema', 'region', 'municipio')
    readonly_fields = ('updated_at',)


class ConversacionRAGCandidataAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_creacion', 'estado', 'telefono', 'cliente', 'pregunta_corta', 'revisado_por',
    )
    list_filter = ('estado', 'fecha_creacion', 'cliente')
    search_fields = ('telefono', 'pregunta', 'respuesta_nati')
    readonly_fields = ('fecha_creacion', 'fecha_revision', 'trace_id')
    actions = ['marcar_aprobada']

    @admin.display(description='Pregunta')
    def pregunta_corta(self, obj):
        return (obj.pregunta or '')[:80]

    @admin.action(description='Marcar aprobada (sin publicar)')
    def marcar_aprobada(self, request, queryset):
        from core.knowledge_studio import revisar_candidata

        for c in queryset.filter(estado=ConversacionRAGCandidata.ESTADO_PENDIENTE):
            revisar_candidata(c, usuario=request.user, accion='aprobar')


@admin.register(AlertaTerritorial)
class AlertaTerritorialAdmin(admin.ModelAdmin):
    list_display = (
        'actualizado_en', 'familia', 'subtipo', 'territory_id',
        'conteo', 'score', 'estado', 'ventana_horas',
    )
    list_filter = ('estado', 'familia')
    search_fields = ('territory_id', 'familia', 'explicacion')
    readonly_fields = ('creado_en', 'actualizado_en')
    actions = ('accion_validar', 'accion_cerrar')

    @admin.action(description='Validar (detectada → validada)')
    def accion_validar(self, request, queryset):
        from core.alerta_territorial_ops import transicionar_alerta

        ok = 0
        for a in queryset.filter(estado=AlertaTerritorial.ESTADO_DETECTADA):
            try:
                transicionar_alerta(
                    a,
                    nuevo_estado=AlertaTerritorial.ESTADO_VALIDADA,
                    usuario=request.user,
                    nota='admin_action',
                )
                ok += 1
            except ValueError:
                continue
        self.message_user(request, f'Validadas: {ok}')

    @admin.action(description='Cerrar alertas seleccionadas')
    def accion_cerrar(self, request, queryset):
        from core.alerta_territorial_ops import transicionar_alerta

        ok = 0
        for a in queryset.exclude(estado=AlertaTerritorial.ESTADO_CERRADA):
            try:
                transicionar_alerta(
                    a,
                    nuevo_estado=AlertaTerritorial.ESTADO_CERRADA,
                    usuario=request.user,
                    nota='admin_action',
                )
                ok += 1
            except ValueError:
                continue
        self.message_user(request, f'Cerradas: {ok}')


@admin.register(EventOutbox)
class EventOutboxAdmin(admin.ModelAdmin):
    list_display = (
        'ingested_at', 'event_type', 'territory_id', 'org_id',
        'published_at', 'pii_class',
    )
    list_filter = ('event_type', 'pii_class')
    search_fields = ('event_id', 'event_type', 'territory_id', 'lake_uri')
    readonly_fields = [f.name for f in EventOutbox._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(SenalTerritorial)
class SenalTerritorialAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'tipo', 'territory_id', 'confianza', 'fuente', 'org_id')
    list_filter = ('fuente', 'tipo')
    search_fields = ('tipo', 'territory_id')
    readonly_fields = ('creado_en',)


@admin.register(SandboxCanalSesion)
class SandboxCanalSesionAdmin(admin.ModelAdmin):
    list_display = ('actualizado_en', 'telefono', 'modo', 'memoria_corte_en', 'creado_en')
    list_filter = ('modo',)
    search_fields = ('telefono',)
    readonly_fields = ('creado_en', 'actualizado_en')

