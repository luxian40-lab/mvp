"""
Admin completo: Estudiantes, Plantillas, Campañas, EnvioLog, Sistema Educativo
CON función de envío directo desde Plantillas Y gestión de cursos/módulos/exámenes
"""
from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin import helpers
from django.urls import path
from django.db import models  # ✅ Para usar Q() en queries
import openpyxl
from django.http import HttpResponse
from .models import (
    Estudiante, WhatsappLog, Plantilla, Campana, EnvioLog, Linea,
    Curso, Modulo, ProgresoEstudiante, ModuloCompletado,
    Examen, PreguntaExamen, ResultadoExamen, TemaCampana, Cliente,
    PerfilGamificacion, Badge, BadgeEstudiante, TransaccionPuntos
)
from .recompensas import Recompensa, CanjeRecompensa
from .utils import enviar_whatsapp_twilio
import logging

logger = logging.getLogger(__name__)


# ========== CLIENTE (NUEVO) ==========
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """Gestión de clientes/organizaciones"""
    list_display = ('nombre', 'contacto_principal', 'email', 'telefono', 'estudiantes_activos', 'cursos_asignados', 'activo', 'fecha_registro')
    list_filter = ('activo', 'fecha_registro')
    search_fields = ('nombre', 'nit', 'contacto_principal', 'email')
    list_per_page = 50
    ordering = ('-fecha_registro',)
    
    fieldsets = (
        ('Información del Cliente', {
            'fields': ('nombre', 'nit', 'contacto_principal', 'email', 'telefono')
        }),
        ('Estado', {
            'fields': ('activo', 'notas_internas')
        }),
    )
    
    def estudiantes_activos(self, obj):
        count = obj.total_estudiantes()
        if count > 0:
            return format_html('<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    estudiantes_activos.short_description = "👥 Estudiantes"
    
    def cursos_asignados(self, obj):
        count = obj.total_cursos()
        if count > 0:
            return format_html('<span style="background:#2196f3;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    cursos_asignados.short_description = "📚 Cursos"


# ========== TEMA DE CAMPAÑA ==========
@admin.register(TemaCampana)
class TemaCampanaAdmin(admin.ModelAdmin):
    """Gestión de temas para organizar plantillas y campañas"""
    list_display = ('nombre_con_emoji', 'descripcion_corta', 'total_plantillas', 'total_campanas', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'descripcion')
    list_per_page = 50
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'emoji', 'activo')
        }),
        ('Detalles', {
            'fields': ('descripcion',)
        }),
    )
    
    def nombre_con_emoji(self, obj):
        return str(obj)
    nombre_con_emoji.short_description = "Tema"
    
    def descripcion_corta(self, obj):
        if obj.descripcion:
            return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
        return '-'
    descripcion_corta.short_description = "Descripción"
    
    def total_plantillas(self, obj):
        count = obj.plantillas.count()
        if count > 0:
            return format_html('<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    total_plantillas.short_description = "📄 Plantillas"
    
    def total_campanas(self, obj):
        count = obj.campanas.count()
        if count > 0:
            return format_html('<span style="background:#2196f3;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{}</span>', count)
        return format_html('<span style="color:#999;">0</span>')
    total_campanas.short_description = "📢 Campañas"


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    """Gestión de estudiantes/campesinos"""
    list_display = ('nombre', 'telefono_formateado', 'cliente_nombre', 'ver_chat_boton', 'activo', 'fecha_registro', 'total_mensajes')
    list_filter = ('activo', 'cliente', 'fecha_registro')
    search_fields = ('nombre', 'telefono', 'cliente__nombre')
    list_per_page = 50
    ordering = ('-fecha_registro',)
    actions = ['enviar_mensaje_manual', 'exportar_estudiantes_excel', 'exportar_estudiantes_csv']  # ✅ Nuevas acciones
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'telefono', 'cliente', 'activo')
        }),
    )
    
    def telefono_formateado(self, obj):
        """Muestra teléfono con formato WhatsApp"""
        return f"+{obj.telefono}"
    telefono_formateado.short_description = "📱 WhatsApp"
    
    def cliente_nombre(self, obj):
        """Muestra el cliente al que pertenece"""
        if obj.cliente:
            return obj.cliente.nombre
        return format_html('<span style="color:#999;">Sin cliente</span>')
    cliente_nombre.short_description = "🏢 Cliente"
    
    def ver_chat_boton(self, obj):
        """Botón para ver conversación completa del estudiante"""
        count = WhatsappLog.objects.filter(
            models.Q(telefono=obj.telefono) | 
            models.Q(estudiante=obj)
        ).count()
        if count > 0:
            url = f'/admin/conversaciones/?estudiante={obj.id}'
            return format_html(
                '<a href="{}" class="button" style="background:#25d366;color:white;padding:5px 12px;border-radius:4px;text-decoration:none;">💬 Ver Chat ({})</a>',
                url, count
            )
        return format_html('<span style="color:#999;">Sin mensajes</span>')
    ver_chat_boton.short_description = "Conversación"
    
    def total_mensajes(self, obj):
        """Cuenta cuántos mensajes ha enviado el estudiante"""
        count = WhatsappLog.objects.filter(telefono=obj.telefono).count()
        return format_html(
            '<span style="background:#e3f2fd;padding:4px 8px;border-radius:4px;">{} mensajes</span>',
            count
        )
    total_mensajes.short_description = "💬 Total"
    
    # ✅ Acción para enviar mensaje manual de prueba
    def enviar_mensaje_manual(self, request, queryset):
        """Permite enviar un mensaje de prueba a los estudiantes seleccionados"""
        if 'aplicar' in request.POST:
            # El usuario confirmó el envío
            mensaje = request.POST.get('mensaje')
            if not mensaje:
                self.message_user(request, "⚠️ Debes escribir un mensaje", level=messages.ERROR)
                return
            
            enviados = 0
            errores = 0
            for estudiante in queryset:
                try:
                    telefono = estudiante.telefono
                    if not telefono.startswith('whatsapp:'):
                        telefono = f'whatsapp:{telefono}'
                    
                    # Enviar con Twilio
                    resultado = enviar_whatsapp_twilio(
                        telefono=telefono,
                        texto=mensaje,
                        mensaje_id_referencia=None
                    )
                    
                    if resultado.get('success'):
                        # Registrar en log
                        WhatsappLog.objects.create(
                            telefono=estudiante.telefono,
                            mensaje=mensaje,
                            mensaje_id=resultado.get('mensaje_id'),
                            tipo='SENT',
                            estado='sent'
                        )
                        enviados += 1
                        logger.info(f"✅ Mensaje manual enviado a {estudiante.nombre} ({estudiante.telefono})")
                    else:
                        errores += 1
                        logger.error(f"❌ Error al enviar a {estudiante.telefono}: {resultado.get('error')}")
                
                except Exception as e:
                    errores += 1
                    logger.error(f"❌ Excepción al enviar a {estudiante.telefono}: {str(e)}")
            
            if enviados > 0:
                self.message_user(request, f"✅ Mensaje enviado exitosamente a {enviados} estudiante(s)", level=messages.SUCCESS)
            if errores > 0:
                self.message_user(request, f"⚠️ Hubo {errores} error(es) al enviar", level=messages.WARNING)
            
            return redirect(request.get_full_path())
        
        # Mostrar formulario de confirmación
        return render(request, 'admin/enviar_mensaje_manual.html', {
            'estudiantes': queryset,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })
    
    enviar_mensaje_manual.short_description = "📤 Enviar mensaje de prueba"
    
    @admin.action(description='📊 Exportar estudiantes a Excel')
    def exportar_estudiantes_excel(self, request, queryset):
        """Exporta estudiantes seleccionados a archivo Excel"""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from datetime import datetime
        
        # Crear workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Estudiantes"
        
        # Encabezados
        headers = ['ID', 'Nombre', 'Teléfono', 'Activo', 'Fecha Registro', 'Total Mensajes', 'Cursos Inscritos']
        ws.append(headers)
        
        # Estilo de encabezados
        header_fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Datos
        for estudiante in queryset:
            mensajes_count = WhatsappLog.objects.filter(telefono=estudiante.telefono).count()
            cursos_count = ProgresoEstudiante.objects.filter(estudiante=estudiante).count()
            
            ws.append([
                estudiante.id,
                estudiante.nombre,
                f"+{estudiante.telefono}",
                "Sí" if estudiante.activo else "No",
                estudiante.fecha_registro.strftime('%Y-%m-%d %H:%M'),
                mensajes_count,
                cursos_count
            ])
        
        # Ajustar anchos
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Crear respuesta HTTP
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'estudiantes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        wb.save(response)
        return response
    
    @admin.action(description='📄 Exportar estudiantes a CSV')
    def exportar_estudiantes_csv(self, request, queryset):
        """Exporta estudiantes seleccionados a archivo CSV"""
        import csv
        from datetime import datetime
        
        response = HttpResponse(content_type='text/csv')
        filename = f'estudiantes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Nombre', 'Teléfono', 'Activo', 'Fecha Registro', 'Total Mensajes', 'Cursos Inscritos'])
        
        for estudiante in queryset:
            mensajes_count = WhatsappLog.objects.filter(telefono=estudiante.telefono).count()
            cursos_count = ProgresoEstudiante.objects.filter(estudiante=estudiante).count()
            
            writer.writerow([
                estudiante.id,
                estudiante.nombre,
                f"+{estudiante.telefono}",
                "Sí" if estudiante.activo else "No",
                estudiante.fecha_registro.strftime('%Y-%m-%d %H:%M'),
                mensajes_count,
                cursos_count
            ])
        
        return response


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    """Gestión de plantillas de mensajes mejorada con vista previa y estadísticas"""
    list_display = ('nombre_interno', 'categoria_emoji', 'temas_badge', 'meta_status_badge', 'vista_previa', 'activa', 'veces_usada', 'fecha_modificacion')
    list_filter = ('categoria', 'temas', 'activa', 'meta_template_status', 'fecha_creacion')
    search_fields = ('nombre_interno', 'cuerpo_mensaje', 'meta_template_name')
    actions = ['enviar_plantilla_directa', 'duplicar_plantilla', 'activar_plantillas', 'desactivar_plantillas', 'enviar_a_meta_accion']
    readonly_fields = ('veces_usada', 'fecha_creacion', 'fecha_modificacion', 'preview_personalizado', 'meta_template_id', 'meta_template_status', 'meta_template_name')
    filter_horizontal = ('temas',)
    
    fieldsets = (
        ('✏️ Información de la Plantilla', {
            'fields': ('nombre_interno', 'categoria', 'temas', 'activa'),
            'description': 'Dale un nombre descriptivo a tu plantilla, categoría y temas relacionados'
        }),
        ('📝 Contenido del Mensaje', {
            'fields': ('cuerpo_mensaje',),
            'description': '<strong>Variables disponibles:</strong> {nombre} {telefono} {curso}<br>'
                          '<strong>Ejemplo:</strong> "Hola {nombre}, te damos la bienvenida al curso {curso}"'
        }),
        ('� Estado en Meta WhatsApp', {
            'fields': ('enviada_a_meta', 'meta_template_id', 'meta_template_status', 'meta_template_name'),
            'classes': ('collapse',),
            'description': 'Información sobre el estado de la plantilla en Meta WhatsApp Business'
        }),
        ('�📊 Estadísticas y Vista Previa', {
            'fields': ('preview_personalizado', 'veces_usada', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )
    
    def temas_badge(self, obj):
        """Muestra temas asociados con badges"""
        temas = obj.temas.all()
        if not temas:
            return format_html('<span style="color:#999;">Sin temas</span>')
        
        badges = []
        for tema in temas:
            badges.append(f'<span style="background:#e3f2fd;color:#1976d2;padding:3px 10px;border-radius:12px;margin:2px;display:inline-block;">{tema}</span>')
        return format_html(''.join(badges))
    temas_badge.short_description = "🏷️ Temas"
    
    def meta_status_badge(self, obj):
        """Muestra estado de aprobación en Meta"""
        if not obj.enviada_a_meta:
            return format_html('<span style="background:#f5f5f5;color:#666;padding:4px 10px;border-radius:12px;font-size:11px;">📝 No enviada</span>')
        
        status_colors = {
            'PENDING': ('#fff3e0', '#f57c00', '⏳'),
            'APPROVED': ('#e8f5e9', '#2e7d32', '✅'),
            'REJECTED': ('#ffebee', '#c62828', '❌'),
            'DISABLED': ('#f5f5f5', '#666', '🚫'),
        }
        
        bg, color, emoji = status_colors.get(obj.meta_template_status, ('#f5f5f5', '#666', '❓'))
        status_text = obj.get_meta_template_status_display() if obj.meta_template_status else 'Desconocido'
        
        return format_html(
            '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-size:11px;font-weight:500;">{} {}</span>',
            bg, color, emoji, status_text
        )
    meta_status_badge.short_description = "📱 Estado Meta"
    
    def categoria_emoji(self, obj):
        """Muestra categoría con emoji"""
        return obj.get_categoria_display()
    categoria_emoji.short_description = "📂 Categoría"
    
    def vista_previa(self, obj):
        """Muestra preview del mensaje"""
        preview = obj.vista_previa()
        return format_html('<span style="color:#666;font-style:italic;">{}</span>', preview)
    vista_previa.short_description = "📄 Vista Previa"
    
    def preview_personalizado(self, obj):
        """Muestra cómo se vería el mensaje personalizado"""
        ejemplo = obj.cuerpo_mensaje.replace('{nombre}', 'Juan Pérez')
        ejemplo = ejemplo.replace('{telefono}', '+573001234567')
        ejemplo = ejemplo.replace('{curso}', 'Cultivo de Aguacate Hass')
        return format_html(
            '<div style="background:#f5f5f5;padding:15px;border-left:4px solid #4CAF50;border-radius:4px;">'
            '<strong>📱 Vista Previa Personalizada:</strong><br><br>{}</div>',
            ejemplo
        )
    preview_personalizado.short_description = "Vista Previa con Variables"
    
    @admin.action(description='📄 Duplicar plantilla(s) seleccionada(s)')
    def duplicar_plantilla(self, request, queryset):
        """Duplica plantillas seleccionadas"""
        duplicadas = 0
        for plantilla in queryset:
            plantilla.pk = None
            plantilla.nombre_interno = f"{plantilla.nombre_interno} (Copia)"
            plantilla.veces_usada = 0
            plantilla.save()
            duplicadas += 1
        self.message_user(request, f"✅ {duplicadas} plantilla(s) duplicada(s)", level=messages.SUCCESS)
    
    @admin.action(description='✅ Activar plantilla(s) seleccionada(s)')
    def activar_plantillas(self, request, queryset):
        """Activa plantillas seleccionadas"""
        actualizadas = queryset.update(activa=True)
        self.message_user(request, f"✅ {actualizadas} plantilla(s) activada(s)", level=messages.SUCCESS)
    
    @admin.action(description='❌ Desactivar plantilla(s) seleccionada(s)')
    def desactivar_plantillas(self, request, queryset):
        """Desactiva plantillas seleccionadas"""
        actualizadas = queryset.update(activa=False)
        self.message_user(request, f"⚠️ {actualizadas} plantilla(s) desactivada(s)", level=messages.WARNING)
    
    @admin.action(description='📱 Enviar a Meta para aprobación')
    def enviar_a_meta_accion(self, request, queryset):
        """Envía plantillas a Meta WhatsApp Business para aprobación"""
        from .meta_templates import enviar_plantilla_a_meta
        
        enviadas = 0
        errores = 0
        
        for plantilla in queryset:
            try:
                # Verificar si ya fue enviada
                if plantilla.enviada_a_meta and plantilla.meta_template_status == 'APPROVED':
                    self.message_user(
                        request,
                        f"⚠️ '{plantilla.nombre_interno}' ya está aprobada en Meta",
                        level=messages.WARNING
                    )
                    continue
                
                # Enviar a Meta
                resultado = enviar_plantilla_a_meta(
                    nombre_plantilla=plantilla.nombre_interno,
                    contenido=plantilla.cuerpo_mensaje,
                    categoria=plantilla.categoria if plantilla.categoria in ['MARKETING', 'UTILITY'] else 'MARKETING',
                    idioma='es'
                )
                
                if resultado['success']:
                    # Actualizar plantilla con información de Meta
                    plantilla.enviada_a_meta = True
                    plantilla.meta_template_id = resultado['template_id']
                    plantilla.meta_template_status = resultado['status']
                    plantilla.meta_template_name = resultado['nombre_meta']
                    plantilla.save()
                    
                    enviadas += 1
                    self.message_user(
                        request,
                        f"✅ '{plantilla.nombre_interno}' enviada a Meta. ID: {resultado['template_id']}",
                        level=messages.SUCCESS
                    )
                else:
                    errores += 1
                    self.message_user(
                        request,
                        f"❌ Error con '{plantilla.nombre_interno}': {resultado['message']}",
                        level=messages.ERROR
                    )
            
            except Exception as e:
                errores += 1
                logger.error(f"Error enviando plantilla a Meta: {str(e)}")
                self.message_user(
                    request,
                    f"❌ Excepción con '{plantilla.nombre_interno}': {str(e)}",
                    level=messages.ERROR
                )
        
        # Resumen final
        if enviadas > 0:
            self.message_user(
                request,
                f"🎉 {enviadas} plantilla(s) enviada(s) a Meta para revisión",
                level=messages.SUCCESS
            )
        if errores > 0:
            self.message_user(
                request,
                f"⚠️ {errores} plantilla(s) con errores. Verifica las credenciales de Meta.",
                level=messages.WARNING
            )
    
    @admin.action(description='📤 Enviar plantilla a estudiantes')
    def enviar_plantilla_directa(self, request, queryset):
        """Permite enviar una plantilla directamente a estudiantes seleccionados"""
        
        if queryset.count() > 1:
            self.message_user(request, "⚠️ Solo puedes enviar una plantilla a la vez", level=messages.WARNING)
            return
        
        plantilla = queryset.first()
        
        # Si es POST con confirmación
        if 'aplicar' in request.POST:
            # Obtener estudiantes seleccionados
            estudiantes_ids = request.POST.getlist('estudiantes_seleccionados')
            if not estudiantes_ids:
                self.message_user(request, "⚠️ Debes seleccionar al menos un estudiante", level=messages.ERROR)
            else:
                enviados = 0
                errores = 0
                
                for est_id in estudiantes_ids:
                    try:
                        estudiante = Estudiante.objects.get(id=est_id)
                        
                        # Personalizar mensaje con nombre
                        mensaje = plantilla.cuerpo_mensaje.replace('{nombre}', estudiante.nombre)
                        mensaje = mensaje.replace('{estudiante}', estudiante.nombre)
                        
                        telefono = estudiante.telefono
                        if not telefono.startswith('whatsapp:'):
                            telefono = f'whatsapp:{telefono}'
                        
                        resultado = enviar_whatsapp_twilio(
                            telefono=telefono,
                            texto=mensaje,
                            mensaje_id_referencia=None
                        )
                        
                        if resultado.get('success'):
                            enviados += 1
                            # Registrar en WhatsappLog
                            WhatsappLog.objects.create(
                                telefono=estudiante.telefono,
                                mensaje=mensaje,
                                mensaje_id=resultado.get('mensaje_id'),
                                tipo='SENT',
                                estado='SENT'
                            )
                            logger.info(f"✅ Plantilla '{plantilla.nombre_interno}' enviada a {estudiante.nombre}")
                        else:
                            errores += 1
                            logger.error(f"❌ Error al enviar plantilla a {estudiante.telefono}")
                    
                    except Exception as e:
                        errores += 1
                        logger.error(f"❌ Excepción al enviar: {str(e)}")
                
                if enviados > 0:
                    self.message_user(request, f"✅ Plantilla enviada a {enviados} estudiante(s)", level=messages.SUCCESS)
                if errores > 0:
                    self.message_user(request, f"⚠️ Hubo {errores} error(es)", level=messages.WARNING)
                
                # Redirigir a la lista de plantillas después de enviar
                from django.urls import reverse
                return redirect(reverse('admin:core_plantilla_changelist'))
        
        # Mostrar formulario de selección de estudiantes
        estudiantes = Estudiante.objects.filter(activo=True).order_by('nombre')
        
        return render(request, 'admin/enviar_plantilla_directa.html', {
            'plantilla': plantilla,
            'estudiantes': estudiantes,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })


@admin.register(Campana)
class CampanaAdmin(admin.ModelAdmin):
    """Gestión de campañas masivas"""
    list_display = ('nombre', 'cliente_nombre', 'tema_badge', 'estado_visual', 'conteo_destinatarios', 'fecha_creacion')
    list_filter = ('ejecutada', 'cliente', 'tema', 'fecha_creacion')
    search_fields = ('nombre', 'cliente__nombre')
    filter_horizontal = ('destinatarios',)
    actions = ['enviar_campana_accion']
    
    fieldsets = (
        ('📝 Datos Básicos', {
            'fields': ('nombre', 'cliente', 'tema', 'plantilla', 'linea_origen'),
            'description': '💡 <strong>Tip:</strong> Selecciona el tema primero para filtrar plantillas relacionadas. Los mensajes se envían por WhatsApp.'
        }),
        ('📂 Importar (Opcional)', {
            'fields': ('archivo_excel',),
            'description': 'Sube un Excel con columnas A (Nombre) y B (Teléfono).'
        }),
        ('👥 Audiencia', {
            'fields': ('destinatarios',)
        }),
    )
    
    def cliente_nombre(self, obj):
        """Muestra el cliente de la campaña"""
        if obj.cliente:
            return obj.cliente.nombre
        return format_html('<span style="color:#999;font-style:italic;">Sin cliente</span>')
    cliente_nombre.short_description = "🏢 Cliente"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtrar plantillas según el tema seleccionado en la campaña"""
        if db_field.name == "plantilla":
            # Intentar obtener el tema desde POST (cuando está guardando)
            tema_id = request.POST.get('tema') or request.GET.get('tema')
            
            if tema_id:
                try:
                    tema = TemaCampana.objects.get(id=tema_id)
                    kwargs["queryset"] = Plantilla.objects.filter(temas=tema, activa=True)
                except TemaCampana.DoesNotExist:
                    kwargs["queryset"] = Plantilla.objects.filter(activa=True)
            else:
                # Si no hay tema, mostrar todas las plantillas activas
                kwargs["queryset"] = Plantilla.objects.filter(activa=True)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def tema_badge(self, obj):
        """Muestra el tema con badge"""
        if obj.tema:
            return format_html(
                '<span style="background:#e3f2fd;color:#1976d2;padding:6px 12px;border-radius:12px;font-weight:bold;">{}</span>',
                str(obj.tema)
            )
        return format_html('<span style="color:#999;">Sin tema</span>')
    tema_badge.short_description = "🏷️ Tema"
    
    @admin.action(description='🚀 Ejecutar Campaña (Enviar Mensajes)')
    def enviar_campana_accion(self, request, queryset):
        """Ejecuta el envío de campañas masivas por WhatsApp"""
        from .services import ejecutar_campana_servicio
        
        for campana in queryset:
            if campana.ejecutada:
                self.message_user(
                    request, 
                    f"⚠️ '{campana.nombre}' ya fue enviada antes.", 
                    level=messages.WARNING
                )
                continue
            
            # Validar que tenga destinatarios
            if campana.destinatarios.count() == 0:
                self.message_user(
                    request,
                    f"⚠️ '{campana.nombre}' no tiene destinatarios seleccionados.",
                    level=messages.WARNING
                )
                continue
            
            try:
                res = ejecutar_campana_servicio(campana)
                self.message_user(
                    request, 
                    f"✅ '{campana.nombre}': {res['exitosos']} enviados, {res['fallidos']} errores de {res['total']} total.", 
                    level=messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ Error ejecutando '{campana.nombre}': {str(e)}",
                    level=messages.ERROR
                )
    
    enviar_campana_accion.short_description = "📤 Ejecutar campañas seleccionadas (envío real por WhatsApp)"
    
    def estado_visual(self, obj):
        if obj.ejecutada:
            return format_html('<span style="color: green;">✅ Ejecutada</span>')
        return format_html('<span style="color: orange;">⏳ Pendiente</span>')
    estado_visual.short_description = "Estado"
    
    def conteo_destinatarios(self, obj):
        return obj.destinatarios.count()
    conteo_destinatarios.short_description = "# Destinatarios"


@admin.register(EnvioLog)
class EnvioLogAdmin(admin.ModelAdmin):
    """Historial de envíos de campañas"""
    list_display = ('id', 'estudiante_nombre', 'estado_color', 'fecha_envio', 'nombre_plantilla')
    list_filter = ('estado', 'fecha_envio', 'campana__nombre')
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'campana__nombre')
    readonly_fields = ('campana', 'estudiante', 'estado', 'respuesta_api', 'fecha_envio')
    
    def estudiante_nombre(self, obj):
        return f"{obj.estudiante.nombre} ({obj.estudiante.telefono})"
    estudiante_nombre.short_description = "Receptor"
    
    def nombre_plantilla(self, obj):
        return obj.campana.plantilla.nombre_interno
    nombre_plantilla.short_description = "Plantilla"
    
    def estado_color(self, obj):
        if obj.estado == 'ENVIADO':
            return format_html('<b style="color:green;">ENVIADO</b>')
        elif obj.estado == 'FALLIDO':
            return format_html('<b style="color:red;">FALLIDO</b>')
        return obj.estado
    estado_color.short_description = "Estado"


@admin.register(WhatsappLog)
class WhatsappLogAdmin(admin.ModelAdmin):
    """Registro de todas las conversaciones del chatbot"""
    list_display = ('fecha', 'estudiante_nombre', 'telefono_corto', 'tipo_badge', 'mensaje_preview', 'estado_badge', 'actividad_badge')
    list_filter = ('tipo', 'estado', 'fecha', 'estudiante__activo')
    search_fields = ('telefono', 'mensaje', 'mensaje_id', 'estudiante__nombre')  # ✅ Búsqueda por nombre
    date_hierarchy = 'fecha'
    list_per_page = 100
    ordering = ('-fecha',)
    readonly_fields = ('fecha', 'mensaje_id', 'estudiante')
    actions = ['exportar_conversaciones_excel', 'exportar_conversaciones_csv', 'ver_conversacion_completa']  # ✅ Nueva acción
    autocomplete_fields = ['estudiante']  # ✅ Autocompletar estudiante
    
    fieldsets = (
        ('Información del Mensaje', {
            'fields': ('telefono', 'estudiante', 'tipo', 'mensaje', 'estado')
        }),
        ('Metadatos', {
            'fields': ('mensaje_id', 'fecha'),
            'classes': ('collapse',)
        }),
    )
    
    def estudiante_nombre(self, obj):
        """Muestra nombre del estudiante si está asignado"""
        if obj.estudiante:
            return obj.estudiante.nombre
        return format_html('<span style="color:#999;font-style:italic;">Sin asignar</span>')
    estudiante_nombre.short_description = "👤 Estudiante"
    estudiante_nombre.admin_order_field = 'estudiante__nombre'
    
    def telefono_corto(self, obj):
        """Muestra solo los últimos 4 dígitos"""
        return f"...{obj.telefono[-4:]}"
    telefono_corto.short_description = "📱"
    
    def tipo_badge(self, obj):
        """Badge visual para tipo de mensaje"""
        if obj.tipo == 'INCOMING':
            return format_html(
                '<span style="background:#4caf50;color:white;padding:3px 8px;border-radius:12px;font-size:11px;">⬇️ RECIBIDO</span>'
            )
        return format_html(
            '<span style="background:#2196f3;color:white;padding:3px 8px;border-radius:12px;font-size:11px;">⬆️ ENVIADO</span>'
        )
    tipo_badge.short_description = "Tipo"
    
    def mensaje_preview(self, obj):
        """Muestra preview del mensaje"""
        texto = obj.mensaje[:60] + "..." if len(obj.mensaje) > 60 else obj.mensaje
        return texto
    mensaje_preview.short_description = "💬 Mensaje"
    
    def estado_badge(self, obj):
        """Badge visual para estado"""
        colores = {
            'RECIBIDO': '#4caf50',
            'SENT': '#2196f3',
            'PENDING': '#ff9800',
            'ERROR': '#f44336'
        }
        color = colores.get(obj.estado, '#999')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.estado
        )
    estado_badge.short_description = "Estado"
    
    def actividad_badge(self, obj):
        """Badge de actividad del mensaje"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        delta = now - obj.fecha
        
        if delta.total_seconds() < 86400:  # 24 horas
            return format_html('<span style="color:#f44336;font-weight:bold;">🔴 Nueva</span>')
        elif delta.days < 7:
            return format_html('<span style="color:#4caf50;font-weight:bold;">🟢 Activa</span>')
        elif delta.days < 30:
            return format_html('<span style="color:#ff9800;">🟡 Reciente</span>')
        else:
            return format_html('<span style="color:#999;">⚪ Antigua</span>')
    actividad_badge.short_description = "⏰ Actividad"
    
    def get_queryset(self, request):
        """Ordena por fecha descendente por defecto"""
        qs = super().get_queryset(request)
        return qs.order_by('-fecha')
    
    @admin.action(description='📊 Exportar conversaciones a Excel')
    def exportar_conversaciones_excel(self, request, queryset):
        """Exporta conversaciones seleccionadas a archivo Excel"""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from datetime import datetime
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Conversaciones"
        
        # Encabezados
        headers = ['Fecha', 'Teléfono', 'Tipo', 'Mensaje', 'Estado', 'ID Mensaje']
        ws.append(headers)
        
        # Estilo
        header_fill = PatternFill(start_color="2196F3", end_color="2196F3", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        # Datos
        for log in queryset.order_by('fecha'):
            ws.append([
                log.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                log.telefono,
                log.tipo,
                log.mensaje[:500],  # Limitar tamaño
                log.estado,
                log.mensaje_id or 'N/A'
            ])
        
        # Ajustar anchos
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 12
        ws.column_dimensions['D'].width = 60
        ws.column_dimensions['E'].width = 12
        ws.column_dimensions['F'].width = 35
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'conversaciones_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        wb.save(response)
        return response
    
    @admin.action(description='📄 Exportar conversaciones a CSV')
    def exportar_conversaciones_csv(self, request, queryset):
        """Exporta conversaciones seleccionadas a archivo CSV"""
        import csv
        from datetime import datetime
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f'conversaciones_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Fecha', 'Teléfono', 'Tipo', 'Mensaje', 'Estado', 'ID Mensaje'])
        
        for log in queryset.order_by('fecha'):
            writer.writerow([
                log.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                log.telefono,
                log.tipo,
                log.mensaje[:500],
                log.estado,
                log.mensaje_id or 'N/A'
            ])
        
        return response
    
    @admin.action(description='💬 Ver conversación completa')
    def ver_conversacion_completa(self, request, queryset):
        """Redirige a la vista de conversaciones para el estudiante del primer mensaje seleccionado"""
        from django.shortcuts import redirect
        
        if queryset.count() == 0:
            self.message_user(request, "No hay mensajes seleccionados", level=messages.WARNING)
            return
        
        # Obtener el primer mensaje
        primer_mensaje = queryset.first()
        
        # Intentar obtener el estudiante
        if primer_mensaje.estudiante:
            estudiante_id = primer_mensaje.estudiante.id
        else:
            # Buscar estudiante por teléfono
            from .models import Estudiante
            telefono_limpio = primer_mensaje.telefono.replace('+', '').replace(' ', '').replace('whatsapp:', '')
            try:
                estudiante = Estudiante.objects.get(telefono=telefono_limpio)
                estudiante_id = estudiante.id
            except Estudiante.DoesNotExist:
                self.message_user(
                    request, 
                    f"No se encontró estudiante con el teléfono {primer_mensaje.telefono}",
                    level=messages.ERROR
                )
                return
        
        # Redirigir a la vista de conversaciones
        return redirect(f'/admin/conversaciones/?estudiante={estudiante_id}')
        import csv
        from datetime import datetime
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f'conversaciones_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Fecha', 'Teléfono', 'Tipo', 'Mensaje', 'Estado', 'ID Mensaje'])
        
        for log in queryset.order_by('fecha'):
            writer.writerow([
                log.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                log.telefono,
                log.tipo,
                log.mensaje[:500],
                log.estado,
                log.mensaje_id or 'N/A'
            ])
        
        return response


