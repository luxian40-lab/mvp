from django.contrib import admin
from unfold.admin import ModelAdmin

from core.lineas.modelo import LineaWhatsapp


@admin.register(LineaWhatsapp)
class LineaWhatsappAdmin(ModelAdmin):
    list_display = ('nombre', 'e164', 'phone_id', 'uso', 'waba_id', 'cliente', 'activo', 'orden')
    list_filter = ('uso', 'activo')
    search_fields = ('nombre', 'e164', 'phone_id', 'waba_id')
    list_select_related = ('cliente',)
    raw_id_fields = ('cliente',)
    filter_horizontal = ('cursos',)
    readonly_fields = ('creado_en', 'actualizado_en')
    fieldsets = (
        (None, {'fields': ('nombre', 'e164', 'phone_id', 'uso', 'activo', 'orden')}),
        ('Cursos', {'fields': ('cursos',)}),
        ('Cuenta', {'fields': ('waba_id', 'cliente')}),
        ('Registro', {'fields': ('creado_en', 'actualizado_en')}),
    )
