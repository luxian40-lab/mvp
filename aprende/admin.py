from django.contrib import admin
from django.utils import timezone

from .models import EntregaTarea, TareaCurso


@admin.register(TareaCurso)
class TareaCursoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'modulo', 'activa', 'fecha_limite', 'fecha_creacion')
    list_filter = ('activa', 'curso__cliente', 'curso')
    search_fields = ('titulo', 'curso__nombre')
    autocomplete_fields = ('curso', 'modulo')
    ordering = ('-fecha_creacion',)
    fieldsets = (
        (None, {
            'fields': ('curso', 'modulo', 'titulo', 'instrucciones', 'fecha_limite', 'activa', 'orden'),
            'description': (
                'Las tareas aparecen en el aula del estudiante (pestaña Tareas). '
                'Allí suben el archivo; usted califica en Entregas de tareas o el profesor en /aprende/profesor/.'
            ),
        }),
    )


@admin.register(EntregaTarea)
class EntregaTareaAdmin(admin.ModelAdmin):
    list_display = (
        'estudiante',
        'tarea',
        'nota',
        'pendiente_calificacion',
        'fecha_entrega',
        'fecha_calificacion',
    )
    list_filter = ('tarea__curso', 'nota', 'tarea__curso__cliente')
    search_fields = ('estudiante__nombre', 'estudiante__cedula', 'tarea__titulo')
    readonly_fields = ('fecha_entrega', 'fecha_calificacion', 'calificado_por', 'archivo', 'nombre_archivo')
    autocomplete_fields = ('tarea', 'estudiante')
    list_editable = ('nota',)
    fieldsets = (
        (None, {
            'fields': ('tarea', 'estudiante', 'archivo', 'nombre_archivo', 'comentario_estudiante', 'fecha_entrega'),
        }),
        ('Calificación', {
            'fields': ('nota', 'comentario_profesor', 'fecha_calificacion', 'calificado_por'),
            'description': 'Nota de 1 a 5. Guarde para que el estudiante la vea en el aula.',
        }),
    )

    @admin.display(boolean=True, description='Pendiente')
    def pendiente_calificacion(self, obj):
        return obj.nota is None

    def save_model(self, request, obj, form, change):
        if obj.nota is not None:
            if not obj.fecha_calificacion:
                obj.fecha_calificacion = timezone.now()
            if not obj.calificado_por_id:
                obj.calificado_por = request.user
        super().save_model(request, obj, form, change)