# Personalizar el admin site
admin.site.site_header = "Eki - Chatbot Agro 🌱"


# ==========================================
# SISTEMA EDUCATIVO - ADMINISTRACIÓN
# ==========================================

class ModuloInline(admin.TabularInline):
    """Módulos dentro del curso"""
    model = Modulo
    extra = 1
    fields = ('numero', 'titulo', 'descripcion', 'duracion_dias')
    ordering = ['numero']


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    """Administración de cursos"""
    list_display = ('emoji_nombre', 'cliente_nombre', 'total_modulos_display', 'duracion_semanas', 'activo', 'orden')
    list_filter = ('activo', 'cliente')
    search_fields = ('nombre', 'descripcion', 'cliente__nombre')
    list_editable = ('activo', 'orden')
    inlines = [ModuloInline]
    
    fieldsets = (
        ('📚 Información del Curso', {
            'fields': ('nombre', 'emoji', 'descripcion', 'cliente', 'duracion_semanas')
        }),
        ('⚙️ Configuración', {
            'fields': ('activo', 'orden')
        }),
    )
    
    def emoji_nombre(self, obj):
        return f"{obj.emoji} {obj.nombre}"
    emoji_nombre.short_description = "Curso"
    
    def cliente_nombre(self, obj):
        """Muestra si es curso específico de un cliente"""
        if obj.cliente:
            return obj.cliente.nombre
        return format_html('<span style="color:#999;font-style:italic;">General (Eki)</span>')
    cliente_nombre.short_description = "🏢 Cliente"
    
    def total_modulos_display(self, obj):
        count = obj.modulos.count()
        return format_html(
            '<span style="background:#e3f2fd;padding:4px 8px;border-radius:4px;">{} módulos</span>',
            count
        )
    total_modulos_display.short_description = "Módulos"


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    """Administración de módulos"""
    list_display = ('numero_titulo', 'curso', 'duracion_dias', 'contenido_preview')
    list_filter = ('curso',)
    search_fields = ('titulo', 'descripcion', 'contenido')
    list_per_page = 50
    ordering = ['curso', 'numero']
    
    fieldsets = (
        ('📖 Información del Módulo', {
            'fields': ('curso', 'numero', 'titulo', 'descripcion')
        }),
        ('📝 Contenido Educativo', {
            'fields': ('contenido',),
            'description': 'Escribe el contenido completo de la lección (se enviará por WhatsApp)'
        }),
        ('🎥 Multimedia', {
            'fields': ('video_archivo', 'video_resolucion', 'video_url', 'imagen_portada_url', 'archivo_pdf_url'),
            'description': 'Video: Sube MP4 360p para campo. URLs: YouTube/Vimeo o PDFs complementarios',
            'classes': ('collapse',)
        }),
        ('⏱️ Configuración', {
            'fields': ('duracion_dias',)
        }),
    )
    
    def numero_titulo(self, obj):
        return f"Módulo {obj.numero}: {obj.titulo}"
    numero_titulo.short_description = "Módulo"
    
    def contenido_preview(self, obj):
        preview = obj.contenido[:60] + "..." if len(obj.contenido) > 60 else obj.contenido
        return format_html('<span style="color:#666;font-style:italic;">{}</span>', preview)
    contenido_preview.short_description = "Vista Previa"


