from core.admin._common import *  # noqa: F401,F403

# ========================================
# 🤝 ADMIN DE PROSPECTOS B2B (LEADS)
# ========================================

class ProspectoB2BAdmin(admin.ModelAdmin):
    """
    🤝 GESTIÓN DE LEADS B2B
    Prospectos capturados desde WhatsApp (Phase 0 del webhook).
    """
    list_display = ('telefono', 'nombre_contacto', 'empresa', 'email', 'estado_badge', 'origen', 'fecha_captura')
    list_filter = ('estado', 'origen', 'fecha_captura')
    search_fields = ('telefono', 'email', 'empresa', 'nombre_contacto')
    list_per_page = 50
    ordering = ('-fecha_captura',)
    readonly_fields = ('fecha_captura',)
    actions = ['enviar_campana_b2b']
    change_list_template = 'admin/prospectob2b_changelist.html'

    fieldsets = (
        ('📱 Contacto', {
            'fields': ('telefono', 'nombre_contacto', 'email', 'empresa')
        }),
        ('📊 Estado', {
            'fields': ('estado', 'origen', 'fecha_captura', 'notas')
        }),
    )

    def estado_badge(self, obj):
        colores = {
            'nuevo': '#2196f3',
            'contactado': '#ff9800',
            'convertido': '#4caf50',
            'descartado': '#999',
        }
        color = colores.get(obj.estado, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"

    @admin.action(description='📤 Enviar campaña B2B a seleccionados')
    def enviar_campana_b2b(self, request, queryset):
        """Envía una campaña B2B elegida por el admin a los prospectos seleccionados."""
        from core.models import CampanaB2B
        from core.utils import enviar_whatsapp_twilio
        from core.whatsapp_service import enviar_template_twilio

        campanas = CampanaB2B.objects.all().order_by('-fecha_creacion')
        if not campanas.exists():
            self.message_user(request, "❌ No hay campañas B2B creadas. Crea una primero.", level='error')
            return

        # Paso 2: Si el admin ya eligió la campaña, enviar
        if 'campana_id' in request.POST:
            try:
                campana = CampanaB2B.objects.get(id=request.POST['campana_id'])
            except CampanaB2B.DoesNotExist:
                self.message_user(request, "❌ Campaña no encontrada.", level='error')
                return

            enviados = 0
            errores = 0

            for prospecto in queryset:
                try:
                    if campana.twilio_template_sid:
                        variables = {}
                        if prospecto.nombre_contacto:
                            variables['1'] = prospecto.nombre_contacto
                        resultado = enviar_template_twilio(
                            prospecto.telefono,
                            campana.twilio_template_sid,
                            variables=variables if variables else None
                        )
                        if resultado.get('success'):
                            enviados += 1
                        else:
                            errores += 1

                        if campana.url_media and resultado.get('success'):
                            import time
                            time.sleep(1)
                            enviar_whatsapp_twilio(
                                prospecto.telefono,
                                "📄 Adjunto:",
                                media_url=campana.url_media
                            )
                    else:
                        texto = campana.mensaje.replace('{nombre}', prospecto.nombre_contacto or 'Estimado/a')
                        media = campana.url_media or None
                        resultado = enviar_whatsapp_twilio(
                            prospecto.telefono,
                            texto,
                            media_url=media
                        )
                        if resultado.get('success'):
                            enviados += 1
                        else:
                            errores += 1

                    prospecto.estado = 'contactado'
                    prospecto.fecha_ultimo_contacto = timezone.now()
                    prospecto.save()

                except Exception as e:
                    errores += 1
                    import logging
                    logging.getLogger(__name__).error(f"Error enviando a {prospecto.telefono}: {e}")

            campana.total_enviados += enviados
            campana.total_errores += errores
            campana.estado = 'enviada'
            campana.fecha_envio = timezone.now()
            campana.save()

            self.message_user(
                request,
                f"📤 Campaña '{campana.nombre}' enviada: {enviados} exitosos, {errores} errores"
            )
            return

        # Paso 1: Mostrar formulario para elegir campaña
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'admin/elegir_campana_b2b.html', {
            'title': 'Elegir campaña B2B',
            'campanas': campanas,
            'prospectos': queryset,
            'prospectos_ids': ','.join(str(p.pk) for p in queryset),
            'action': 'enviar_campana_b2b',
            'opts': self.model._meta,
        })


# ========================================
# � ADMIN DE CAMPAÑAS B2B
# ========================================

