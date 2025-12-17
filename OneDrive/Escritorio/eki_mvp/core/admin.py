from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
import openpyxl
from django.http import HttpResponse
from .models import Estudiante, Plantilla, Campana, EnvioLog, Linea
from .services import ejecutar_campana_servicio

# =================================================
# 1. ACCIÓN: EXPORTAR A EXCEL (Estilo Andrés)
# =================================================
@admin.action(description='📥 Descargar Reporte Excel')
def exportar_logs_excel(modeladmin, request, queryset):
    """
    Genera un Excel idéntico a la tabla que ve Andrés.
    """
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="reporte_envios.xlsx"'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = 'Reporte de Envíos'

    # Encabezados (Iguales a la imagen)
    columns = ['ID', 'Receptor (Estudiante)', 'Teléfono', 'Estado', 'Fecha Envío', 'Campaña', 'Plantilla', 'Respuesta API']
    worksheet.append(columns)

    # Datos
    for log in queryset:
        # Quitamos la zona horaria para que Excel no moleste
        fecha_sin_tz = log.fecha_envio.replace(tzinfo=None) if log.fecha_envio else ""
        
        row = [
            log.id,
            log.estudiante.nombre,
            log.estudiante.telefono,
            log.estado,
            fecha_sin_tz,
            log.campana.nombre,
            log.campana.plantilla.nombre_interno,
            log.respuesta_api
        ]
        worksheet.append(row)

    workbook.save(response)
    return response

# =================================================
# 2. CONFIGURACIÓN DE TABLAS
# =================================================

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'activo', 'fecha_registro')
    search_fields = ('nombre', 'telefono')
    list_per_page = 20

@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ('nombre_interno', 'vista_previa')
    search_fields = ('nombre_interno',)
    
    def vista_previa(self, obj):
        return obj.cuerpo_mensaje[:50] + "..."
    vista_previa.short_description = "Cuerpo del Mensaje"

@admin.register(Campana)
class CampanaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estado_visual', 'conteo_destinatarios', 'fecha_creacion')
    list_filter = ('ejecutada', 'fecha_creacion')
    search_fields = ('nombre',)
    filter_horizontal = ('destinatarios',)
    
    # Configuramos para que el formulario de crear sea limpio
    fieldsets = (
        ('📝 Datos Básicos', {
            'fields': ('nombre', 'plantilla', 'canal_envio', 'linea_origen')
        }),
        ('📂 Importar (Opcional)', {
            'fields': ('archivo_excel',),
            'description': 'Sube un Excel con columnas A (Nombre) y B (Teléfono).'
        }),
        ('👥 Audiencia', {
            'fields': ('destinatarios',)
        }),
    )

    # Botón para enviar desde la lista
    actions = ['enviar_campana_accion']

    @admin.action(description='🚀 Ejecutar Campaña (Enviar Mensajes)')
    def enviar_campana_accion(self, request, queryset):
        for campana in queryset:
            if campana.ejecutada:
                self.message_user(request, f"⚠️ '{campana.nombre}' ya fue enviada antes.", level=messages.WARNING)
                continue
            
            res = ejecutar_campana_servicio(campana)
            self.message_user(request, f"✅ '{campana.nombre}': {res['exitosos']} enviados, {res['fallidos']} errores.", level=messages.SUCCESS)

    def estado_visual(self, obj):
        if obj.ejecutada:
            return format_html('<span style="color: green;">✅ Ejecutada</span>')
        return format_html('<span style="color: orange;">⏳ Pendiente</span>')
    estado_visual.short_description = "Estado"
    
    def conteo_destinatarios(self, obj):
        return obj.destinatarios.count()
    conteo_destinatarios.short_description = "# Destinatarios"


# ESTA ES LA TABLA QUE SE PARECE A LA IMAGEN
@admin.register(EnvioLog)
class EnvioLogAdmin(admin.ModelAdmin):
    # Columnas exactas de la imagen
    list_display = ('id', 'estudiante_nombre', 'estado_color', 'fecha_envio', 'nombre_plantilla', 'detalle_mensaje')
    
    # Filtros laterales (Simulan los tabs y fechas)
    list_filter = ('estado', 'fecha_envio', 'campana__nombre')
    
    # Buscador general
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'campana__nombre')
    
    # Botón de exportar
    actions = [exportar_logs_excel]
    
    # Solo lectura (historial no se debe editar)
    readonly_fields = ('campana', 'estudiante', 'estado', 'respuesta_api', 'fecha_envio')

    def estudiante_nombre(self, obj):
        return f"{obj.estudiante.nombre} ({obj.estudiante.telefono})"
    estudiante_nombre.short_description = "Receptor"

    def nombre_plantilla(self, obj):
        return obj.campana.plantilla.nombre_interno
    nombre_plantilla.short_description = "Plantilla"

    def detalle_mensaje(self, obj):
        # Mostramos el inicio del mensaje
        msg = obj.campana.plantilla.cuerpo_mensaje.replace("{nombre}", obj.estudiante.nombre)
        return msg[:40] + "..."
    detalle_mensaje.short_description = "Detalle"

    def estado_color(self, obj):
        if obj.estado == 'ENVIADO':
            return format_html('<b style="color:green;">ENVIADO</b>')
        elif obj.estado == 'FALLIDO':
            return format_html('<b style="color:red;">FALLIDO</b>')
        return obj.estado
    estado_color.short_description = "Estado"