class PreguntaExamenInline(admin.TabularInline):
    """Preguntas dentro del examen"""
    model = PreguntaExamen
    extra = 1
    fields = ('numero', 'pregunta', 'respuesta_correcta', 'puntos')
    ordering = ['numero']


@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    """Administración de exámenes"""
    list_display = ('curso_nombre', 'total_preguntas_display', 'puntaje_minimo')
    list_filter = ('curso',)
    search_fields = ('curso__nombre', 'instrucciones')
    inlines = [PreguntaExamenInline]
    
    fieldsets = (
        ('📝 Configuración del Examen', {
            'fields': ('curso', 'instrucciones', 'puntaje_minimo')
        }),
    )
    
    def curso_nombre(self, obj):
        return f"{obj.curso.emoji} {obj.curso.nombre}"
    curso_nombre.short_description = "Curso"
    
    def total_preguntas_display(self, obj):
        count = obj.preguntas.count()
        return format_html(
            '<span style="background:#fff3cd;padding:4px 8px;border-radius:4px;">{} preguntas</span>',
            count
        )
    total_preguntas_display.short_description = "Preguntas"


@admin.register(PreguntaExamen)
class PreguntaExamenAdmin(admin.ModelAdmin):
    """Administración de preguntas de examen"""
    list_display = ('numero_pregunta', 'examen', 'puntos', 'pregunta_preview')
    list_filter = ('examen__curso',)
    search_fields = ('pregunta', 'respuesta_correcta')
    ordering = ['examen', 'numero']
    
    fieldsets = (
        ('❓ Pregunta', {
            'fields': ('examen', 'numero', 'pregunta')
        }),
        ('✅ Respuesta', {
            'fields': ('respuesta_correcta', 'puntos'),
            'description': 'Palabras clave separadas por comas (la IA evaluará si están presentes)'
        }),
    )
    
    def numero_pregunta(self, obj):
        return f"Pregunta {obj.numero}"
    numero_pregunta.short_description = "N°"
    
    def pregunta_preview(self, obj):
        preview = obj.pregunta[:80] + "..." if len(obj.pregunta) > 80 else obj.pregunta
        return preview
    pregunta_preview.short_description = "Pregunta"


