from django.contrib import admin

from .models import EntregaTarea, TareaCurso


@admin.register(TareaCurso)
class TareaCursoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'modulo', 'activa', 'fecha_limite', 'fecha_creacion')
    list_filter = ('activa', 'curso__cliente', 'curso')
    search_fields = ('titulo', 'curso__nombre')
    autocomplete_fields = ('curso', 'modulo')
    ordering = ('-fecha_creacion',)


@admin.register(EntregaTarea)
class EntregaTareaAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'tarea', 'nota', 'fecha_entrega', 'fecha_calificacion')
    list_filter = ('tarea__curso', 'nota')
    search_fields = ('estudiante__nombre', 'estudiante__cedula', 'tarea__titulo')
    readonly_fields = ('fecha_entrega', 'fecha_calificacion', 'calificado_por')
    autocomplete_fields = ('tarea', 'estudiante')