class CampanaB2BAdminForm(forms.ModelForm):
    media_file_upload = forms.FileField(
        label='Subir archivo desde PC',
        required=False,
        help_text='Opcional. Guarda el archivo en storage/S3 y completa URL del PDF/Media.',
    )

    class Meta:
        model = CampanaB2B
        fields = '__all__'

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded_file = self.cleaned_data.get('media_file_upload')
        if uploaded_file:
            instance.url_media = guardar_upload_admin_media(
                uploaded_file,
                carpeta='campanas_b2b',
                prefix='media',
            )
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CampanaB2BAdmin(admin.ModelAdmin):
    """
    📤 CAMPAÑAS B2B — Envío de plantillas/PDF a prospectos sin registrarlos.
    """
    form = CampanaB2BAdminForm
    list_display = ('nombre', 'estado_badge', 'tiene_template', 'tiene_media', 'total_enviados', 'total_errores', 'fecha_creacion')
    list_filter = ('estado',)
    search_fields = ('nombre',)
    readonly_fields = ('total_enviados', 'total_errores', 'fecha_envio')
    ordering = ('-fecha_creacion',)

    fieldsets = (
        ('📤 Campaña', {
            'fields': ('nombre', 'estado')
        }),
        ('💬 Contenido del Mensaje', {
            'fields': ('mensaje', 'twilio_template_sid', 'url_media', 'media_file_upload'),
            'description': '📝 Si especificas un Content SID de Twilio, se usará ese template. Si no, se envía el mensaje de texto. Puedes pegar URL o subir archivo desde PC; el PDF/media se adjunta en ambos casos.'
        }),
        ('📊 Resultados', {
            'fields': ('total_enviados', 'total_errores', 'fecha_envio'),
            'classes': ('collapse',)
        }),
    )

    def estado_badge(self, obj):
        color = '#ffc107' if obj.estado == 'borrador' else '#28a745'
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = "Estado"

    def tiene_template(self, obj):
        if obj.twilio_template_sid:
            return format_html('<span style="color:green;">✅ {}</span>', obj.twilio_template_sid[:15] + '...')
        return format_html('<span style="color:#999;">—</span>')
    tiene_template.short_description = "Template"

    def tiene_media(self, obj):
        if obj.url_media:
            return format_html('<span style="color:green;">📎 Sí</span>')
        return format_html('<span style="color:#999;">—</span>')
    tiene_media.short_description = "Media"


# ========================================
# 📚 ADMIN DE DOCUMENTOS RAG
# ========================================

def _nombre_documento_desde_nombre_archivo(filename: str) -> str:
    """Identificador a partir del archivo subido (sin extensión), máx. 200 caracteres."""
    base = os.path.basename((filename or '').strip())
    stem, _ext = os.path.splitext(base)
    stem = (stem or base or 'documento').strip()
    return stem[:200]


def _nombre_rag_comercial_unico(cliente, canal: str, nombre_base: str, exclude_pk=None):
    """Evita violar unique_together (cliente, canal, nombre)."""
    nombre = nombre_base[:200]
    q = DocumentoRAGComercial.objects.filter(canal=canal, nombre=nombre)
    q = q.filter(cliente__isnull=True) if cliente is None else q.filter(cliente=cliente)
    if exclude_pk:
        q = q.exclude(pk=exclude_pk)
    if not q.exists():
        return nombre
    for i in range(2, 200):
        suf = f'_{i}'
        candidato = (nombre_base[: 200 - len(suf)] + suf)[:200]
        q2 = DocumentoRAGComercial.objects.filter(canal=canal, nombre=candidato)
        q2 = q2.filter(cliente__isnull=True) if cliente is None else q2.filter(cliente=cliente)
        if exclude_pk:
            q2 = q2.exclude(pk=exclude_pk)
        if not q2.exists():
            return candidato
    return (nombre_base[:190] + '_dup')[:200]


def _nombre_rag_curso_unico(curso, nombre_base: str, exclude_pk=None):
    nombre = nombre_base[:200]
    q = DocumentoRAG.objects.filter(curso=curso, nombre=nombre)
    if exclude_pk:
        q = q.exclude(pk=exclude_pk)
    if not q.exists():
        return nombre
    for i in range(2, 200):
        suf = f'_{i}'
        candidato = (nombre_base[: 200 - len(suf)] + suf)[:200]
        q2 = DocumentoRAG.objects.filter(curso=curso, nombre=candidato)
        if exclude_pk:
            q2 = q2.exclude(pk=exclude_pk)
        if not q2.exists():
            return candidato
    return (nombre_base[:190] + '_dup')[:200]


class DocumentoRAGComercialAdminForm(forms.ModelForm):
    archivo_segundo = forms.FileField(
        required=False,
        label='Segundo archivo (opcional)',
        help_text='Mismo cliente, canal y tipo. Se crea otro documento y se indexa en segundo plano.',
    )

    class Meta:
        model = DocumentoRAGComercial
        fields = '__all__'

    def clean(self):
        data = super().clean()
        archivo = data.get('archivo')
        nombre = (data.get('nombre') or '').strip()
        if archivo and not nombre:
            data['nombre'] = _nombre_documento_desde_nombre_archivo(getattr(archivo, 'name', '') or '')
        return data


class DocumentoRAGAdminForm(forms.ModelForm):
    archivo_segundo = forms.FileField(
        required=False,
        label='Segundo archivo (opcional)',
        help_text='Mismo curso y tipo. Se crea otro documento y se indexa en segundo plano.',
    )

    class Meta:
        model = DocumentoRAG
        fields = '__all__'

    def clean(self):
        data = super().clean()
        archivo = data.get('archivo')
        nombre = (data.get('nombre') or '').strip()
        if archivo and not nombre:
            data['nombre'] = _nombre_documento_desde_nombre_archivo(getattr(archivo, 'name', '') or '')
        return data