@admin.register(ProgresoEstudiante)
class ProgresoEstudianteAdmin(admin.ModelAdmin):
    """Seguimiento del progreso de estudiantes"""
    list_display = ('estudiante', 'curso', 'porcentaje_badge', 'modulo_actual', 'completado_badge', 'fecha_inicio')
    list_filter = ('completado', 'curso', 'fecha_inicio')
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'curso__nombre')
    readonly_fields = ('fecha_inicio', 'porcentaje_avance')
    list_per_page = 50
    ordering = ('-fecha_inicio',)
    actions = ['exportar_progreso_excel', 'exportar_progreso_csv']  # ✅ Nuevas acciones
    
    fieldsets = (
        ('👤 Estudiante y Curso', {
            'fields': ('estudiante', 'curso')
        }),
        ('📊 Progreso', {
            'fields': ('modulo_actual', 'completado', 'porcentaje_avance')
        }),
        ('📅 Fechas', {
            'fields': ('fecha_inicio', 'fecha_completado')
        }),
    )
    
    def porcentaje_badge(self, obj):
        porcentaje = obj.porcentaje_avance()
        if porcentaje >= 80:
            color = '#4caf50'
        elif porcentaje >= 50:
            color = '#ff9800'
        else:
            color = '#f44336'
        return format_html(
            '<span style="background:{};color:white;padding:4px 12px;border-radius:12px;font-weight:bold;"{}%</span>',
            color, porcentaje
        )
    porcentaje_badge.short_description = "Avance"
    
    def completado_badge(self, obj):
        if obj.completado:
            return format_html('<span style="color:green;">✅ Completo</span>')
        return format_html('<span style="color:orange;">⏳ En progreso</span>')
    completado_badge.short_description = "Estado"
    
    @admin.action(description='📊 Exportar progreso a Excel')
    def exportar_progreso_excel(self, request, queryset):
        """Exporta el progreso de estudiantes a Excel"""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from datetime import datetime
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Progreso Estudiantes"
        
        # Encabezados
        headers = ['Estudiante', 'Teléfono', 'Curso', 'Módulo Actual', 'Avance %', 'Completado', 'Fecha Inicio', 'Fecha Completado']
        ws.append(headers)
        
        # Estilo
        header_fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        # Datos
        for progreso in queryset:
            ws.append([
                progreso.estudiante.nombre,
                f"+{progreso.estudiante.telefono}",
                progreso.curso.nombre,
                progreso.modulo_actual or 'No iniciado',
                progreso.porcentaje_avance(),
                "Sí" if progreso.completado else "No",
                progreso.fecha_inicio.strftime('%Y-%m-%d %H:%M'),
                progreso.fecha_completado.strftime('%Y-%m-%d %H:%M') if progreso.fecha_completado else 'N/A'
            ])
        
        # Ajustar anchos
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 18
        ws.column_dimensions['C'].width = 30
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 12
        ws.column_dimensions['G'].width = 20
        ws.column_dimensions['H'].width = 20
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'progreso_estudiantes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        wb.save(response)
        return response
    
    @admin.action(description='📄 Exportar progreso a CSV')
    def exportar_progreso_csv(self, request, queryset):
        """Exporta el progreso de estudiantes a CSV"""
        import csv
        from datetime import datetime
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f'progreso_estudiantes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Estudiante', 'Teléfono', 'Curso', 'Módulo Actual', 'Avance %', 'Completado', 'Fecha Inicio', 'Fecha Completado'])
        
        for progreso in queryset:
            writer.writerow([
                progreso.estudiante.nombre,
                f"+{progreso.estudiante.telefono}",
                progreso.curso.nombre,
                progreso.modulo_actual or 'No iniciado',
                progreso.porcentaje_avance(),
                "Sí" if progreso.completado else "No",
                progreso.fecha_inicio.strftime('%Y-%m-%d %H:%M'),
                progreso.fecha_completado.strftime('%Y-%m-%d %H:%M') if progreso.fecha_completado else 'N/A'
            ])
        
        return response


