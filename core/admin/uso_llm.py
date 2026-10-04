"""UsoLLM solo se consulta. El costo no se edita a mano."""
from django.contrib import admin

from core.models_uso_llm import UsoLLM


@admin.register(UsoLLM)
class UsoLLMAdmin(admin.ModelAdmin):
    list_display = (
        'creado', 'cliente', 'agente', 'modelo',
        'tokens_in', 'tokens_out', 'costo_usd_est', 'estimado',
    )
    list_filter = ('agente', 'modelo', 'estimado', 'creado')
    search_fields = ('agente', 'modelo')
    ordering = ('-creado',)
    date_hierarchy = 'creado'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