def _enqueue_indexar_rag_task(model_class_name: str, pk: int):
    """Registra indexación en Celery después del commit (archivo/DB visibles para el worker)."""

    def _run():
        try:
            from core.tasks import indexar_documento_rag_por_id

            indexar_documento_rag_por_id.delay('core', model_class_name, pk)
        except Exception:
            logger.exception('[RAG] Fallo encolando %s id=%s', model_class_name, pk)

    transaction.on_commit(_run)


def _encolar_o_indexar_rag_doc(request, modeladmin, model_class_name: str, obj, show_index_message=True):
    """
    La indexación RAG puede superar el timeout de nginx/ALB; en producción
    se delega a Celery o a un hilo en background si no hay worker Redis.
    """
    pk = obj.pk

    def _run():
        try:
            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                import threading

                def _bg():
                    try:
                        from django.apps import apps

                        Model = apps.get_model('core', model_class_name)
                        doc = Model.objects.filter(pk=pk).first()
                        if doc and getattr(doc, 'archivo', None):
                            doc.indexar()
                    except Exception:
                        logger.exception('[RAG] Indexación background falló %s id=%s', model_class_name, pk)

                threading.Thread(target=_bg, daemon=True, name=f'rag-idx-{pk}').start()
            else:
                from core.tasks import indexar_documento_rag_por_id

                indexar_documento_rag_por_id.delay('core', model_class_name, pk)
        except Exception:
            logger.exception('[RAG] Fallo encolando %s id=%s', model_class_name, pk)

    transaction.on_commit(_run)
    if show_index_message:
        modeladmin.message_user(
            request,
            'La indexación RAG se ejecuta en segundo plano; actualiza el listado en unos minutos para ver el estado.',
            messages.INFO,
        )
    return None


def _encolar_zip_rag_comercial(
    storage_path: str,
    cliente_id,
    canal: str,
    tipo: str,
    descripcion: str,
    user_id,
) -> None:
    """ZIP → worker Celery; si no hay broker, hilo en background (evita 504 en EB)."""
    args = (storage_path, cliente_id, canal, tipo, descripcion, user_id)

    def _run():
        import threading

        from core.tasks import procesar_zip_rag_comercial

        def _bg():
            try:
                procesar_zip_rag_comercial.apply(args=args)
            except Exception:
                logger.exception('[RAG comercial] Procesamiento ZIP en background falló')

        try:
            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                threading.Thread(target=_bg, daemon=True, name='rag-zip').start()
            else:
                procesar_zip_rag_comercial.delay(*args)
        except Exception:
            logger.warning('[RAG comercial] Celery no disponible; ZIP en hilo background')
            threading.Thread(target=_bg, daemon=True, name='rag-zip').start()

    transaction.on_commit(_run)


# Subida masiva solo RAG comercial (varios archivos → un DocumentoRAGComercial por archivo).
RAG_COMERCIAL_SUBIDA_MASIVA_MIN = 2
# Subida masiva solo RAG comercial (varios archivos → un DocumentoRAGComercial por archivo).
RAG_COMERCIAL_SUBIDA_MASIVA_MAX = 50
RAG_COMERCIAL_ZIP_MAX_BYTES = 150 * 1024 * 1024  # 150 MB
RAG_COMERCIAL_ZIP_MAX_FILES = 100
_RAG_COMERCIAL_EXT_OK = {'.pdf', '.docx', '.txt', '.xlsx', '.xlsm', '.xls'}


def _extension_archivo_comercial_ok(nombre: str) -> bool:
    ext = os.path.splitext((nombre or '').lower())[1]
    return ext in _RAG_COMERCIAL_EXT_OK


class MetaMetricaEmpresaAdmin(admin.ModelAdmin):
    list_display = (
        "cliente", "curso", "meta_finalizacion_porcentaje",
        "meta_inicio_porcentaje", "meta_max_no_iniciados_porcentaje", "activa",
    )
    list_filter = ("activa", "cliente")
    search_fields = ("cliente__nombre", "curso__nombre")
    autocomplete_fields = ("cliente", "curso")


class MetaMetricaNatiAdmin(admin.ModelAdmin):
    list_display = ("cliente", "meta_lectura_porcentaje", "meta_respuesta_porcentaje", "activa")
    list_filter = ("activa",)
    search_fields = ("cliente__nombre",)
    autocomplete_fields = ("cliente",)