@admin.register(ModuloCompletado)
class ModuloCompletadoAdmin(admin.ModelAdmin):
    """Registro de módulos completados"""
    list_display = ('estudiante_nombre', 'modulo_info', 'fecha_completado')
    list_filter = ('fecha_completado', 'modulo__curso')
    search_fields = ('progreso__estudiante__nombre', 'modulo__titulo')
    readonly_fields = ('fecha_completado',)
    ordering = ('-fecha_completado',)
    
    def estudiante_nombre(self, obj):
        return obj.progreso.estudiante.nombre
    estudiante_nombre.short_description = "Estudiante"
    
    def modulo_info(self, obj):
        return f"{obj.modulo.curso.emoji} {obj.modulo.titulo}"
    modulo_info.short_description = "Módulo"


@admin.register(ResultadoExamen)
class ResultadoExamenAdmin(admin.ModelAdmin):
    """Resultados de exámenes"""
    list_display = ('estudiante', 'examen_info', 'puntaje_badge', 'aprobado_badge', 'fecha_realizado')
    list_filter = ('aprobado', 'examen__curso', 'fecha_realizado')
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'examen__curso__nombre')
    readonly_fields = ('fecha_realizado', 'respuestas', 'feedback')
    ordering = ('-fecha_realizado',)
    
    fieldsets = (
        ('👤 Estudiante y Examen', {
            'fields': ('estudiante', 'examen')
        }),
        ('📊 Resultado', {
            'fields': ('puntaje', 'aprobado')
        }),
        ('📝 Respuestas y Retroalimentación', {
            'fields': ('respuestas', 'feedback'),
            'classes': ('collapse',)
        }),
        ('📅 Fecha', {
            'fields': ('fecha_realizado',)
        }),
    )
    
    def examen_info(self, obj):
        return f"{obj.examen.curso.emoji} {obj.examen.curso.nombre}"
    examen_info.short_description = "Examen"
    
    def puntaje_badge(self, obj):
        if obj.puntaje >= 80:
            color = '#4caf50'
        elif obj.puntaje >= 70:
            color = '#ff9800'
        else:
            color = '#f44336'
        return format_html(
            '<span style="background:{};color:white;padding:6px 12px;border-radius:12px;font-weight:bold;font-size:14px;">{}/100</span>',
            color, obj.puntaje
        )
    puntaje_badge.short_description = "Puntaje"
    
    def aprobado_badge(self, obj):
        if obj.aprobado:
            return format_html('<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;">✅ APROBADO</span>')
        return format_html('<span style="background:#f44336;color:white;padding:4px 12px;border-radius:12px;">❌ REPROBADO</span>')
    aprobado_badge.short_description = "Estado"


