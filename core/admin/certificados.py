from core.admin._common import *  # noqa: F401,F403

# ========================================
# 📜 CERTIFICADOS DIGITALES
# ========================================

class PlantillaCertificadoAdmin(admin.ModelAdmin):
    """Plantillas de Certificados — imagen S3 o diseño eki con vista previa"""
    change_form_template = 'admin/learning/plantillacertificado/change_form.html'
    list_display = ('nombre', 'curso_info', 'cliente_info', 'tipo_plantilla', 'por_defecto', 'activa')
    list_filter = ('activa', 'por_defecto', 'modo_plantilla', 'cliente', 'curso')
    search_fields = ('nombre', 'descripcion', 'cliente__nombre', 'curso__nombre')
    list_per_page = 50
    
    fieldsets = (
        ('📝 Información Básica', {
            'fields': ('nombre', 'descripcion', 'curso', 'cliente', 'modo_plantilla', 'activa', 'por_defecto'),
            'description': mark_safe('''<div style="background:#e3f2fd;padding:12px;border-radius:8px;border-left:4px solid #2196F3;margin:10px 0;">
                <strong>📌 IMPORTANTE:</strong> Selecciona el <strong>Curso</strong> para que el certificado se genere automáticamente al completar ese curso.<br>
                Si no seleccionas curso, se usará solo si está marcada como "Por defecto".
            </div>''')
        }),
        ('🖼️ Imagen del Certificado (S3)', {
            'fields': ('formato_certificado', 'archivo_plantilla_imagen', 'url_plantilla_imagen'),
            'description': mark_safe('''<div style="background:#e8f5e9;padding:15px;border-radius:8px;border-left:4px solid #4CAF50;margin:10px 0;">
                <strong>✅ CÓMO PREPARAR TU PLANTILLA DE CERTIFICADO</strong><br><br>
                1. Diseña tu certificado en Canva, Word, Photoshop, etc.<br>
                2. Coloca <strong>marcadores de color PURO</strong> (relleno sólido, sin degradado) donde quieras cada dato:<br>
                &nbsp;&nbsp;&nbsp;⬜ <strong>GRIS</strong> RGB (128,128,128) = <strong>NOMBRE</strong> del estudiante<br>
                &nbsp;&nbsp;&nbsp;🟥 <strong>ROJO</strong> RGB (255,0,0) = <strong>CÉDULA</strong> / documento<br>
                &nbsp;&nbsp;&nbsp;🟨 <strong>AMARILLO</strong> RGB (255,255,0) = <strong>FECHA</strong> de emisión (hoy; opcional)<br>
                &nbsp;&nbsp;&nbsp;🟦 <strong>AZUL</strong> RGB (0,0,255) = <strong>CÓDIGO QR</strong> de verificación<br>
                3. Exporta como <strong>PNG o JPG</strong> (mejor PNG para colores exactos)<br>
                4. Sube la imagen aquí o pega la URL de S3<br><br>
                <strong>📐 Tamaños de texto (automáticos):</strong> nombre ~56px · cédula ~30px · fecha ~26px · QR 130px.<br>
                <strong>💡 Cada curso puede tener su propia plantilla.</strong> Al actualizar, los certificados nuevos usan el diseño actualizado.<br>
                <strong>⚠️ URL:</strong> pega solo UNA vez la URL completa (https://…).<br>
                <strong>🔄 Archivo nuevo:</strong> el archivo tiene prioridad y actualiza la URL sola.
            </div>''')
        }),
        ('📄 PDF Personalizado (Avanzado)', {
            'fields': ('archivo_plantilla_pdf', 'variable_nombre', 'variable_curso', 'variable_fecha'),
            'classes': ('collapse',),
            'description': mark_safe('''<div style="background:#f5f5f5;padding:10px;border-radius:8px;margin:10px 0;">
                <em>Opcional: sube un PDF con variables {nombre}, {curso}, {fecha}</em>
            </div>''')
        }),
        ('🎨 Diseño eki', {
            'fields': ('imagen_fondo', 'logo_institucion', 'color_primario', 'color_secundario', 'texto_superior', 'texto_certificado'),
            'description': mark_safe('''<div style="background:#ede9fe;padding:12px;border-radius:8px;border-left:4px solid #7c3aed;margin:8px 0;">
                Use este modo cuando quiera armar el certificado con colores y textos de eki.
                La vista previa a la derecha muestra un ejemplo con nombre de prueba.
            </div>'''),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'preview/',
                self.admin_site.admin_view(self.preview_certificado_view),
                name='learning_plantillacertificado_preview',
            ),
            path(
                'estudiantes-preview/',
                self.admin_site.admin_view(self.estudiantes_preview_view),
                name='learning_plantillacertificado_estudiantes_preview',
            ),
        ]
        return custom + urls

    def estudiantes_preview_view(self, request):
        """Lista estudiantes del cliente para elegir en vista previa."""
        from django.http import JsonResponse

        from core.models import Estudiante

        raw = request.GET.get('cliente') or ''
        if not str(raw).isdigit():
            return JsonResponse({'estudiantes': []})
        filas = list(
            Estudiante.objects.filter(cliente_id=int(raw), activo=True)
            .order_by('nombre')
            .values('id', 'nombre', 'cedula')[:200]
        )
        return JsonResponse({'estudiantes': filas})

    def preview_certificado_view(self, request):
        """Genera PNG de vista previa según modo y campos del formulario."""
        import logging

        from django.http import HttpResponse
        from core.certificado_preview import generar_preview_certificado, plantilla_desde_request
        from core.models import Estudiante

        if request.method != 'POST':
            return HttpResponse(status=405)

        nombre = cedula = org = url = None
        est_id_raw = request.POST.get('estudiante_preview')
        if str(est_id_raw or '').isdigit():
            est = (
                Estudiante.objects.filter(pk=int(est_id_raw), activo=True)
                .select_related('cliente')
                .first()
            )
            if est:
                nombre = est.nombre
                cedula = est.cedula or ''
                org = est.cliente.nombre if est.cliente else None
                url = f'https://certificados.eki.technology/verificar-certificado/PREVIEW/'

        try:
            plantilla = plantilla_desde_request(request.POST)
            buf = generar_preview_certificado(
                plantilla,
                post_data=request.POST,
                files=request.FILES,
                nombre_estudiante=nombre,
                cedula_estudiante=cedula,
                organizacion_nombre=org,
                url_verificacion=url,
            )
            if not buf:
                return HttpResponse('No se pudo generar', status=500)
            return HttpResponse(buf.getvalue(), content_type='image/png')
        except ValueError as exc:
            return HttpResponse(str(exc), status=400)
        except Exception as exc:
            logging.getLogger(__name__).exception('Vista previa certificado falló')
            return HttpResponse(str(exc), status=500)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from django.urls import reverse

        from core.models import Estudiante

        extra_context = extra_context or {}
        estudiantes = []
        if object_id:
            obj = self.get_object(request, object_id)
            if obj and obj.cliente_id:
                estudiantes = list(
                    Estudiante.objects.filter(cliente_id=obj.cliente_id, activo=True)
                    .order_by('nombre')
                    .values('id', 'nombre', 'cedula')[:200]
                )
        extra_context['estudiantes_preview'] = estudiantes
        extra_context['estudiantes_preview_url'] = reverse(
            'admin:learning_plantillacertificado_estudiantes_preview',
        )
        return super().change_view(request, object_id, form_url, extra_context=extra_context)
    
    def get_form(self, request, obj=None, **kwargs):
        """Personaliza el formulario para usar color picker"""
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['color_primario'].widget = ColorPickerWidget()
        form.base_fields['color_secundario'].widget = ColorPickerWidget()
        return form
    
    def curso_info(self, obj):
        """Muestra el curso asignado"""
        if obj.curso:
            return format_html(
                '<span style="background:#c8e6c9;padding:4px 10px;border-radius:12px;font-size:11px;">📚 {}</span>',
                obj.curso.nombre
            )
        return format_html('<span style="color:#999;font-style:italic;">Sin curso (general)</span>')
    curso_info.short_description = "Curso"
    
    def cliente_info(self, obj):
        """Muestra el cliente asociado"""
        if obj.cliente:
            return format_html(
                '<span style="background:#e3f2fd;padding:4px 10px;border-radius:12px;font-size:11px;">🏢 {}</span>',
                obj.cliente.nombre
            )
        return format_html('<span style="color:#999;font-style:italic;">General (eki)</span>')
    cliente_info.short_description = "Cliente"
    
    def tipo_plantilla(self, obj):
        """Muestra el modo efectivo de la plantilla"""
        modo = obj.modo_efectivo()
        labels = {
            'imagen': ('🖼️ Imagen', '#f59f00'),
            'diseno_eki': ('🎨 Diseño eki', '#2196F3'),
            'pdf': ('📄 PDF', '#4CAF50'),
        }
        label, color = labels.get(modo, ('?', '#64748b'))
        if modo == 'imagen' and obj.url_plantilla_imagen and not obj.archivo_plantilla_imagen:
            label += ' (URL)'
        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color,
            label,
        )
    tipo_plantilla.short_description = "Tipo"
    
    def vista_colores(self, obj):
        """Muestra preview de los colores (solo si no usa PDF)"""
        if obj.archivo_plantilla_pdf:
            return format_html('<span style="color:#999;">-</span>')
        
        return format_html(
            '<div style="display:flex;gap:8px;align-items:center;">'
            '<div style="background:{};width:40px;height:40px;border-radius:6px;border:2px solid #ddd;box-shadow:0 2px 4px rgba(0,0,0,0.1);"></div>'
            '<div style="background:{};width:40px;height:40px;border-radius:6px;border:2px solid #ddd;box-shadow:0 2px 4px rgba(0,0,0,0.1);"></div>'
            '</div>',
            obj.color_primario,
            obj.color_secundario
        )
    vista_colores.short_description = "🎨 Colores"
    
    def total_certificados(self, obj):
        """Cuenta certificados generados con esta plantilla"""
        # Por ahora retorna placeholder, puedes implementar el conteo real si agregas FK en Certificado
        return format_html('<span style="color:#999;">-</span>')
    total_certificados.short_description = "Certificados"
    
    def save_model(self, request, obj, form, change):
        """Al guardar plantilla: auto-regenerar certificados existentes que usen esta plantilla"""
        super().save_model(request, obj, form, change)
        if change:  # Solo al editar (no al crear)
            # Buscar certificados que usen esta plantilla y regenerarlos
            from core.models_certificados import Certificado
            from core.certificado_service import generar_y_guardar_certificado
            import logging
            logger = logging.getLogger(__name__)
            
            # Certificados del curso de esta plantilla
            cert_qs = Certificado.objects.filter(emitido=True)
            if obj.curso:
                cert_qs = cert_qs.filter(curso=obj.curso)
            elif obj.cliente:
                cert_qs = cert_qs.filter(estudiante__cliente=obj.cliente)
            else:
                # Plantilla por defecto — regenerar solo los que NO tienen plantilla especifica
                if obj.por_defecto:
                    from core.models_certificados import PlantillaCertificado
                    cursos_con_plantilla = PlantillaCertificado.objects.filter(
                        activa=True, curso__isnull=False
                    ).exclude(pk=obj.pk).values_list('curso_id', flat=True)
                    cert_qs = cert_qs.exclude(curso_id__in=cursos_con_plantilla)
                else:
                    cert_qs = cert_qs.none()
            
            count = cert_qs.count()
            if count > 0 and count <= 50:  # Limite de seguridad
                regenerados = 0
                for cert in cert_qs:
                    try:
                        if generar_y_guardar_certificado(cert, plantilla=obj, force=True):
                            regenerados += 1
                    except Exception as e:
                        logger.error(f"Error regenerando cert {cert.codigo_verificacion}: {e}")
                if regenerados > 0:
                    self.message_user(
                        request,
                        f"🔄 {regenerados} certificado(s) regenerado(s) automaticamente con la nueva plantilla",
                        messages.SUCCESS
                    )
            elif count > 50:
                self.message_user(
                    request,
                    f"⚠️ Hay {count} certificados que usan esta plantilla. Usa la accion 'Regenerar' en Certificados para actualizarlos.",
                    messages.WARNING
                )

    actions = ['previsualizar_certificado_accion']

    @admin.action(description='👁️ Previsualizar con nombre de prueba')
    def previsualizar_certificado_accion(self, request, queryset):
        """Abre la plantilla en edición (vista previa a la derecha)."""
        if queryset.count() != 1:
            self.message_user(request, 'Selecciona una sola plantilla.', level=messages.WARNING)
            return
        plantilla = queryset.first()
        url = reverse('admin:learning_plantillacertificado_change', args=[plantilla.pk])
        return redirect(url)