class DocumentoRAGAdmin(admin.ModelAdmin):
    """
    📚 GESTIÓN DE DOCUMENTOS RAG — Base de Conocimiento para Agentes IA
    Multi-Tenant: cada documento está aislado por Cliente + Curso.
    """
    form = DocumentoRAGAdminForm
    list_display = ('nombre', 'curso_link', 'cliente_display', 'tipo_badge', 'estado_rag_badge', 'chunks_indexados', 'fecha_subida')
    list_filter = ('estado', 'tipo', 'curso__cliente', 'curso')
    search_fields = ('nombre', 'descripcion', 'curso__nombre', 'curso__cliente__nombre')
    list_per_page = 50
    ordering = ('-fecha_subida',)
    readonly_fields = ('estado', 'chunks_indexados', 'fecha_subida', 'fecha_indexado', 'subido_por')
    actions = ['indexar_seleccionados', 'reindexar_seleccionados', 'eliminar_del_rag']

    fieldsets = (
        ('📄 Documento', {
            'fields': ('curso', 'nombre', 'archivo', 'archivo_segundo', 'tipo', 'descripcion'),
            'description': 'Si dejás "Nombre" vacío al subir archivo, se usa el nombre del archivo (sin extensión). Podés adjuntar un segundo archivo en la misma carga.',
        }),
        ('🤖 Estado RAG', {
            'fields': ('estado', 'chunks_indexados', 'fecha_subida', 'fecha_indexado', 'subido_por'),
            'description': 'Estado de indexación en la base de datos vectorial. Los documentos indexados son usados por los agentes IA.'
        }),
    )

    def curso_link(self, obj):
        url = reverse('admin:core_curso_change', args=[obj.curso_id])
        return format_html('<a href="{}">{}</a>', url, obj.curso.nombre)
    curso_link.short_description = "Curso"

    def cliente_display(self, obj):
        if obj.curso.cliente:
            return obj.curso.cliente.nombre
        return format_html('<span style="color:#999;">General (eki)</span>')
    cliente_display.short_description = "🏢 Cliente"

    def tipo_badge(self, obj):
        colores = {'contenido': '#2196F3', 'manual': '#9C27B0', 'faq': '#FF9800', 'guia': '#4CAF50', 'normativa': '#607D8B'}
        color = colores.get(obj.tipo, '#999')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_tipo_display()
        )
    tipo_badge.short_description = "Tipo"

    def estado_rag_badge(self, obj):
        colores = {'pendiente': '#ffc107', 'indexado': '#28a745', 'error': '#dc3545'}
        color = colores.get(obj.estado, '#6c757d')
        label = obj.get_estado_display()
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:12px;font-size:11px;">{}</span>',
            color, label
        )
    estado_rag_badge.short_description = "Estado RAG"

    def save_model(self, request, obj, form, change):
        arch2 = form.cleaned_data.get('archivo_segundo') if form and hasattr(form, 'cleaned_data') else None
        if obj.archivo and (not obj.nombre or not str(obj.nombre).strip()):
            obj.nombre = _nombre_documento_desde_nombre_archivo(obj.archivo.name)
        if obj.curso_id and obj.nombre:
            obj.nombre = _nombre_rag_curso_unico(obj.curso, obj.nombre, exclude_pk=obj.pk if change else None)
        if not obj.subido_por_id:
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)
        if obj.estado == 'pendiente' and obj.archivo:
            _encolar_o_indexar_rag_doc(request, self, 'DocumentoRAG', obj)
        if arch2:
            n2 = _nombre_documento_desde_nombre_archivo(arch2.name)
            n2 = _nombre_rag_curso_unico(obj.curso, n2)
            doc2 = DocumentoRAG(
                curso=obj.curso,
                nombre=n2,
                archivo=arch2,
                tipo=obj.tipo,
                descripcion=obj.descripcion or '',
                subido_por=request.user,
                estado='pendiente',
            )
            doc2.save()
            _encolar_o_indexar_rag_doc(request, self, 'DocumentoRAG', doc2)
            self.message_user(
                request,
                f'Se creó también el documento «{n2}» en el mismo curso (indexación en segundo plano).',
                messages.SUCCESS,
            )

    @admin.action(description='🤖 Indexar documentos seleccionados en RAG')
    def indexar_seleccionados(self, request, queryset):
        queued = 0
        for doc in queryset.filter(estado='pendiente'):
            if not doc.archivo:
                continue
            _encolar_o_indexar_rag_doc(request, self, 'DocumentoRAG', doc, show_index_message=False)
            queued += 1
        self.message_user(
            request,
            f'✅ {queued} en cola (segundo plano). Actualice el listado en unos minutos.'
            if queued else 'Nada que indexar.',
        )

    @admin.action(description='🔄 Re-indexar documentos seleccionados')
    def reindexar_seleccionados(self, request, queryset):
        queued = 0
        for doc in queryset:
            doc.estado = 'pendiente'
            doc.save(update_fields=['estado'])
            if not doc.archivo:
                continue
            _encolar_o_indexar_rag_doc(request, self, 'DocumentoRAG', doc, show_index_message=False)
            queued += 1
        self.message_user(
            request,
            f'✅ {queued} re-indexaciones en cola (segundo plano).' if queued else 'Listo.',
        )

    @admin.action(description='🗑️ Eliminar del RAG (sin borrar archivo)')
    def eliminar_del_rag(self, request, queryset):
        from core.rag_manager import rag_manager
        for doc in queryset:
            rag_manager.eliminar_documento(doc.cliente_id, doc.curso_id, doc.nombre)
            doc.estado = 'pendiente'
            doc.chunks_indexados = 0
            doc.save(update_fields=['estado', 'chunks_indexados'])
        self.message_user(request, f"✅ {queryset.count()} documentos eliminados del índice RAG.")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = '📚 Documentos RAG — Base de Conocimiento para Agentes IA'
        return super().changelist_view(request, extra_context)


