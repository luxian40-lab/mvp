from django.contrib import admin

from calculadora_margen.models import CalculoMargen, MargenEnlaceCliente, MargenUsoEvento


@admin.register(CalculoMargen)
class CalculoMargenAdmin(admin.ModelAdmin):
    list_display = ('producto', 'margen_actual', 'costo_unitario', 'cliente', 'creado_en')
    list_filter = ('creado_en',)
    search_fields = ('producto',)
    readonly_fields = ('creado_en',)


@admin.register(MargenEnlaceCliente)
class MargenEnlaceClienteAdmin(admin.ModelAdmin):
    list_display = ('slug', 'cliente', 'token', 'activo', 'actualizado_en')
    search_fields = ('slug', 'token', 'cliente__nombre')
    list_filter = ('activo',)


@admin.register(MargenUsoEvento)
class MargenUsoEventoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'evento', 'margen_rango', 'curso_id', 'creado_en')
    list_filter = ('evento', 'creado_en')
    search_fields = ('session_key',)
