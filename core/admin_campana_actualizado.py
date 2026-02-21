from django.contrib import admin
from .models import CampanaUnica, RespuestaCampanaUnica, Estudiante
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
from .exportar_respuestas_xlsx import exportar_respuestas_xlsx

@admin.register(CampanaUnica)
class CampanaUnicaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'estado', 'total_enviados', 'respuestas_si', 'respuestas_no', 'fecha_envio', 'descargar_xlsx_link']
    list_filter = ['estado', 'fecha_envio', 'cliente']
    search_fields = ['nombre']
    readonly_fields = ['respuestas_si', 'respuestas_no', 'total_enviados', 'fecha_envio']
    fieldsets = (
        ('Información General', {
            'fields': ('cliente', 'nombre', 'contenido', 'estado')
        }),
        ('Twilio', {
            'fields': ('template_twilio_id',),
            'description': 'El Content SID del template aprobado en Twilio (ej: HX123abc...). Las variables del template se llenan automáticamente.'
        }),
        ('Estadísticas', {
            'fields': ('total_enviados', 'respuestas_si', 'respuestas_no', 'fecha_envio')
        }),
    )
    actions = ['enviar_campana_unica']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:campana_id>/descargar-xlsx/', self.admin_site.admin_view(self.descargar_xlsx), name='descargar_xlsx_campana'),
        ]
        return custom_urls + urls

    def descargar_xlsx(self, request, campana_id):
        return exportar_respuestas_xlsx(request, campana_id)

    def descargar_xlsx_link(self, obj):
        if obj.estado == 'enviada' or obj.respuestas_si > 0 or obj.respuestas_no > 0:
            url = f"/admin/core/campanaunica/{obj.id}/descargar-xlsx/"
            return format_html('<a class="button" href="{}">⬇️ Descargar XLSX</a>', url)
        return "-"
    descargar_xlsx_link.short_description = "Descargar XLSX"

    def enviar_campana_unica(self, request, queryset):
        """Enviar campaña única a todos los estudiantes del cliente usando Twilio Content Template"""
        from .utils import enviar_whatsapp_twilio_content_template
        
        total_ok = 0
        total_err = 0
        
        for campana in queryset:
            if campana.estado != 'borrador':
                self.message_user(request, f"⚠️ '{campana.nombre}' ya fue enviada. Solo se envían campañas en estado Borrador.", messages.WARNING)
                continue
            
            if not campana.template_twilio_id:
                self.message_user(request, f"❌ '{campana.nombre}' no tiene Content SID de Twilio configurado.", messages.ERROR)
                continue
            
            estudiantes = Estudiante.objects.filter(cliente=campana.cliente, activo=True)
            
            if not estudiantes.exists():
                self.message_user(request, f"⚠️ No hay estudiantes activos para el cliente '{campana.cliente}'.", messages.WARNING)
                continue
            
            for est in estudiantes:
                try:
                    # Variables del template: 1=nombre, 2=contenido
                    variables = {
                        '1': est.nombre or 'Estimado/a',
                        '2': campana.contenido,
                    }
                    resultado = enviar_whatsapp_twilio_content_template(
                        est.telefono,
                        campana.template_twilio_id,
                        variables
                    )
                    if resultado.get('success'):
                        total_ok += 1
                    else:
                        total_err += 1
                        print(f"⚠️ Campaña envío falló a {est.telefono}: {resultado.get('response')}", flush=True)
                except Exception as e:
                    total_err += 1
                    print(f"❌ Error enviando campaña a {est.telefono}: {e}", flush=True)
                
                campana.total_enviados += 1
            
            campana.estado = 'enviada'
            campana.fecha_envio = timezone.now()
            campana.save()
        
        self.message_user(
            request,
            f"✅ Campaña enviada: {total_ok} enviados correctamente, {total_err} errores.",
            messages.SUCCESS if total_err == 0 else messages.WARNING
        )
    enviar_campana_unica.short_description = "📤 Enviar campaña única (Twilio)"

@admin.register(RespuestaCampanaUnica)
class RespuestaCampanaUnicaAdmin(admin.ModelAdmin):
    list_display = ['numero_telefono', 'respuesta', 'nombre_estudiante', 'campana', 'fecha_respuesta']
    list_filter = ['respuesta', 'campana', 'fecha_respuesta']
    search_fields = ['numero_telefono']
    readonly_fields = ['campana', 'estudiante', 'numero_telefono', 'respuesta', 'fecha_respuesta', 'mensaje_sid']
    
    def nombre_estudiante(self, obj):
        return obj.estudiante.nombre if obj.estudiante else "No identificado"
    nombre_estudiante.short_description = "Nombre"
    
    def has_add_permission(self, request):
        return False