@admin.register(ProductoCatalogo)
class ProductoCatalogoAdmin(admin.ModelAdmin):
    """Recomendaciones Nat (dosis, link, problema). No es la lista de precios SKU."""

    list_display = (
        'nombre', 'sku', 'cliente', 'categoria',
        'cultivos_objetivo', 'precio_cop', 'unidad', 'activo',
    )
    list_filter = ('cliente', 'categoria', 'activo')
    search_fields = ('nombre', 'sku', 'descripcion', 'problema_que_resuelve', 'ingrediente_activo')
    list_editable = ('activo',)
    readonly_fields = ('fecha_actualizacion',)
    fieldsets = (
        ('Identificación', {
            'fields': ('cliente', 'nombre', 'sku', 'categoria', 'cultivos_objetivo', 'activo'),
        }),
        ('Foto', {
            'fields': ('imagen',),
        }),
        ('Información técnica', {
            'fields': ('descripcion', 'problema_que_resuelve', 'ingrediente_activo', 'dosis'),
        }),
        ('Información comercial', {
            'fields': ('precio_cop', 'unidad', 'url_producto'),
        }),
        ('Auditoría', {
            'fields': ('fecha_actualizacion',),
            'classes': ('collapse',),
        }),
    )
    actions = ['desactivar_productos', 'activar_productos']

    @admin.action(description='Desactivar productos seleccionados')
    def desactivar_productos(self, request, queryset):
        count = queryset.update(activo=False)
        self.message_user(request, f'{count} productos desactivados.')

    @admin.action(description='Activar productos seleccionados')
    def activar_productos(self, request, queryset):
        count = queryset.update(activo=True)
        self.message_user(request, f'{count} productos activados.')


@admin.register(ProductoComercial)
class ProductoComercialAdmin(admin.ModelAdmin):
    """Lista de precios SKU para Nat (consultas de precio). Distinto de ProductoCatalogo (recomendaciones)."""

    change_list_template = 'admin/productocomercial_changelist.html'
    list_display = (
        'sku', 'nombre', 'presentacion', 'stock', 'precio', 'moneda',
        'cliente', 'categoria', 'activo', 'fecha_actualizacion',
    )
    list_filter = ('activo', 'cliente', 'categoria', 'moneda')
    search_fields = ('sku', 'nombre', 'categoria', 'notas')
    list_editable = ('precio', 'activo')
    ordering = ('-fecha_actualizacion',)
    list_per_page = 50

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                'importar-precios/',
                self.admin_site.admin_view(self.importar_precios_view),
                name='%s_%s_importar_precios' % info,
            ),
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        opts = self.model._meta
        extra_context['title'] = '💰 Precios comerciales — Nat (Postgres)'
        extra_context['importar_precios_url'] = reverse(
            'admin:%s_%s_importar_precios' % (opts.app_label, opts.model_name)
        )
        return super().changelist_view(request, extra_context)

    def importar_precios_view(self, request):
        import os
        import tempfile

        from django.core.exceptions import PermissionDenied

        from core.precios_import import importar_precios_desde_archivo

        if not self.has_add_permission(request):
            raise PermissionDenied

        opts = self.model._meta
        changelist_url = reverse('admin:%s_%s_changelist' % (opts.app_label, opts.model_name))
        clientes = Cliente.objects.filter(activo=True).order_by('nombre')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Importar precios comerciales (Excel → Postgres)',
            'opts': opts,
            'changelist_url': changelist_url,
            'clientes': clientes,
            'preview': None,
            'cliente_sel': '',
            'vigencia_desde': '',
            'vigencia_hasta': '',
            'desactivar_ausentes': False,
        }

        if request.method != 'POST':
            return render(request, 'admin/importar_precios_comercial.html', context)

        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Seleccioná un archivo Excel o JSON.')
            return render(request, 'admin/importar_precios_comercial.html', context)

        cliente_id_raw = (request.POST.get('cliente') or '').strip()
        cliente_id = int(cliente_id_raw) if cliente_id_raw else None
        context['cliente_sel'] = cliente_id_raw
        context['vigencia_desde'] = request.POST.get('vigencia_desde') or ''
        context['vigencia_hasta'] = request.POST.get('vigencia_hasta') or ''
        context['desactivar_ausentes'] = request.POST.get('desactivar_ausentes') == '1'

        ext = os.path.splitext(archivo.name or '')[1].lower()
        if ext not in {'.xlsx', '.xlsm', '.xls', '.json'}:
            messages.error(request, 'Formato no soportado. Use .xlsx, .xlsm, .xls o .json')
            return render(request, 'admin/importar_precios_comercial.html', context)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in archivo.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            dry_run = (request.POST.get('accion') or '').strip().lower() == 'vista previa'
            result = importar_precios_desde_archivo(
                tmp_path,
                cliente_id=cliente_id,
                desactivar_ausentes=context['desactivar_ausentes'],
                dry_run=dry_run,
                vigencia_desde=context['vigencia_desde'] or None,
                vigencia_hasta=context['vigencia_hasta'] or None,
            )

            if result.errores:
                messages.error(
                    request,
                    'Errores de validación:\n' + '\n'.join(result.errores[:12]),
                )
                context['preview'] = result
                return render(request, 'admin/importar_precios_comercial.html', context)

            if dry_run:
                context['preview'] = result
                messages.info(
                    request,
                    f'Vista previa: {result.total_validos} producto(s) válido(s) para «{result.cliente_nombre}».',
                )
                return render(request, 'admin/importar_precios_comercial.html', context)

            messages.success(
                request,
                f'Importación lista: {result.creados} creados, {result.actualizados} actualizados'
                + (f', {result.desactivados} desactivados' if result.desactivados else '')
                + f' — cliente «{result.cliente_nombre}».',
            )
            return redirect(changelist_url)
        except (ValueError, FileNotFoundError) as e:
            messages.error(request, str(e))
            return render(request, 'admin/importar_precios_comercial.html', context)
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


