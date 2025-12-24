from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.shortcuts import render, redirect
from django.urls import path
import openpyxl
from django.http import HttpResponse, JsonResponse
from .models import Estudiante, Plantilla, Campana, EnvioLog, Linea, WhatsappLog, Etiqueta
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
# 2. ACCIÓN: IMPORTAR ESTUDIANTES MASIVAMENTE
# =================================================
@admin.action(description='📤 Importar Estudiantes desde Excel')
def importar_estudiantes_desde_logs(modeladmin, request, queryset):
    """
    Importa estudiantes desde un archivo Excel en la vista de logs.
    """
    if request.method == 'POST':
        archivo = request.FILES.get('archivo_estudiantes')
        
        if not archivo:
            modeladmin.message_user(request, '❌ Por favor selecciona un archivo Excel', level=messages.ERROR)
            return redirect(request.META.get('HTTP_REFERER', '/admin/core/enviolog/'))
        
        try:
            # Validar extensión
            if not archivo.name.endswith(('.xlsx', '.xls')):
                modeladmin.message_user(request, '❌ El archivo debe ser .xlsx o .xls', level=messages.ERROR)
                return redirect(request.META.get('HTTP_REFERER', '/admin/core/enviolog/'))
            
            # Cargar Excel
            wb = openpyxl.load_workbook(archivo)
            ws = wb.active
            
            creados = 0
            actualizados = 0
            errores = []
            
            # Procesar filas (saltar encabezado en fila 1)
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    nombre = row[0]
                    telefono = row[1]
                    
                    if not nombre or not telefono:
                        continue
                    
                    telefono_str = str(telefono).strip()
                    nombre_str = str(nombre).strip()
                    
                    estudiante, created = Estudiante.objects.update_or_create(
                        telefono=telefono_str,
                        defaults={'nombre': nombre_str, 'activo': True}
                    )
                    
                    if created:
                        creados += 1
                    else:
                        actualizados += 1
                
                except Exception as e:
                    errores.append(f"Fila {row_idx}: {str(e)}")
            
            # Mensaje de éxito
            total = creados + actualizados
            msg = f"✅ Importación completada: {creados} nuevos, {actualizados} actualizados, {total} total"
            
            if errores:
                msg += f"\n⚠️ {len(errores)} errores encontrados"
            
            modeladmin.message_user(request, msg, level=messages.SUCCESS)
            
        except Exception as e:
            modeladmin.message_user(request, f'❌ Error al procesar: {str(e)}', level=messages.ERROR)
        
        return redirect(request.META.get('HTTP_REFERER', '/admin/core/enviolog/'))
    
    # Mostrar formulario para subir archivo
    return render(request, 'admin/importar_en_logs.html', {
        'action': 'importar_estudiantes_desde_logs',
        'site_header': 'Importar Estudiantes'
    })

