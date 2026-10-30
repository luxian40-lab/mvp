"""Admin Unfold: entrenar a Coach, Profe IA y Ventas sin deploy."""
from django.contrib import admin, messages
from django.utils.safestring import mark_safe

from core.admin._common import *  # noqa: F401,F403
from core.conocimiento_agentes import limpiar_cache_conocimiento
from core.models import DerivacionAsesoria, FichaNegocio
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


@admin.register(FichaNegocio)
class FichaNegocioAdmin(admin.ModelAdmin):
    list_display = ('telefono', 'dedica', 'lugar', 'etapa', 'equipo', 'actualizada_en')
    list_filter = ('etapa', 'equipo')
    search_fields = ('telefono', 'dedica')
    list_per_page = 50
    ordering = ('-actualizada_en',)
    readonly_fields = ('preguntadas', 'pendiente', 'pendiente_desde', 'saltadas', 'creada_en', 'actualizada_en')
    fieldsets = (
        ('Lo que contó la persona', {
            'fields': ('telefono', 'trato', 'como_esta', 'lugar', 'dedica', 'etapa', 'equipo'),
            'description': (
                'Lo leen el que deriva la pregunta y los agentes. '
                'Se corrige aquí; la persona no vuelve a ver una pregunta ya hecha.'
            ),
        }),
        ('Preguntas', {
            'classes': ['collapse'],
            'fields': ('preguntadas', 'pendiente', 'pendiente_desde', 'saltadas', 'creada_en', 'actualizada_en'),
        }),
    )


@admin.register(DerivacionAsesoria)
class DerivacionAsesoriaAdmin(admin.ModelAdmin):
    """Revisión semanal: las últimas 20, y cuántas se corrigieron en 7 días."""
    list_display = ('creada_en', 'frase', 'agente', 'agente_secundario', 'corregida', 'corregida_a', 'fuente')
    list_filter = ('corregida', 'agente', 'fuente', 'con_contexto', 'creada_en')
    search_fields = ('frase',)
    list_per_page = 20
    ordering = ('-creada_en',)
    readonly_fields = (
        'creada_en', 'frase', 'agente', 'agente_secundario', 'fuente', 'con_contexto',
        'corregida', 'corregida_a', 'telefono_hash',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from core.lineas.principal.derivaciones import resumen_semana

        total, corregidas = resumen_semana()
        if total:
            titulo = (
                f'Derivaciones de asesoría · 7 días: {total}, corregidas {corregidas} '
                f'({round(100 * corregidas / total)} %)'
            )
        else:
            titulo = 'Derivaciones de asesoría · 7 días: sin derivaciones'
        extra_context = {**(extra_context or {}), 'title': titulo}
        return super().changelist_view(request, extra_context=extra_context)
