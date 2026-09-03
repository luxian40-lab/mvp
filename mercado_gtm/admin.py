from django.contrib import admin

from .models import EscenarioMercado


@admin.register(EscenarioMercado)
class EscenarioMercadoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'nombre_escenario', 'producto', 'cliente', 'confianza_estimacion', 'actualizado_en',
    )
    list_filter = ('confianza_estimacion', 'alcance')
    search_fields = ('nombre_escenario', 'producto', 'mercado_objetivo')
    readonly_fields = ('creado_en', 'actualizado_en')