# Personalizar el admin site
admin.site.site_header = "Eki - Chatbot Agro 🌱"
admin.site.site_title = "Administración Eki"
admin.site.index_title = "Panel de Control - Chatbot Educativo"


# ==========================================
# PERSONALIZACIÓN DEL INDEX DEL ADMIN
# ==========================================
from django.contrib.admin import AdminSite
from django.urls import reverse
from django.utils.html import format_html

# Sobrescribir el template del index para agregar enlaces personalizados
def index_view(self, request, extra_context=None):
    """Vista personalizada del index del admin con enlaces a conversaciones"""
    extra_context = extra_context or {}
    
    # Agregar enlace a conversaciones en el contexto
    extra_context['conversaciones_url'] = reverse('conversaciones')
    extra_context['dashboard_url'] = reverse('dashboard_metricas')
    
    return AdminSite.index(self, request, extra_context)

# Aplicar la vista personalizada
admin.site.index = index_view.__get__(admin.site, AdminSite)


# ========================================
# 🎮 GAMIFICACIÓN
# ========================================

@admin.register(PerfilGamificacion)
class PerfilGamificacionAdmin(admin.ModelAdmin):
    """Administración de perfiles de gamificación"""
    list_display = ('estudiante_info', 'nivel_display', 'puntos_totales', 'racha_display', 'badges_count', 'posicion_ranking')
    list_filter = ('nivel', 'racha_dias_actual')
    search_fields = ('estudiante__nombre', 'estudiante__telefono')
    readonly_fields = ('puntos_totales', 'nivel', 'experiencia_nivel_actual', 'fecha_creacion', 'fecha_actualizacion', 'posicion_ranking')
    list_per_page = 50
    ordering = ['-puntos_totales']
    
    fieldsets = (
        ('👤 Estudiante', {
            'fields': ('estudiante',)
        }),
        ('🎯 Nivel y Puntos', {
            'fields': ('nivel', 'puntos_totales', 'experiencia_nivel_actual')
        }),
        ('🔥 Rachas', {
            'fields': ('racha_dias_actual', 'racha_dias_maxima', 'ultima_actividad')
        }),
        ('📊 Estadísticas', {
            'fields': ('modulos_completados', 'examenes_aprobados', 'preguntas_respondidas', 'audios_enviados')
        }),
        ('🏆 Ranking', {
            'fields': ('posicion_ranking',)
        }),
    )
    
    def estudiante_info(self, obj):
        return f"{obj.estudiante.nombre}"
    estudiante_info.short_description = "Estudiante"
    
    def nivel_display(self, obj):
        colores = {
            1: '#9e9e9e', 2: '#795548', 3: '#4caf50', 4: '#03a9f4',
            5: '#3f51b5', 6: '#9c27b0', 7: '#e91e63', 8: '#ff5722',
            9: '#ff9800', 10: '#ffc107'
        }
        color = colores.get(obj.nivel, '#000')
        porcentaje = obj.porcentaje_nivel()
        return format_html(
            '<div style="background:{};color:white;padding:8px 16px;border-radius:20px;font-weight:bold;text-align:center;">'
            'Nivel {} <br><small>{}% progreso</small></div>',
            color, obj.nivel, porcentaje
        )
    nivel_display.short_description = "Nivel"
    
    def racha_display(self, obj):
        if obj.racha_dias_actual >= 7:
            color = '#ff5722'
            emoji = '🔥🔥'
        elif obj.racha_dias_actual >= 3:
            color = '#ff9800'
            emoji = '🔥'
        else:
            color = '#9e9e9e'
            emoji = '📅'
        
        return format_html(
            '<span style="background:{};color:white;padding:6px 12px;border-radius:12px;font-weight:bold;">'
            '{} {} días</span>',
            color, emoji, obj.racha_dias_actual
        )
    racha_display.short_description = "Racha Actual"
    
    def badges_count(self, obj):
        count = obj.get_badges().count()
        if count > 0:
            return format_html(
                '<span style="background:#ffc107;color:#000;padding:6px 12px;border-radius:12px;font-weight:bold;">'
                '🏆 {} badges</span>',
                count
            )
        return format_html('<span style="color:#999;">0</span>')
    badges_count.short_description = "Badges"


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    """Administración de badges/insignias"""
    list_display = ('icono_nombre', 'tipo', 'descripcion_corta', 'criterios', 'puntos_bonus', 'total_obtenidos_display', 'activo')
    list_filter = ('tipo', 'activo', 'es_secreto')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('activo',)
    list_per_page = 50
    ordering = ['orden', 'tipo', 'nombre']
    
    fieldsets = (
        ('🏆 Información del Badge', {
            'fields': ('nombre', 'descripcion', 'icono', 'tipo')
        }),
        ('✅ Criterios de Obtención', {
            'fields': ('nivel_requerido', 'valor_requerido', 'curso_requerido', 'puntos_bonus')
        }),
        ('⚙️ Configuración', {
            'fields': ('es_secreto', 'activo', 'orden')
        }),
    )
    
    actions = ['duplicar_badge', 'activar_badges', 'desactivar_badges']
    
    def icono_nombre(self, obj):
        return f"{obj.icono} {obj.nombre}"
    icono_nombre.short_description = "Badge"
    
    def descripcion_corta(self, obj):
        if len(obj.descripcion) > 60:
            return obj.descripcion[:60] + '...'
        return obj.descripcion
    descripcion_corta.short_description = "Descripción"
    
    def criterios(self, obj):
        """Muestra los criterios para obtener el badge"""
        criterios = []
        if obj.nivel_requerido:
            criterios.append(f"Nivel {obj.nivel_requerido}")
        if obj.valor_requerido:
            if obj.tipo == 'RACHA':
                criterios.append(f"{obj.valor_requerido} días de racha")
            elif obj.tipo == 'CURSO':
                criterios.append(f"{obj.valor_requerido} cursos completados")
            else:
                criterios.append(f"Valor: {obj.valor_requerido}")
        if obj.curso_requerido:
            criterios.append(f"Curso: {obj.curso_requerido.nombre}")
        
        if not criterios:
            return format_html('<span style="color:#999;font-style:italic;">Sin criterios</span>')
        
        return format_html('<span style="color:#666;">{}</span>', ' | '.join(criterios))
    criterios.short_description = "Criterios"
    
    def total_obtenidos_display(self, obj):
        count = obj.total_obtenidos()
        if count > 0:
            return format_html(
                '<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{} estudiantes</span>',
                count
            )
        return format_html('<span style="color:#999;">Nadie aún</span>')
    total_obtenidos_display.short_description = "Obtenido por"
    
    def duplicar_badge(self, request, queryset):
        """Duplica badges seleccionados"""
        count = 0
        for badge in queryset:
            badge.pk = None
            badge.nombre = f"{badge.nombre} (Copia)"
            badge.save()
            count += 1
        self.message_user(request, f"{count} badge(s) duplicado(s)")
    duplicar_badge.short_description = "📋 Duplicar badges"
    
    def activar_badges(self, request, queryset):
        count = queryset.update(activo=True)
        self.message_user(request, f"{count} badge(s) activado(s)")
    activar_badges.short_description = "✅ Activar badges"
    
    def desactivar_badges(self, request, queryset):
        count = queryset.update(activo=False)
        self.message_user(request, f"{count} badge(s) desactivado(s)")
    desactivar_badges.short_description = "❌ Desactivar badges"