class DocumentoRAGComercialAdmin(admin.ModelAdmin):
    """Legacy RAG comercial (admin). Preferir Portal → Biblioteca para material nuevo."""

    form = DocumentoRAGComercialAdminForm
    change_list_template = 'admin/documentoragcomercial_changelist.html'
    list_display = (
        'nombre',
        'cliente_display',
        'canal',
        'tipo_badge',
        'estado_rag_badge',
        'chunks_indexados',
        'fecha_subida',
    )
    list_filter = ('estado', 'tipo', 'canal', 'cliente')
    search_fields = ('nombre', 'descripcion', 'cliente__nombre', 'error_indexacion')
    list_per_page = 50
    ordering = ('-fecha_subida',)
    readonly_fields = (
        'estado', 'chunks_indexados', 'error_indexacion',
        'fecha_subida', 'fecha_indexado', 'subido_por',
    )
    actions = [
        'indexar_seleccionados',
        'reindexar_seleccionados',
        'eliminar_del_rag',
        'importar_precios_a_catalogo',
    ]

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                'subida-masiva/',
                self.admin_site.admin_view(self.subida_masiva_view),
                name='%s_%s_subida_masiva' % info,
            ),
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        opts = self.model._meta
        extra_context['subida_masiva_max'] = RAG_COMERCIAL_SUBIDA_MASIVA_MAX
        extra_context['subida_masiva_url'] = reverse(
            'admin:%s_%s_subida_masiva' % (opts.app_label, opts.model_name)
        )
        return super().changelist_view(request, extra_context)

    fieldsets = (
        ('📄 Documento Comercial', {
            'fields': ('cliente', 'canal', 'nombre', 'archivo', 'archivo_segundo', 'tipo', 'descripcion'),
            'description': 'Si dejás "Nombre" vacío al subir archivo, se usa el nombre del archivo (sin extensión). Podés adjuntar un segundo archivo en la misma carga.',
        }),
        ('🤖 Estado RAG Comercial', {
            'fields': ('estado', 'chunks_indexados', 'fecha_subida', 'fecha_indexado', 'subido_por'),
            'description': 'Estos documentos alimentan el bot comercial y NO el bot educativo de cursos.'
        }),
    )

    def cliente_display(self, obj):
        if obj.cliente:
            return obj.cliente.nombre
        return format_html('<span style="color:#999;">General</span>')
    cliente_display.short_description = '🏢 Cliente'

    def tipo_badge(self, obj):
        colores = {
            'producto': '#0ea5e9',
            'precio': '#ef4444',
            'informe_tecnico': '#475569',
            'faq': '#f59e0b',
            'politica': '#64748b',
            'promo': '#10b981',
            'general': '#3b82f6',
        }
        color = colores.get(obj.tipo, '#999')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:12px;font-size:11px;">{}</span>',
            color,
            obj.get_tipo_display(),
        )
    tipo_badge.short_description = 'Tipo'

    def estado_rag_badge(self, obj):
        colores = {'pendiente': '#ffc107', 'indexado': '#28a745', 'error': '#dc3545'}
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:12px;font-size:11px;">{}</span>',
            color,
            obj.get_estado_display(),
        )
    estado_rag_badge.short_description = 'Estado RAG'

    def subida_masiva_view(self, request):
        """Varios archivos → un documento comercial por archivo; el nombre sale del nombre del archivo."""
        from django.core.exceptions import PermissionDenied

        if not self.has_add_permission(request):
            raise PermissionDenied

        opts = self.model._meta
        changelist_url = reverse('admin:%s_%s_changelist' % (opts.app_label, opts.model_name))

        clientes = Cliente.objects.filter(activo=True).order_by('nombre')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Subida masiva — RAG comercial',
            'opts': opts,
            'changelist_url': changelist_url,
            'clientes': clientes,
            'canal_choices': DocumentoRAGComercial.CANAL_CHOICES,
            'tipo_choices': DocumentoRAGComercial.TIPO_CHOICES,
            'min_files': RAG_COMERCIAL_SUBIDA_MASIVA_MIN,
            'max_files': RAG_COMERCIAL_SUBIDA_MASIVA_MAX,
            'ext_help': ', '.join(sorted(_RAG_COMERCIAL_EXT_OK)),
        }

        if request.method != 'POST':
            return render(request, 'admin/subida_masiva_rag_comercial.html', context)

        canal = (request.POST.get('canal') or 'bot_comercial').strip()
        tipo = (request.POST.get('tipo') or 'general').strip()
        descripcion = (request.POST.get('descripcion') or '').strip()
        cliente_id = request.POST.get('cliente') or ''
        cliente = None
        if cliente_id:
            try:
                cliente = Cliente.objects.get(pk=int(cliente_id))
            except (ValueError, TypeError, Cliente.DoesNotExist):
                messages.error(request, 'Cliente inválido.')
                return render(request, 'admin/subida_masiva_rag_comercial.html', context)

        valid_canal = {c for c, _ in DocumentoRAGComercial.CANAL_CHOICES}
        if canal not in valid_canal:
            messages.error(request, 'Canal inválido.')
            return render(request, 'admin/subida_masiva_rag_comercial.html', context)

        valid_tipo = {t for t, _ in DocumentoRAGComercial.TIPO_CHOICES}
        if tipo not in valid_tipo:
            messages.error(request, 'Tipo de documento inválido.')
            return render(request, 'admin/subida_masiva_rag_comercial.html', context)

        archivo_zip = request.FILES.get('archivo_zip')
        archivos = request.FILES.getlist('archivos')

        if archivo_zip:
            import uuid

            from django.core.files.storage import default_storage

            if not (archivo_zip.name or '').lower().endswith('.zip'):
                messages.error(request, 'El archivo debe ser un .zip')
                return render(request, 'admin/subida_masiva_rag_comercial.html', context)
            if archivo_zip.size > RAG_COMERCIAL_ZIP_MAX_BYTES:
                messages.error(
                    request,
                    f'ZIP demasiado grande (máx {RAG_COMERCIAL_ZIP_MAX_BYTES // (1024 * 1024)} MB).',
                )
                return render(request, 'admin/subida_masiva_rag_comercial.html', context)
            storage_path = default_storage.save(
                f'rag_zip_uploads/{uuid.uuid4().hex}.zip',
                archivo_zip,
            )
            _encolar_zip_rag_comercial(
                storage_path,
                cliente.pk if cliente else None,
                canal,
                tipo,
                descripcion,
                request.user.pk,
            )
            messages.success(
                request,
                f'ZIP recibido. Se procesará en segundo plano (hasta {RAG_COMERCIAL_ZIP_MAX_FILES} archivos válidos). '
                'Refrescá el listado en unos minutos.',
            )
            return redirect(changelist_url)

        n = len(archivos)
        if n < RAG_COMERCIAL_SUBIDA_MASIVA_MIN:
            messages.error(
                request,
                f'Seleccioná al menos {RAG_COMERCIAL_SUBIDA_MASIVA_MIN} archivos, o subí un ZIP.',
            )
            return render(request, 'admin/subida_masiva_rag_comercial.html', context)
        if n > RAG_COMERCIAL_SUBIDA_MASIVA_MAX:
            messages.error(
                request,
                f'Máximo {RAG_COMERCIAL_SUBIDA_MASIVA_MAX} archivos por carga. Dividí en varias tandas.',
            )
            return render(request, 'admin/subida_masiva_rag_comercial.html', context)

        rechazados = []
        for f in archivos:
            if not _extension_archivo_comercial_ok(getattr(f, 'name', '') or ''):
                rechazados.append(getattr(f, 'name', '?'))
        if rechazados:
            messages.error(
                request,
                'Extensión no permitida en: ' + ', '.join(rechazados[:12])
                + (f' (+{len(rechazados) - 12} más)' if len(rechazados) > 12 else '')
                + f'. Permitidos: {context["ext_help"]}',
            )
            return render(request, 'admin/subida_masiva_rag_comercial.html', context)

        creados = []
        try:
            with transaction.atomic():
                for f in archivos:
                    nombre = _nombre_documento_desde_nombre_archivo(f.name)
                    nombre = _nombre_rag_comercial_unico(cliente, canal, nombre)
                    doc = DocumentoRAGComercial(
                        cliente=cliente,
                        canal=canal,
                        nombre=nombre,
                        archivo=f,
                        tipo=tipo,
                        descripcion=descripcion,
                        subido_por=request.user,
                        estado='pendiente',
                    )
                    doc.save()
                    creados.append(doc)
        except Exception:
            logger.exception('[RAG comercial] Subida masiva falló')
            messages.error(request, 'No se pudieron guardar los documentos. Revisá los logs o probá con menos archivos.')
            return render(request, 'admin/subida_masiva_rag_comercial.html', context)

        for i, doc in enumerate(creados):
            if doc.estado == 'pendiente' and doc.archivo:
                try:
                    from core.tasks import indexar_documento_rag_por_id

                    indexar_documento_rag_por_id.apply_async(
                        ('core', 'DocumentoRAGComercial', doc.pk),
                        countdown=min(i * 12, 900),
                    )
                except Exception:
                    _encolar_o_indexar_rag_doc(
                        request, self, 'DocumentoRAGComercial', doc, show_index_message=False
                    )

        messages.success(
            request,
            f'Se crearon {len(creados)} documentos comerciales. El título de cada uno es el nombre del archivo '
            '(ajustado si ya existía). La indexación corre en segundo plano; refrescá el listado en unos minutos.',
        )
        return redirect(changelist_url)

    def save_model(self, request, obj, form, change):
        arch2 = form.cleaned_data.get('archivo_segundo') if form and hasattr(form, 'cleaned_data') else None
        if obj.archivo and (not obj.nombre or not str(obj.nombre).strip()):
            obj.nombre = _nombre_documento_desde_nombre_archivo(obj.archivo.name)
        obj.nombre = _nombre_rag_comercial_unico(obj.cliente, obj.canal, obj.nombre, exclude_pk=obj.pk if change else None)
        if not obj.subido_por_id:
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)
        if obj.estado == 'pendiente' and obj.archivo:
            _encolar_o_indexar_rag_doc(request, self, 'DocumentoRAGComercial', obj)
        if arch2:
            n2 = _nombre_documento_desde_nombre_archivo(arch2.name)
            n2 = _nombre_rag_comercial_unico(obj.cliente, obj.canal, n2)
            doc2 = DocumentoRAGComercial(
                cliente=obj.cliente,
                canal=obj.canal,
                nombre=n2,
                archivo=arch2,
                tipo=obj.tipo,
                descripcion=obj.descripcion or '',
                subido_por=request.user,
                estado='pendiente',
            )
            doc2.save()
            _encolar_o_indexar_rag_doc(request, self, 'DocumentoRAGComercial', doc2)
            self.message_user(
                request,
                f'Se creó también el documento comercial «{n2}» (indexación en segundo plano).',
                messages.SUCCESS,
            )

    @admin.action(description='🤖 Indexar documentos comerciales seleccionados')
    def indexar_seleccionados(self, request, queryset):
        queued = 0
        for doc in queryset.filter(estado='pendiente'):
            if not doc.archivo:
                continue
            _encolar_o_indexar_rag_doc(
                request, self, 'DocumentoRAGComercial', doc, show_index_message=False,
            )
            queued += 1
        self.message_user(
            request,
            f'✅ {queued} en cola (segundo plano). Actualice el listado en unos minutos.'
            if queued else 'Nada que indexar.',
        )

    @admin.action(description='🔄 Re-indexar documentos comerciales seleccionados')
    def reindexar_seleccionados(self, request, queryset):
        queued = 0
        for doc in queryset:
            doc.estado = 'pendiente'
            doc.save(update_fields=['estado'])
            if not doc.archivo:
                continue
            _encolar_o_indexar_rag_doc(
                request, self, 'DocumentoRAGComercial', doc, show_index_message=False,
            )
            queued += 1
        self.message_user(
            request,
            f'✅ {queued} re-indexaciones en cola (segundo plano).' if queued else 'Listo.',
        )

    @admin.action(description='📥 Importar precios a catálogo (Excel → Postgres)')
    def importar_precios_a_catalogo(self, request, queryset):
        from core.precios_import import importar_precios_desde_documento_rag

        ok = err = 0
        for doc in queryset:
            try:
                result = importar_precios_desde_documento_rag(doc)
                if result.errores:
                    err += 1
                    self.message_user(
                        request,
                        f'«{doc.nombre}»: ' + '; '.join(result.errores[:3]),
                        level=messages.ERROR,
                    )
                    continue
                ok += 1
                self.message_user(
                    request,
                    f'«{doc.nombre}»: {result.creados} creados, {result.actualizados} actualizados '
                    f'(cliente «{result.cliente_nombre}»).',
                    level=messages.SUCCESS,
                )
            except (ValueError, FileNotFoundError) as e:
                err += 1
                self.message_user(request, f'«{doc.nombre}»: {e}', level=messages.ERROR)
        if ok and not err:
            self.message_user(request, f'✅ {ok} lista(s) importada(s) al catálogo de precios.', level=messages.SUCCESS)

    @admin.action(description='🗑️ Eliminar del RAG comercial (sin borrar archivo)')
    def eliminar_del_rag(self, request, queryset):
        from core.rag_comercial_manager import rag_comercial_manager

        for doc in queryset:
            rag_comercial_manager.eliminar_documento(doc.cliente_scope_id, doc.canal, doc.nombre)
            doc.estado = 'pendiente'
            doc.chunks_indexados = 0
            doc.save(update_fields=['estado', 'chunks_indexados'])
        self.message_user(request, f"✅ {queryset.count()} documentos eliminados del índice comercial.")

