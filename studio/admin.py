from django.contrib import admin

from .models import AccesoCursoPagado, CreadorStudio, CuentaAula, PublicacionStudio


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