@admin.register(BadgeEstudiante)
class BadgeEstudianteAdmin(admin.ModelAdmin):
    """Administración de badges obtenidos por estudiantes"""
    list_display = ('estudiante', 'badge_display', 'fecha_obtenido')
    list_filter = ('badge__tipo', 'fecha_obtenido')
    search_fields = ('estudiante__nombre', 'badge__nombre')
    readonly_fields = ('fecha_obtenido',)
    list_per_page = 50
    ordering = ['-fecha_obtenido']
    
    def badge_display(self, obj):
        return f"{obj.badge.icono} {obj.badge.nombre}"
    badge_display.short_description = "Badge"


@admin.register(TransaccionPuntos)
class TransaccionPuntosAdmin(admin.ModelAdmin):
    """Historial de transacciones de puntos"""
    list_display = ('estudiante_nombre', 'puntos_display', 'tipo', 'razon', 'fecha')
    list_filter = ('tipo', 'fecha')
    search_fields = ('perfil__estudiante__nombre', 'razon')
    readonly_fields = ('fecha',)
    list_per_page = 100
    ordering = ['-fecha']
    
    def estudiante_nombre(self, obj):
        return obj.perfil.estudiante.nombre
    estudiante_nombre.short_description = "Estudiante"
    
    def puntos_display(self, obj):
        if obj.tipo in ['GANANCIA', 'BONUS']:
            color = '#4caf50'
            signo = '+'
        else:
            color = '#f44336'
            signo = '-'
        
        return format_html(
            '<span style="background:{};color:white;padding:4px 12px;border-radius:8px;font-weight:bold;">{}{}</span>',
            color, signo, obj.puntos
        )
    puntos_display.short_description = "Puntos"