# =================================================
# 2. CONFIGURACIÓN DE TABLAS
# =================================================

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'mostrar_etiquetas', 'activo', 'fecha_registro')
    search_fields = ('nombre', 'telefono')
    list_filter = ('activo', 'etiquetas')
    filter_horizontal = ('etiquetas',)
    list_per_page = 20
    actions = ['exportar_estudiantes_excel', 'enviar_mensaje_prueba_accion', 'aplicar_etiquetas_accion', 'enviar_bienvenida_accion']
    
    def save_model(self, request, obj, form, change):
        """
        Guarda el estudiante (envío automático desactivado - usar acción manual)
        """
        # Solo guardar el estudiante
        super().save_model(request, obj, form, change)
        
        # Mensaje informativo
        if not change:  # Es nuevo
            self.message_user(
                request,
                f"✅ Estudiante {obj.nombre} creado. Usa la acción '👋 Enviar bienvenida' para enviar mensaje.",
                messages.SUCCESS
            )
    
    @admin.action(description='👋 Enviar mensaje de bienvenida')
    def enviar_bienvenida_accion(self, request, queryset):
        """Acción para enviar bienvenida a estudiantes seleccionados (texto simple)"""
        from .twilio_templates import enviar_mensaje_proactivo_simple
        
        exitosos = 0
        fallidos = 0
        
        for estudiante in queryset.filter(activo=True):
            # Mensaje de bienvenida simple (sin plantilla)
            mensaje = f"""¡Hola {estudiante.nombre}! 👋 Bienvenido a Eki Educación.

Soy tu asistente virtual inteligente. Puedo ayudarte con:

✅ Consultar tus tareas pendientes
✅ Ver tu horario de clases
✅ Revisar tu progreso académico
✅ Recordatorios importantes

¿En qué puedo ayudarte hoy?"""
            
            resultado = enviar_mensaje_proactivo_simple(estudiante.telefono, mensaje)
            
            if resultado.get('exito'):
                exitosos += 1
            else:
                fallidos += 1
        
        self.message_user(
            request,
            f"✅ Bienvenidas enviadas: {exitosos} exitosas, {fallidos} fallidas",
            messages.SUCCESS if fallidos == 0 else messages.WARNING
        )
    
    def mostrar_etiquetas(self, obj):
        """Mostrar etiquetas con colores"""
        from django.utils.html import format_html
        etiquetas = obj.etiquetas.all()
        if not etiquetas:
            return '-'
        
        html = ''
        for etiq in etiquetas:
            html += f'<span style="background-color: {etiq.color}; color: white; padding: 3px 8px; border-radius: 3px; margin-right: 5px; font-size: 0.85em;">{etiq.nombre}</span>'
        return format_html(html)
    
    mostrar_etiquetas.short_description = 'Etiquetas'
    
    def get_urls(self):
        """Agregar URL personalizada para importar masivamente"""
        urls = super().get_urls()
        custom_urls = [
            path('importar-masivamente/', self.admin_site.admin_view(self.importar_masivamente), name='core_estudiante_importar'),
            path('enviar-mensaje-prueba/', self.admin_site.admin_view(self.enviar_mensaje_prueba), name='core_estudiante_enviar_mensaje'),
            path('aplicar-etiquetas/', self.admin_site.admin_view(self.aplicar_etiquetas_view), name='core_estudiante_aplicar_etiquetas'),
        ]
        return custom_urls + urls
    
    @admin.action(description='📤 Enviar mensaje de prueba')
    def enviar_mensaje_prueba_accion(self, request, queryset):
        """Acción para enviar mensaje de prueba a estudiantes seleccionados"""
        ids = ','.join(str(est.id) for est in queryset)
        return redirect(f'/admin/core/estudiante/enviar-mensaje-prueba/?ids={ids}')
    
    @admin.action(description='🏷️ Aplicar etiquetas')
    def aplicar_etiquetas_accion(self, request, queryset):
        """Acción para aplicar etiquetas a estudiantes seleccionados"""
        ids = ','.join(str(est.id) for est in queryset)
        return redirect(f'/admin/core/estudiante/aplicar-etiquetas/?ids={ids}')
    
    def enviar_mensaje_prueba(self, request):
        """Vista para enviar mensaje de prueba y opcionalmente guardar como plantilla"""
        from .utils import enviar_whatsapp, enviar_whatsapp_twilio
        from .models import Plantilla
        
        # Obtener estudiantes seleccionados
        ids = request.GET.get('ids', '').split(',')
        estudiantes = Estudiante.objects.filter(id__in=ids, activo=True)
        
        context = {
            'estudiantes': estudiantes,
            'mensaje': None,
            'error': False,
            'site_header': self.admin_site.site_header,
            'site_title': self.admin_site.site_title,
        }
        
        if request.method == 'POST':
            try:
                proveedor = request.POST.get('proveedor', 'meta')
                mensaje_texto = request.POST.get('mensaje', '').strip()
                url_imagen = request.POST.get('url_imagen', '').strip()
                guardar_plantilla = request.POST.get('guardar_plantilla') == 'on'
                nombre_plantilla = request.POST.get('nombre_plantilla', '').strip()
                accion = request.POST.get('accion', 'enviar')
                
                # Validar
                if not mensaje_texto:
                    context['mensaje'] = '<strong>❌ Error:</strong> Debes escribir un mensaje'
                    context['error'] = True
                    return render(request, 'admin/enviar_mensaje_prueba.html', context)
                
                # Guardar como plantilla si se solicitó
                plantilla_creada = None
                if guardar_plantilla and nombre_plantilla:
                    plantilla_creada = Plantilla.objects.create(
                        nombre_interno=nombre_plantilla,
                        cuerpo_mensaje=mensaje_texto,
                        proveedor=proveedor,
                        tiene_imagen=bool(url_imagen),
                        url_imagen=url_imagen if url_imagen else None
                    )
                
                # Enviar mensajes
                exitosos = 0
                fallidos = 0
                
                for estudiante in estudiantes:
                    mensaje_personalizado = mensaje_texto.replace('{nombre}', estudiante.nombre)
                    
                    try:
                        if proveedor == 'twilio':
                            resultado = enviar_whatsapp_twilio(
                                telefono=estudiante.telefono,
                                texto=mensaje_personalizado,
                                url_imagen=url_imagen if url_imagen else None
                            )
                        else:  # meta
                            resultado = enviar_whatsapp(
                                telefono=estudiante.telefono,
                                texto=mensaje_personalizado,
                                url_imagen=url_imagen if url_imagen else None
                            )
                        
                        if resultado['success']:
                            exitosos += 1
                        else:
                            fallidos += 1
                    except Exception:
                        fallidos += 1
                
                # Mensaje de resultado
                msg = f'<strong>✅ Mensajes enviados!</strong><br>'
                msg += f'📤 Exitosos: {exitosos}<br>'
                if fallidos > 0:
                    msg += f'❌ Fallidos: {fallidos}<br>'
                
                if plantilla_creada:
                    msg += f'<br>💾 Plantilla guardada: <strong>{plantilla_creada.nombre_interno}</strong>'
                
                context['mensaje'] = msg
                context['error'] = False
                
            except Exception as e:
                context['mensaje'] = f'<strong>❌ Error:</strong> {str(e)}'
                context['error'] = True
        
        return render(request, 'admin/enviar_mensaje_prueba.html', context)
    
    def aplicar_etiquetas_view(self, request):
        """Vista para aplicar etiquetas a estudiantes seleccionados"""
        from .models import Etiqueta
        
        ids = request.GET.get('ids', '').split(',')
        estudiantes = Estudiante.objects.filter(id__in=ids)
        
        context = {
            'estudiantes': estudiantes,
            'etiquetas_disponibles': Etiqueta.objects.all(),
        }
        
        if request.method == 'POST':
            etiquetas_ids = request.POST.getlist('etiquetas')
            accion = request.POST.get('accion', 'agregar')  # agregar o reemplazar
            
            if not etiquetas_ids:
                context['mensaje'] = '<strong>⚠️ Selecciona al menos una etiqueta</strong>'
                context['error'] = True
            else:
                etiquetas = Etiqueta.objects.filter(id__in=etiquetas_ids)
                
                for estudiante in estudiantes:
                    if accion == 'reemplazar':
                        estudiante.etiquetas.set(etiquetas)
                    else:  # agregar
                        estudiante.etiquetas.add(*etiquetas)
                
                nombres_etiquetas = ', '.join([e.nombre for e in etiquetas])
                context['mensaje'] = f'<strong>✅ Etiquetas aplicadas!</strong><br>'
                context['mensaje'] += f'👥 Estudiantes: {estudiantes.count()}<br>'
                context['mensaje'] += f'🏷️ Etiquetas: {nombres_etiquetas}'
                context['error'] = False
        
        return render(request, 'admin/aplicar_etiquetas.html', context)
    
    def importar_masivamente(self, request):
        """Vista personalizada para importar estudiantes masivamente"""
        if request.method == 'POST':
            archivo = request.FILES.get('archivo_excel')
            
            if not archivo:
                messages.error(request, '❌ Por favor selecciona un archivo Excel')
                return render(request, 'admin/importar_estudiantes_masivamente.html', {
                    'site_header': self.admin_site.site_header,
                    'site_title': self.admin_site.site_title,
                })
            
            try:
                # Validar extensión
                if not archivo.name.endswith(('.xlsx', '.xls')):
                    messages.error(request, '❌ El archivo debe ser .xlsx o .xls')
                    return render(request, 'admin/importar_estudiantes_masivamente.html', {
                        'site_header': self.admin_site.site_header,
                        'site_title': self.admin_site.site_title,
                    })
                
                # Cargar Excel
                wb = openpyxl.load_workbook(archivo)
                ws = wb.active
                
                creados = 0
                actualizados = 0
                errores = []
                
                # Procesar filas (saltar encabezado en fila 1)
                for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    try:
                        nombre = row[0]
                        telefono = row[1]
                        
                        if not nombre or not telefono:
                            continue
                        
                        telefono_str = str(telefono).strip()
                        nombre_str = str(nombre).strip()
                        
                        estudiante, created = Estudiante.objects.update_or_create(
                            telefono=telefono_str,
                            defaults={'nombre': nombre_str, 'activo': True}
                        )
                        
                        if created:
                            creados += 1
                        else:
                            actualizados += 1
                    
                    except Exception as e:
                        errores.append(f"Fila {row_idx}: {str(e)}")
                
                # Mensaje de éxito
                total = creados + actualizados
                mensaje = f"✅ Importación completada: {creados} nuevos, {actualizados} actualizados, {total} total procesados"
                
                if errores:
                    mensaje += f"\n⚠️ {len(errores)} errores encontrados"
                
                messages.success(request, mensaje)
                
                return render(request, 'admin/importar_estudiantes_masivamente.html', {
                    'site_header': self.admin_site.site_header,
                    'site_title': self.admin_site.site_title,
                    'creados': creados,
                    'actualizados': actualizados,
                    'total': total,
                    'errores': errores,
                })
                
            except Exception as e:
                messages.error(request, f'❌ Error al procesar: {str(e)}')
                return render(request, 'admin/importar_estudiantes_masivamente.html', {
                    'site_header': self.admin_site.site_header,
                    'site_title': self.admin_site.site_title,
                })
        
        # GET: Mostrar formulario
        return render(request, 'admin/importar_estudiantes_masivamente.html', {
            'site_header': self.admin_site.site_header,
            'site_title': self.admin_site.site_title,
        })
    
    def exportar_estudiantes_excel(self, request, queryset):
        """Exportar estudiantes seleccionados a Excel."""
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="estudiantes_export.xlsx"'
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Estudiantes'
        
        # Encabezados
        headers = ['Nombre', 'Teléfono', 'Activo', 'Fecha Registro']
        ws.append(headers)
        
        # Datos
        for est in queryset:
            ws.append([
                est.nombre,
                est.telefono,
                'Sí' if est.activo else 'No',
                est.fecha_registro.strftime('%Y-%m-%d %H:%M') if est.fecha_registro else ''
            ])
        
        wb.save(response)
        return response
    
    exportar_estudiantes_excel.short_description = '📥 Descargar Estudiantes (Excel)'
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Personalizar el formulario para agregar un botón de importar masivamente"""
        from django.urls import reverse
        extra_context = extra_context or {}
        # Usar reverse para obtener la URL personalizada
        extra_context['importar_url'] = reverse('admin:core_estudiante_importar')
        extra_context['show_importar_btn'] = True
        return super().changeform_view(
            request, object_id=object_id, form_url=form_url, extra_context=extra_context
        )


@admin.register(Etiqueta)
class EtiquetaAdmin(admin.ModelAdmin):
    from .forms import EtiquetaForm
    form = EtiquetaForm
    
    list_display = ('mostrar_etiqueta_color', 'descripcion', 'contador_estudiantes', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    list_per_page = 20
    
    class Media:
        css = {
            'all': ('admin/css/etiqueta_color_selector.css',)
        }
    
    def mostrar_etiqueta_color(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 12px; border-radius: 4px; font-weight: 500;">{}</span>',
            obj.color, obj.nombre
        )
    mostrar_etiqueta_color.short_description = 'Etiqueta'
    
    def contador_estudiantes(self, obj):
        count = obj.estudiantes.count()
        if count == 0:
            return '0 estudiantes'
        return f'{count} estudiante{"s" if count != 1 else ""}'
    contador_estudiantes.short_description = 'Estudiantes'


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ('nombre_interno', 'tipo_contenido', 'proveedor', 'activa', 'preview_media')
    search_fields = ('nombre_interno', 'twilio_template_sid')
    list_filter = ('tipo_contenido', 'proveedor', 'activa')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre_interno', 'cuerpo_mensaje', 'activa')
        }),
        ('Proveedor de Mensajería', {
            'fields': ('proveedor', 'twilio_template_sid', 'twilio_variables'),
            'description': 'Configura Twilio Content Template. Variables formato: {"1": "nombre", "2": "materia"}'
        }),
        ('Contenido Multimedia', {
            'fields': ('tipo_contenido', 'url_media'),
            'description': 'Tipo de contenido y URL del media (imagen/video/archivo)'
        }),
    )
    
    def preview_media(self, obj):
        """Vista previa del media"""
        from django.utils.html import format_html
        
        if obj.tipo_contenido == 'imagen' and obj.url_media:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 50px; border-radius: 4px;" />',
                obj.url_media
            )
        elif obj.tipo_contenido == 'video' and obj.url_media:
            return format_html('🎥 <a href="{}" target="_blank">Ver video</a>', obj.url_media)
        elif obj.tipo_contenido == 'archivo' and obj.url_media:
            return format_html('📎 <a href="{}" target="_blank">Ver archivo</a>', obj.url_media)
        return '-'
    
    preview_media.short_description = 'Preview'

@admin.register(Campana)
class CampanaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estado_visual', 'proveedor', 'mostrar_etiquetas_filtro', 'conteo_destinatarios', 'fecha_creacion')
    list_filter = ('ejecutada', 'proveedor', 'filtro_etiquetas', 'fecha_creacion')
    search_fields = ('nombre',)
    filter_horizontal = ('destinatarios', 'filtro_etiquetas')
    
    # Configuramos para que el formulario de crear sea limpio
    fieldsets = (
        ('📝 Datos Básicos', {
            'fields': ('nombre', 'plantilla', 'canal_envio', 'proveedor', 'linea_origen')
        }),
        ('📂 Importar (Opcional)', {
            'fields': ('archivo_excel',),
            'description': 'Sube un Excel con columnas A (Nombre) y B (Teléfono).'
        }),
        ('👥 Audiencia', {
            'fields': ('destinatarios',)
        }),
        ('🏷️ Segmentación por Etiquetas', {
            'fields': ('filtro_etiquetas',),
            'description': 'Filtra los destinatarios: solo se enviarán mensajes a estudiantes con AL MENOS UNA de estas etiquetas. Si no seleccionas ninguna, se envía a todos los destinatarios.'
        }),
        ('⏰ Programación', {
            'fields': ('fecha_programada',),
            'description': 'Programa la campaña para que se ejecute automáticamente en una fecha/hora específica.'
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
    
    def mostrar_etiquetas_filtro(self, obj):
        """Mostrar etiquetas de filtro con colores"""
        from django.utils.html import format_html
        etiquetas = obj.filtro_etiquetas.all()
        if not etiquetas:
            return '-'
        
        html = ''
        for etiq in etiquetas:
            html += f'<span style="background-color: {etiq.color}; color: white; padding: 2px 6px; border-radius: 3px; margin-right: 3px; font-size: 0.8em;">{etiq.nombre}</span>'
        return format_html(html)
    
    mostrar_etiquetas_filtro.short_description = 'Filtro de etiquetas'
    
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
    
    # Botones de exportar e importar
    actions = [exportar_logs_excel, importar_estudiantes_desde_logs]
    
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


# TABLA DE LOGS DE WHATSAPP
@admin.register(WhatsappLog)
class WhatsappLogAdmin(admin.ModelAdmin):
    """Admin para ver logs REALES de WhatsApp"""
    # Columnas principales
    list_display = ('id', 'telefono_formateado', 'tipo_mensaje', 'tipo_color', 'fecha', 'mensaje_preview', 'mensaje_id')
    
    # Filtros laterales
    list_filter = ('tipo', 'fecha')
    
    # Búsqueda
    search_fields = ('telefono', 'mensaje', 'mensaje_id')
    
    # Solo lectura (son logs, no se deben editar)
    readonly_fields = ('telefono', 'mensaje', 'mensaje_id', 'tipo', 'fecha')
    
    # Organización del formulario
    fieldsets = (
        ('📱 Información de Contacto', {
            'fields': ('telefono',)
        }),
        ('💬 Mensaje', {
            'fields': ('mensaje',)
        }),
        ('📊 Estado y Metadata', {
            'fields': ('tipo', 'mensaje_id', 'fecha')
        }),
    )
    
    def telefono_formateado(self, obj):
        return format_html('<strong>{}</strong>', obj.telefono)
    telefono_formateado.short_description = "Teléfono"
    
    def tipo_mensaje(self, obj):
        if obj.tipo == 'INCOMING':
            return format_html('<span style="color: #007bff;">📥 Entrante</span>')
        else:
            return format_html('<span style="color: #28a745;">📤 Saliente</span>')
    tipo_mensaje.short_description = "Tipo"
    
    def tipo_color(self, obj):
        if obj.tipo == 'SENT':
            return format_html('<span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">✅ ENVIADO</span>')
        elif obj.tipo == 'INCOMING':
            return format_html('<span style="background: #007bff; color: white; padding: 3px 8px; border-radius: 3px;">📥 RECIBIDO</span>')
        else:
            return format_html('<span style="background: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>', obj.tipo)
    tipo_color.short_description = "Estado"
    
    def mensaje_preview(self, obj):
        if not obj.mensaje:
            return "—"
        preview = obj.mensaje[:50]
        if len(obj.mensaje) > 50:
            preview += "..."
        return preview
    mensaje_preview.short_description = "Mensaje"
    
    def get_ordering(self, request):
        # Ordenar por fecha descendente por defecto
        return ['-fecha']
