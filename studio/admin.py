from django.contrib import admin

from .models import (
    AccesoCursoPagado,
    CarritoStudio,
    CreadorStudio,
    CuentaAula,
    ItemCarritoStudio,
    OrdenItemStudio,
    OrdenStudio,
    PublicacionStudio,
)


@admin.register(CuentaAula)
class CuentaAulaAdmin(admin.ModelAdmin):
    list_display = ('email', 'nombre_visible', 'estudiante', 'activo', 'creado')
    search_fields = ('user__email', 'nombre_visible', 'estudiante__nombre')
    raw_id_fields = ('user', 'estudiante')


@admin.register(CreadorStudio)
class CreadorStudioAdmin(admin.ModelAdmin):
    list_display = ('nombre_publico', 'slug', 'activo', 'user', 'creado')
    list_editable = ('activo',)
    search_fields = ('nombre_publico', 'user__email')
    prepopulated_fields = {'slug': ('nombre_publico',)}


@admin.register(PublicacionStudio)
class PublicacionStudioAdmin(admin.ModelAdmin):
    list_display = ('curso', 'creador', 'precio_cop', 'destacado')
    list_filter = ('destacado',)
    raw_id_fields = ('curso', 'creador')


@admin.register(AccesoCursoPagado)
class AccesoCursoPagadoAdmin(admin.ModelAdmin):
    list_display = ('wompi_referencia', 'cuenta', 'curso', 'monto_cop', 'estado', 'pagado_en')
    list_filter = ('estado',)
    search_fields = ('wompi_referencia', 'wompi_transaccion_id', 'cuenta__user__email')
    raw_id_fields = ('cuenta', 'curso')


class ItemCarritoInline(admin.TabularInline):
    model = ItemCarritoStudio
    extra = 0
    raw_id_fields = ('publicacion',)


@admin.register(CarritoStudio)
class CarritoStudioAdmin(admin.ModelAdmin):
    list_display = ('cuenta', 'actualizado')
    raw_id_fields = ('cuenta',)
    inlines = [ItemCarritoInline]


class OrdenItemInline(admin.TabularInline):
    model = OrdenItemStudio
    extra = 0
    raw_id_fields = ('publicacion', 'curso')


@admin.register(OrdenStudio)
class OrdenStudioAdmin(admin.ModelAdmin):
    list_display = ('wompi_referencia', 'cuenta', 'monto_cop', 'estado', 'pagado_en', 'creado')
    list_filter = ('estado',)
    search_fields = ('wompi_referencia', 'cuenta__user__email')
    raw_id_fields = ('cuenta',)
    inlines = [OrdenItemInline]