# ========== RECOMPENSAS ==========
@admin.register(Recompensa)
class RecompensaAdmin(admin.ModelAdmin):
    """Gestión de recompensas canjeables"""
    list_display = ('icono_nombre', 'puntos_requeridos', 'tipo', 'estado', 'cantidad_info', 'nivel_minimo', 'destacado', 'canjes_totales')
    list_filter = ('tipo', 'estado', 'destacado', 'activo')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('destacado',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'icono', 'imagen_url')
        }),
        ('Configuración', {
            'fields': ('tipo', 'puntos_requeridos', 'estado', 'cantidad_disponible', 'nivel_minimo')
        }),
        ('Disponibilidad Temporal', {
            'fields': ('fecha_inicio', 'fecha_fin'),
            'classes': ('collapse',)
        }),
        ('Entrega', {
            'fields': ('instrucciones_entrega', 'enlace_descarga'),
            'classes': ('collapse',)
        }),
        ('Visualización', {
            'fields': ('orden', 'destacado', 'activo')
        }),
    )
    
    def icono_nombre(self, obj):
        destacado = '⭐' if obj.destacado else ''
        return format_html(
            '<span style="font-size:18px;">{} {}</span> {}',
            obj.icono, obj.nombre, destacado
        )
    icono_nombre.short_description = "Recompensa"
    
    def cantidad_info(self, obj):
        restante = obj.cantidad_restante()
        if restante is None:
            return format_html('<span style="color:#4caf50;">∞ Ilimitado</span>')
        
        color = '#4caf50' if restante > 10 else '#ff9800' if restante > 0 else '#f44336'
        return format_html(
            '<span style="color:{};">{} / {}</span>',
            color, restante, obj.cantidad_disponible
        )
    cantidad_info.short_description = "Disponible"
    
    def canjes_totales(self, obj):
        return format_html(
            '<span style="background:#2196f3;color:white;padding:4px 8px;border-radius:4px;">{} canjes</span>',
            obj.cantidad_canjeada
        )
    canjes_totales.short_description = "Canjeado"
    
    actions = ['duplicar_recompensa', 'marcar_destacado', 'marcar_agotado']
    
    def duplicar_recompensa(self, request, queryset):
        for recompensa in queryset:
            recompensa.pk = None
            recompensa.nombre = f"{recompensa.nombre} (Copia)"
            recompensa.cantidad_canjeada = 0
            recompensa.save()
        self.message_user(request, f"{queryset.count()} recompensa(s) duplicada(s)")
    duplicar_recompensa.short_description = "Duplicar recompensas seleccionadas"
    
    def marcar_destacado(self, request, queryset):
        queryset.update(destacado=True)
        self.message_user(request, f"{queryset.count()} recompensa(s) marcada(s) como destacadas")
    marcar_destacado.short_description = "Marcar como destacado"
    
    def marcar_agotado(self, request, queryset):
        queryset.update(estado='AGOTADO')
        self.message_user(request, f"{queryset.count()} recompensa(s) marcada(s) como agotadas")
    marcar_agotado.short_description = "Marcar como agotado"


@admin.register(CanjeRecompensa)
class CanjeRecompensaAdmin(admin.ModelAdmin):
    """Gestión de canjes de recompensas"""
    list_display = ('estudiante_nombre', 'recompensa_info', 'puntos_gastados', 'estado_display', 'fecha_canje', 'fecha_entrega', 'atendido_por')
    list_filter = ('estado', 'fecha_canje', 'recompensa__tipo')
    search_fields = ('estudiante__nombre', 'recompensa__nombre')
    readonly_fields = ('estudiante', 'recompensa', 'puntos_gastados', 'fecha_canje')
    
    fieldsets = (
        ('Información del Canje', {
            'fields': ('estudiante', 'recompensa', 'puntos_gastados', 'fecha_canje', 'estado')
        }),
        ('Entrega', {
            'fields': ('fecha_entrega', 'nota_entrega', 'atendido_por')
        }),
    )
    
    def estudiante_nombre(self, obj):
        return obj.estudiante.nombre
    estudiante_nombre.short_description = "Estudiante"
    
    def recompensa_info(self, obj):
        return format_html(
            '{} <b>{}</b>',
            obj.recompensa.icono, obj.recompensa.nombre
        )
    recompensa_info.short_description = "Recompensa"
    
    def estado_display(self, obj):
        colores = {
            'PENDIENTE': '#ff9800',
            'PROCESANDO': '#2196f3',
            'ENTREGADO': '#4caf50',
            'CANCELADO': '#f44336'
        }
        return format_html(
            '<span style="background:{};color:white;padding:4px 12px;border-radius:12px;">{}</span>',
            colores.get(obj.estado, '#999'), obj.get_estado_display()
        )
    estado_display.short_description = "Estado"
    
    actions = ['marcar_entregado', 'marcar_procesando']
    
    def marcar_entregado(self, request, queryset):
        count = 0
        for canje in queryset:
            canje.marcar_entregado(nota="Marcado como entregado desde admin")
            count += 1
        self.message_user(request, f"{count} canje(s) marcado(s) como entregados")
    marcar_entregado.short_description = "Marcar como entregado"
    
    def marcar_procesando(self, request, queryset):
        queryset.update(estado='PROCESANDO')
        self.message_user(request, f"{queryset.count()} canje(s) en procesamiento")
    marcar_procesando.short_description = "Marcar como procesando"


# ========================================
# FIN DEL ADMIN - Gamificación Completamente Desactivada
