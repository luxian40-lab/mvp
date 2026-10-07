from core.admin._common import *  # noqa: F401,F403
from core.models_meta_webhook import MetaWebhookEvento


@admin.register(MetaWebhookEvento)
class MetaWebhookEventoAdmin(admin.ModelAdmin):
    list_display = (
        'recibido_en',
        'telefono',
        'tipo',
        'resultado',
        'plan_efectivo',
        'estado_chat_antes',
        'error',
    )
    list_filter = ('resultado', 'tipo', 'firma_ok')
    search_fields = ('telefono', 'wamid', 'error')
    readonly_fields = (
        'wamid',
        'telefono',
        'tipo',
        'payload_raw',
        'firma_ok',
        'recibido_en',
        'procesado_en',
        'resultado',
        'error',
        'estado_chat_antes',
        'plan_efectivo',
    )

    def get_search_results(self, request, queryset, search_term):
        term = (search_term or '').strip()
        if term.isdigit() and len(term) <= 6:
            return queryset.filter(telefono__endswith=term), False
        return super().get_search_results(request, queryset, search_term)

    def has_add_permission(self, request):
        return False
