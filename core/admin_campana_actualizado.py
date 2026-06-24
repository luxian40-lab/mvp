from django.contrib import admin
from .models import CampanaUnica, RespuestaCampanaUnica, Estudiante
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
from .exportar_respuestas_xlsx import exportar_respuestas_xlsx


class RespuestaCampanaUnicaInline(admin.TabularInline):
    model = RespuestaCampanaUnica
    extra = 0
    can_delete = False
    readonly_fields = (
        'numero_telefono',
        'nombre_estudiante_inline',
        'respuesta',
        'fecha_respuesta',
        'mensaje_sid',
    )
    fields = readonly_fields

    def nombre_estudiante_inline(self, obj):
        if obj.estudiante_id:
            return obj.estudiante.nombre
        return '—'

    nombre_estudiante_inline.short_description = 'Estudiante'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CampanaUnica)
class CampanaUnicaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'cliente', 'estado', 'total_enviados', 'respuestas_si', 'respuestas_no', 'fecha_envio', 'descargar_xlsx_link']
    list_filter = ['estado', 'fecha_envio', 'cliente']
    search_fields = ['nombre']
    readonly_fields = ['respuestas_si', 'respuestas_no', 'total_enviados', 'fecha_envio']
    filter_horizontal = ['estudiantes']  # Widget de selección doble para estudiantes
    fieldsets = (
        ('Información General', {
            'fields': ('cliente', 'nombre', 'contenido', 'estado')
        }),
        ('Twilio', {
            'fields': ('template_twilio_id',),
            'description': 'El Content SID del template aprobado en Twilio (ej: HX54ce1b4c564fe15aa4e4941b203e076d).'
        }),
        ('Destinatarios', {
            'fields': ('estudiantes',),
            'description': '⚠️ Si dejas vacío, se enviará a TODOS los estudiantes activos del cliente. Si seleccionas estudiantes específicos, solo se les enviará a ellos.'
        }),
        ('Estadísticas (solo lectura)', {
            'fields': ('total_enviados', 'respuestas_si', 'respuestas_no', 'fecha_envio'),
            'classes': ('collapse',)
        }),
    )
    actions = ['enviar_campana_unica']
    inlines = [RespuestaCampanaUnicaInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:campana_id>/descargar-xlsx/', self.admin_site.admin_view(self.descargar_xlsx), name='descargar_xlsx_campana'),
        ]
        return custom_urls + urls

    def descargar_xlsx(self, request, campana_id):
        return exportar_respuestas_xlsx(request, campana_id)

    def descargar_xlsx_link(self, obj):
        if obj.respuestas_si > 0 or obj.respuestas_no > 0:
            url = f"/admin/core/campanaunica/{obj.id}/descargar-xlsx/"
            return format_html('<a class="button" href="{}">⬇️ XLSX</a>', url)
        return "-"
    descargar_xlsx_link.short_description = "Exportar"

    def enviar_campana_unica(self, request, queryset):
        """Enviar campaña única usando Twilio Content Template"""
        from .utils import enviar_whatsapp_twilio_content_template
        import json
        
        total_ok = 0
        total_err = 0
        errores_detalle = []
        
        for campana in queryset:
            # Validar Content SID
            if not campana.template_twilio_id or not campana.template_twilio_id.strip():
                self.message_user(request, f"❌ '{campana.nombre}' no tiene Content SID de Twilio. Edita la campaña y agrega el SID.", messages.ERROR)
                continue
            
            content_sid = campana.template_twilio_id.strip()
            
            # Determinar destinatarios: seleccionados o todos del cliente
            if campana.estudiantes.exists():
                destinatarios = campana.estudiantes.filter(activo=True)
                origen = "seleccionados"
            else:
                destinatarios = Estudiante.objects.filter(cliente=campana.cliente, activo=True)
                origen = f"todos del cliente '{campana.cliente}'"
            
            if not destinatarios.exists():
                self.message_user(request, f"⚠️ No hay estudiantes activos ({origen}) para '{campana.nombre}'.", messages.WARNING)
                continue
            
            print(f"📤 CAMPAÑA ÚNICA: Enviando '{campana.nombre}' a {destinatarios.count()} estudiantes ({origen})", flush=True)
            print(f"📤 Content SID: {content_sid}", flush=True)
            
            for est in destinatarios:
                try:
                    # Variables del template - se adaptan al template del usuario
                    variables = {
                        '1': est.nombre or 'Estimado/a',
                    }
                    
                    print(f"📤 Enviando a {est.nombre} ({est.telefono}) con SID {content_sid} vars={json.dumps(variables)}", flush=True)
                    
                    resultado = enviar_whatsapp_twilio_content_template(
                        est.telefono,
                        content_sid,
                        variables
                    )
                    
                    if resultado.get('success'):
                        total_ok += 1
                        print(f"✅ Enviado OK a {est.nombre}: {resultado.get('mensaje_id')}", flush=True)
                    else:
                        total_err += 1
                        error_msg = resultado.get('response', 'Error desconocido')
                        errores_detalle.append(f"{est.nombre}: {error_msg}")
                        print(f"❌ FALLÓ envío a {est.nombre} ({est.telefono}): {error_msg}", flush=True)
                except Exception as e:
                    total_err += 1
                    errores_detalle.append(f"{est.nombre}: {str(e)}")
                    print(f"❌ EXCEPCIÓN enviando a {est.nombre}: {e}", flush=True)
            
            # Actualizar campaña
            campana.total_enviados = total_ok + total_err
            campana.estado = 'enviada'
            campana.fecha_envio = timezone.now()
            campana.save()
        
        # Mensaje de resultado al admin
        if total_ok > 0 and total_err == 0:
            self.message_user(request, f"✅ Campaña enviada exitosamente a {total_ok} estudiantes.", messages.SUCCESS)
        elif total_ok > 0:
            self.message_user(request, f"⚠️ Enviados: {total_ok} OK, {total_err} errores. Errores: {'; '.join(errores_detalle[:3])}", messages.WARNING)
        else:
            self.message_user(request, f"❌ Todos los envíos fallaron ({total_err} errores). Detalle: {'; '.join(errores_detalle[:3])}", messages.ERROR)
    
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