class CertificadoAdmin(admin.ModelAdmin):
    """
    📜 GESTIÓN UNIFICADA DE CERTIFICADOS
    Desde aquí puedes gestionar certificados y ver plantillas
    """
    list_display = (
        'codigo_verificacion',
        'estudiante_info',
        'curso_info',
        'calificacion_badge',
        'mencion_badge',
        'estado_emision',
        'enviado_whatsapp_badge',
        'plantilla_link',
        'fecha_completado'
    )
    list_filter = ('emitido', 'enviado_whatsapp', 'fecha_completado', 'curso')
    search_fields = ('codigo_verificacion', 'estudiante__nombre', 'estudiante__telefono', 'curso__nombre')
    readonly_fields = (
        'codigo_verificacion',
        'creado_en',
        'actualizado_en',
        'vista_previa_certificado',
        'url_verificacion',
        'duracion_dias'
    )
    list_per_page = 50
    ordering = ('-fecha_emision', '-creado_en')
    
    fieldsets = (
        ('📋 Información', {
            'fields': ('codigo_verificacion', 'estudiante', 'curso', 'url_verificacion')
        }),
        ('🎓 Datos Académicos', {
            'fields': ('calificacion_final', 'fecha_inicio', 'fecha_completado', 'duracion_dias')
        }),
        ('📄 Certificado', {
            'fields': ('emitido', 'fecha_emision', 'archivo_pdf', 'archivo_imagen', 'vista_previa_certificado'),
            'description': '📄 PDF o 🖼️ Imagen del certificado generado'
        }),
        ('📲 Envío', {
            'fields': ('enviado_whatsapp', 'fecha_envio')
        }),
        ('🕐 Timestamps', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'generar_certificados', 
        'enviar_por_whatsapp', 
        'regenerar_certificados', 
        'descargar_todos_pdf',
        'descargar_por_cliente',
        'descargar_por_curso',
        'descargar_por_grupo',
        'generar_pdf_consolidado',
        'enviar_email_a_clientes'
    ]
    
    def estudiante_info(self, obj):
        nombre = obj.estudiante.nombre
        telefono = obj.estudiante.telefono
        return format_html(
            '<div style="line-height:1.4;">'
            '<strong>{}</strong><br>'
            '<span style="color:#666;font-size:11px;">📱 {}</span>'
            '</div>',
            nombre, telefono
        )
    estudiante_info.short_description = "👤 Estudiante"
    
    def curso_info(self, obj):
        return format_html(
            '<span style="background:#e3f2fd;color:#1976d2;padding:4px 10px;border-radius:12px;font-size:11px;">'
            '📚 {}'
            '</span>',
            obj.curso.nombre
        )
    curso_info.short_description = "Curso"
    
    def calificacion_badge(self, obj):
        calificacion = float(obj.calificacion_final)
        if calificacion >= 90:
            color = '#4caf50'
            emoji = '🌟'
        elif calificacion >= 80:
            color = '#2196f3'
            emoji = '⭐'
        elif calificacion >= 70:
            color = '#ff9800'
            emoji = '📊'
        else:
            color = '#f44336'
            emoji = '📉'
        
        return format_html(
            '<span style="background:{};color:white;padding:4px 12px;border-radius:12px;font-weight:bold;font-size:12px;">'
            '{} {}%'
            '</span>',
            color, emoji, calificacion
        )
    calificacion_badge.short_description = "📊 Calificación"
    
    def mencion_badge(self, obj):
        mencion = obj.obtener_mencion()
        if mencion:
            return format_html(
                '<span style="background:#ffd700;color:#804000;padding:4px 10px;border-radius:12px;font-size:11px;font-weight:bold;">'
                '🏆 {}'
                '</span>',
                mencion
            )
        return format_html('<span style="color:#999;">-</span>')
    mencion_badge.short_description = "🏆 Mención"
    
    def estado_emision(self, obj):
        if obj.emitido and obj.fecha_emision:
            fecha = obj.fecha_emision.strftime('%d/%m/%Y %H:%M')
            return format_html(
                '<span style="background:#4caf50;color:white;padding:4px 10px;border-radius:12px;font-size:11px;">'
                '✅ Emitido<br>'
                '<span style="font-size:10px;">{}</span>'
                '</span>',
                fecha
            )
        return format_html(
            '<span style="background:#ff9800;color:white;padding:4px 10px;border-radius:12px;font-size:11px;">'
            '⏳ Pendiente'
            '</span>'
        )
    estado_emision.short_description = "Estado"
    
    def enviado_whatsapp_badge(self, obj):
        if obj.enviado_whatsapp and obj.fecha_envio:
            return format_html(
                '<span style="background:#25d366;color:white;padding:4px 10px;border-radius:12px;font-size:11px;">'
                '✅ Enviado'
                '</span>'
            )
        return format_html(
            '<span style="background:#e0e0e0;color:#666;padding:4px 10px;border-radius:12px;font-size:11px;">'
            '📤 No enviado'
            '</span>'
        )
    enviado_whatsapp_badge.short_description = "📲 WhatsApp"
    
    def plantilla_link(self, obj):
        """Link directo para ver plantillas de certificados"""
        count = PlantillaCertificado.objects.filter(cliente=obj.estudiante.cliente).count()
        if count == 0:
            count = PlantillaCertificado.objects.filter(cliente__isnull=True).count()
        
        return format_html(
            '<a href="/admin/core/plantillacertificado/" style="background:#673ab7;color:white;padding:6px 12px;border-radius:12px;text-decoration:none;font-size:11px;font-weight:600;">🎨 {} Plantillas</a>',
            count
        )
    plantilla_link.short_description = "Plantillas"
    
    def url_verificacion(self, obj):
        if obj.codigo_verificacion:
            url = obj.obtener_url_verificacion()
            return format_html(
                '<a href="{}" target="_blank" style="color:#2196f3;">'
                '🔗 Ver certificado público'
                '</a><br>'
                '<code style="font-size:10px;background:#f5f5f5;padding:4px;display:block;margin-top:4px;">{}</code>',
                url, url
            )
        return '-'
    url_verificacion.short_description = "🔗 URL Verificación"
    
    def duracion_dias(self, obj):
        dias = obj.duracion_curso()
        if dias > 0:
            return format_html(
                '<span style="color:#666;">📅 {} día{}</span>',
                dias,
                's' if dias != 1 else ''
            )
        return '-'
    duracion_dias.short_description = "Duración"
    
    def vista_previa_certificado(self, obj):
        if obj.archivo_pdf:
            return format_html(
                '<a href="{}" target="_blank" style="color:#f44336;">'
                '📄 Descargar PDF'
                '</a>',
                obj.archivo_pdf.url
            )
        return format_html('<span style="color:#999;">No generado aún</span>')
    vista_previa_certificado.short_description = "Vista Previa"
    
    @admin.action(description='📄 Generar certificados PDF')
    def generar_certificados(self, request, queryset):
        """Genera los PDFs de los certificados seleccionados"""
        from core.certificado_service import generar_y_guardar_certificado
        from django.utils import timezone
        
        generados = 0
        errores = 0
        
        for certificado in queryset:
            try:
                success = generar_y_guardar_certificado(certificado)
                if success:
                    certificado.emitido = True
                    certificado.fecha_emision = timezone.now()
                    certificado.save()
                    generados += 1
                else:
                    errores += 1
            except Exception as e:
                logger.error(f"Error generando certificado {certificado.codigo_verificacion}: {e}")
                errores += 1
        
        if generados > 0:
            self.message_user(
                request,
                f"✅ {generados} certificado(s) generado(s) exitosamente",
                messages.SUCCESS
            )
        if errores > 0:
            self.message_user(
                request,
                f"❌ {errores} error(es) al generar certificados",
                messages.ERROR
            )
    
    @admin.action(description='📲 Enviar certificados por WhatsApp')
    def enviar_por_whatsapp(self, request, queryset):
        """Envía los certificados por WhatsApp"""
        from core.certificado_service import enviar_certificado_whatsapp
        
        # Filtrar emitidos con PDF o imagen
        queryset = queryset.filter(emitido=True).filter(
            models.Q(archivo_pdf__isnull=False) | models.Q(archivo_imagen__isnull=False)
        ).exclude(archivo_pdf='', archivo_imagen='')
        
        if not queryset.exists():
            self.message_user(
                request,
                "⚠️ Primero debes generar los certificados (PDF o imagen)",
                messages.WARNING
            )
            return
        
        enviados = 0
        errores = 0
        
        for certificado in queryset:
            try:
                success = enviar_certificado_whatsapp(certificado)
                if success:
                    enviados += 1
                else:
                    errores += 1
            except Exception as e:
                logger.error(f"Error enviando certificado {certificado.codigo_verificacion}: {e}")
                errores += 1
        
        if enviados > 0:
            self.message_user(
                request,
                f"✅ {enviados} certificado(s) enviado(s) por WhatsApp",
                messages.SUCCESS
            )
        if errores > 0:
            self.message_user(
                request,
                f"❌ {errores} error(es) al enviar certificados",
                messages.ERROR
            )
    
    @admin.action(description='🔄 Regenerar certificados PDF')
    def regenerar_certificados(self, request, queryset):
        """Regenera los PDFs (útil si cambió el diseño)"""
        from core.certificado_service import generar_y_guardar_certificado
        
        regenerados = 0
        errores = 0
        
        for certificado in queryset:
            try:
                success = generar_y_guardar_certificado(certificado, force=True)
                if success:
                    regenerados += 1
                else:
                    errores += 1
            except Exception as e:
                logger.error(f"Error regenerando certificado {certificado.codigo_verificacion}: {e}")
                errores += 1
        
        if regenerados > 0:
            self.message_user(
                request,
                f"✅ {regenerados} certificado(s) regenerado(s)",
                messages.SUCCESS
            )
        if errores > 0:
            self.message_user(
                request,
                f"❌ {errores} error(es) al regenerar",
                messages.ERROR
            )
    
    @admin.action(description='📥 Descargar todos los certificados en ZIP')
    def descargar_todos_pdf(self, request, queryset):
        """Descarga todos los certificados seleccionados en un archivo ZIP"""
        import zipfile
        from django.http import HttpResponse
        import io
        from django.utils import timezone
        
        # Filtrar solo certificados con PDF
        queryset = queryset.filter(emitido=True, archivo_pdf__isnull=False)
        
        if not queryset.exists():
            self.message_user(
                request,
                "⚠️ No hay certificados con PDF generado",
                messages.WARNING
            )
            return
        
        # Crear archivo ZIP en memoria
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for certificado in queryset:
                try:
                    # Leer el archivo PDF
                    pdf_file = certificado.archivo_pdf.open('rb')
                    pdf_content = pdf_file.read()
                    pdf_file.close()
                    
                    # Nombre del archivo en el ZIP
                    filename = f"{certificado.estudiante.nombre.replace(' ', '_')}_{certificado.curso.nombre.replace(' ', '_')}_{certificado.codigo_verificacion}.pdf"
                    
                    # Agregar al ZIP
                    zip_file.writestr(filename, pdf_content)
                    
                except Exception as e:
                    logger.error(f"Error agregando certificado {certificado.codigo_verificacion} al ZIP: {e}")
        
        # Preparar respuesta HTTP
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="certificados_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip"'
        
        return response
    
    @admin.action(description='� Descargar por Cliente (ZIP)')
    def descargar_por_cliente(self, request, queryset):
        """Descarga certificados agrupados por cliente en ZIPs separados"""
        import zipfile
        from django.http import HttpResponse
        import io
        from django.utils import timezone
        
        # Filtrar certificados con PDF
        queryset = queryset.filter(emitido=True, archivo_pdf__isnull=False)
        
        if not queryset.exists():
            self.message_user(request, "⚠️ No hay certificados con PDF", messages.WARNING)
            return
        
        # Agrupar por cliente
        certificados_por_cliente = {}
        for cert in queryset:
            cliente = cert.estudiante.cliente
            cliente_nombre = cliente.nombre if cliente else "Sin_Cliente"
            if cliente_nombre not in certificados_por_cliente:
                certificados_por_cliente[cliente_nombre] = []
            certificados_por_cliente[cliente_nombre].append(cert)
        
        # Si es un solo cliente, descargar ZIP directo
        if len(certificados_por_cliente) == 1:
            cliente_nombre = list(certificados_por_cliente.keys())[0]
            certs = certificados_por_cliente[cliente_nombre]
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for cert in certs:
                    try:
                        pdf_content = cert.archivo_pdf.read()
                        filename = f"{cert.estudiante.nombre.replace(' ', '_')}_{cert.curso.nombre.replace(' ', '_')}.pdf"
                        zip_file.writestr(filename, pdf_content)
                    except Exception as e:
                        logger.error(f"Error: {e}")
            
            zip_buffer.seek(0)
            response = HttpResponse(zip_buffer.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="Certificados_{cliente_nombre}_{timezone.now().strftime("%Y%m%d")}.zip"'
            return response
        
        # Múltiples clientes: crear ZIP maestro con subdirectorios
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, 'w', zipfile.ZIP_DEFLATED) as zip_master:
            for cliente_nombre, certs in certificados_por_cliente.items():
                for cert in certs:
                    try:
                        pdf_content = cert.archivo_pdf.read()
                        filename = f"{cliente_nombre}/{cert.estudiante.nombre.replace(' ', '_')}_{cert.curso.nombre.replace(' ', '_')}.pdf"
                        zip_master.writestr(filename, pdf_content)
                    except Exception as e:
                        logger.error(f"Error: {e}")
        
        master_zip.seek(0)
        response = HttpResponse(master_zip.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="Certificados_Por_Cliente_{timezone.now().strftime("%Y%m%d")}.zip"'
        
        self.message_user(request, f"✅ Descargados {queryset.count()} certificados de {len(certificados_por_cliente)} cliente(s)", messages.SUCCESS)
        return response
    
    @admin.action(description='📚 Descargar por Curso (ZIP)')
    def descargar_por_curso(self, request, queryset):
        """Descarga certificados agrupados por curso"""
        import zipfile
        from django.http import HttpResponse
        import io
        from django.utils import timezone
        
        queryset = queryset.filter(emitido=True, archivo_pdf__isnull=False)
        
        if not queryset.exists():
            self.message_user(request, "⚠️ No hay certificados con PDF", messages.WARNING)
            return
        
        # Agrupar por curso
        certificados_por_curso = {}
        for cert in queryset:
            curso_nombre = cert.curso.nombre
            if curso_nombre not in certificados_por_curso:
                certificados_por_curso[curso_nombre] = []
            certificados_por_curso[curso_nombre].append(cert)
        
        # Si es un solo curso
        if len(certificados_por_curso) == 1:
            curso_nombre = list(certificados_por_curso.keys())[0]
            certs = certificados_por_curso[curso_nombre]
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for cert in certs:
                    try:
                        pdf_content = cert.archivo_pdf.read()
                        filename = f"{cert.estudiante.nombre.replace(' ', '_')}_{cert.codigo_verificacion}.pdf"
                        zip_file.writestr(filename, pdf_content)
                    except Exception as e:
                        logger.error(f"Error: {e}")
            
            zip_buffer.seek(0)
            response = HttpResponse(zip_buffer.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="Certificados_{curso_nombre.replace(" ", "_")}_{timezone.now().strftime("%Y%m%d")}.zip"'
            return response
        
        # Múltiples cursos
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, 'w', zipfile.ZIP_DEFLATED) as zip_master:
            for curso_nombre, certs in certificados_por_curso.items():
                for cert in certs:
                    try:
                        pdf_content = cert.archivo_pdf.read()
                        filename = f"{curso_nombre.replace(' ', '_')}/{cert.estudiante.nombre.replace(' ', '_')}.pdf"
                        zip_master.writestr(filename, pdf_content)
                    except Exception as e:
                        logger.error(f"Error: {e}")
        
        master_zip.seek(0)
        response = HttpResponse(master_zip.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="Certificados_Por_Curso_{timezone.now().strftime("%Y%m%d")}.zip"'
        
        self.message_user(request, f"✅ Descargados {queryset.count()} certificados de {len(certificados_por_curso)} curso(s)", messages.SUCCESS)
        return response
    
    @admin.action(description='👥 Descargar por Grupo (ZIP)')
    def descargar_por_grupo(self, request, queryset):
        """Descarga certificados agrupados por grupo de estudiantes"""
        import zipfile
        from django.http import HttpResponse
        import io
        from django.utils import timezone
        from core.models_extras import GrupoEstudiantes
        
        queryset = queryset.filter(emitido=True, archivo_pdf__isnull=False)
        
        if not queryset.exists():
            self.message_user(request, "⚠️ No hay certificados con PDF", messages.WARNING)
            return
        
        # Agrupar por grupo
        certificados_por_grupo = {}
        sin_grupo = []
        
        for cert in queryset:
            estudiante = cert.estudiante
            # Buscar grupos del estudiante
            grupos = GrupoEstudiantes.objects.filter(estudiantes=estudiante)
            
            if grupos.exists():
                for grupo in grupos:
                    grupo_nombre = grupo.nombre
                    if grupo_nombre not in certificados_por_grupo:
                        certificados_por_grupo[grupo_nombre] = []
                    certificados_por_grupo[grupo_nombre].append(cert)
            else:
                sin_grupo.append(cert)
        
        if not certificados_por_grupo:
            self.message_user(request, "⚠️ Los estudiantes seleccionados no pertenecen a ningún grupo", messages.WARNING)
            return
        
        # Crear ZIP
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, 'w', zipfile.ZIP_DEFLATED) as zip_master:
            # Certificados por grupo
            for grupo_nombre, certs in certificados_por_grupo.items():
                for cert in certs:
                    try:
                        pdf_content = cert.archivo_pdf.read()
                        filename = f"{grupo_nombre.replace(' ', '_')}/{cert.estudiante.nombre.replace(' ', '_')}_{cert.curso.nombre.replace(' ', '_')}.pdf"
                        zip_master.writestr(filename, pdf_content)
                    except Exception as e:
                        logger.error(f"Error: {e}")
            
            # Certificados sin grupo
            if sin_grupo:
                for cert in sin_grupo:
                    try:
                        pdf_content = cert.archivo_pdf.read()
                        filename = f"Sin_Grupo/{cert.estudiante.nombre.replace(' ', '_')}_{cert.curso.nombre.replace(' ', '_')}.pdf"
                        zip_master.writestr(filename, pdf_content)
                    except Exception as e:
                        logger.error(f"Error: {e}")
        
        master_zip.seek(0)
        response = HttpResponse(master_zip.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="Certificados_Por_Grupo_{timezone.now().strftime("%Y%m%d")}.zip"'
        
        self.message_user(request, f"✅ Descargados {queryset.count()} certificados de {len(certificados_por_grupo)} grupo(s)", messages.SUCCESS)
        return response
    
    @admin.action(description='📄 Generar PDF Consolidado (Un archivo)')
    def generar_pdf_consolidado(self, request, queryset):
        """Genera un único PDF con todos los certificados seleccionados"""
        from PyPDF2 import PdfMerger
        from django.http import HttpResponse
        import io
        from django.utils import timezone
        
        queryset = queryset.filter(emitido=True, archivo_pdf__isnull=False)
        
        if not queryset.exists():
            self.message_user(request, "⚠️ No hay certificados con PDF", messages.WARNING)
            return
        
        # Crear merger
        merger = PdfMerger()
        
        # Agregar cada certificado
        for cert in queryset:
            try:
                pdf_file = cert.archivo_pdf.open('rb')
                merger.append(pdf_file)
                pdf_file.close()
            except Exception as e:
                logger.error(f"Error agregando certificado {cert.codigo_verificacion}: {e}")
        
        # Guardar PDF consolidado
        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)
        
        # Preparar respuesta
        response = HttpResponse(output.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Certificados_Consolidados_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        
        self.message_user(request, f"✅ Generado PDF consolidado con {queryset.count()} certificado(s)", messages.SUCCESS)
        return response
    
    @admin.action(description='�📧 Enviar certificados por email a clientes')
    def enviar_email_a_clientes(self, request, queryset):
        """Envía los certificados por email al cliente (no al estudiante) usando API"""
        from core.email_service import enviar_certificados_a_cliente
        
        # Filtrar solo certificados con PDF
        queryset = queryset.filter(emitido=True, archivo_pdf__isnull=False)
        
        if not queryset.exists():
            self.message_user(
                request,
                "⚠️ No hay certificados con PDF generado",
                messages.WARNING
            )
            return
        
        # Agrupar certificados por cliente
        certificados_por_cliente = {}
        sin_cliente = []
        
        for certificado in queryset:
            estudiante = certificado.estudiante
            cliente = estudiante.cliente
            
            if cliente and cliente.enviar_certificados_email:
                if cliente.id not in certificados_por_cliente:
                    certificados_por_cliente[cliente.id] = {
                        'cliente': cliente,
                        'certificados': []
                    }
                certificados_por_cliente[cliente.id]['certificados'].append(certificado)
            else:
                sin_cliente.append(certificado)
        
        enviados = 0
        errores = 0
        
        # Enviar emails agrupados por cliente usando el servicio
        for cliente_id, data in certificados_por_cliente.items():
            cliente = data['cliente']
            certificados = data['certificados']
            
            try:
                success = enviar_certificados_a_cliente(cliente, certificados)
                if success:
                    enviados += len(certificados)
                else:
                    errores += len(certificados)
                    
            except Exception as e:
                logger.error(f"❌ Error enviando certificados a {cliente.email}: {e}")
                errores += len(certificados)
        
        # Mensaje de resultado
        if enviados > 0:
            self.message_user(
                request,
                f"✅ {enviados} certificado(s) enviado(s) por email a {len(certificados_por_cliente)} cliente(s)",
                messages.SUCCESS
            )
        
        if sin_cliente:
            self.message_user(
                request,
                f"⚠️ {len(sin_cliente)} certificado(s) sin cliente o con envío deshabilitado",
                messages.WARNING
            )
        
        if errores > 0:
            self.message_user(
                request,
                f"❌ {errores} error(es) al enviar emails",
                messages.ERROR
            )


