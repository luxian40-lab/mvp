"""Admin Unfold: entrenar a Coach, Profe IA y Ventas sin deploy."""
from django.contrib import admin, messages
from django.utils.safestring import mark_safe

from core.admin._common import *  # noqa: F401,F403
from core.conocimiento_agentes import limpiar_cache_conocimiento
from core.models_agentes import ConocimientoAgente


@admin.register(ConocimientoAgente)
class ConocimientoAgenteAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'agente', 'tipo', 'estado', 'origen', 'actualizado_en')
    list_filter = ('estado', 'agente', 'tipo', 'origen')
    search_fields = ('titulo', 'contenido', 'pregunta_origen')
    list_per_page = 50
    ordering = ('-actualizado_en',)
    readonly_fields = ('pregunta_origen', 'respuesta_origen', 'origen', 'revisado_por', 'creado_en', 'actualizado_en')
    actions = ['aprobar', 'descartar']
    fieldsets = (
        ('Qué aprende el agente', {
            'fields': ('agente', 'tipo', 'titulo', 'contenido', 'estado', 'orden'),
            'description': mark_safe(
                '<p>Solo lo <strong>Aprobado</strong> entra a la IA (tarda hasta 5 minutos). '
                'Escriba corto: un dato, una respuesta validada o una regla de tono. '
                'Nat se alimenta en <a href="/admin/knowledge-studio/">Knowledge Studio</a>.</p>'
            ),
        }),
        ('De dónde salió', {
            'classes': ['collapse'],
            'fields': ('origen', 'pregunta_origen', 'respuesta_origen', 'revisado_por', 'creado_en', 'actualizado_en'),
            'description': (
                'Las sugerencias salen solas de una muestra de preguntas reales (sin teléfono, '
                'correos ni números). Corrija la respuesta en el campo de arriba antes de aprobar.'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        if 'estado' in form.changed_data:
            obj.revisado_por = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Aprobar (el agente lo empieza a usar)')
    def aprobar(self, request, queryset):
        n = queryset.update(estado=ConocimientoAgente.ESTADO_APROBADO, revisado_por=request.user)
        limpiar_cache_conocimiento()
        self.message_user(request, f'{n} aprobado(s).', level=messages.SUCCESS)

    @admin.action(description='Descartar')
    def descartar(self, request, queryset):
        n = queryset.update(estado=ConocimientoAgente.ESTADO_DESCARTADO, revisado_por=request.user)
        limpiar_cache_conocimiento()
        self.message_user(request, f'{n} descartado(s).', level=messages.SUCCESS)
