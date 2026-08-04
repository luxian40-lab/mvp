from core.admin._common import *  # noqa: F401,F403
from core.orden_bloques import (
    intercambiar_orden,
    preparar_ordenes_temporales,
    renumerar_orden_1_based,
)

# ==========================================
# SISTEMA EDUCATIVO - ADMINISTRACIÓN
# ==========================================

# Alta de módulo: 1 sección + N microcontenidos vacíos (inactivos hasta completar).
MODULO_ALTA_PASOS_PLANTILLA = 3


def _botones_mover_bloque(obj, kind: str):
    """Enlaces ↑↓ nativos (Unfold): solo si el registro ya tiene PK."""
    if not obj or not obj.pk or not getattr(obj, 'modulo_id', None):
        return format_html(
            '<span style="color:#94a3b8;font-size:12px;">Guarde para reordenar</span>'
        )
    up = reverse(
        'admin:core_modulo_mover_bloque',
        args=[obj.modulo_id, kind, obj.pk, 'up'],
    )
    down = reverse(
        'admin:core_modulo_mover_bloque',
        args=[obj.modulo_id, kind, obj.pk, 'down'],
    )
    return format_html(
        '<span class="eki-orden-btns" style="display:inline-flex;gap:4px;align-items:center;">'
        '<a class="button" href="{}" title="Subir" style="padding:2px 8px;min-width:2rem;text-align:center;">↑</a>'
        '<a class="button" href="{}" title="Bajar" style="padding:2px 8px;min-width:2rem;text-align:center;">↓</a>'
        '<span style="color:#6b6575;font-size:12px;margin-left:4px;">#{}</span>'
        '</span>',
        up,
        down,
        obj.orden,
    )


def sembrar_plantilla_modulo(modulo, *, n_pasos: int = MODULO_ALTA_PASOS_PLANTILLA) -> dict:
    """
    Tras el alta: garantiza 1 sección y N microcontenidos vacíos (activo=False).
    No pisa secciones/pasos que el operador ya haya cargado en el mismo POST.
    """
    created = {'seccion': False, 'pasos': 0}
    if not modulo or not modulo.pk:
        return created

    seccion = modulo.secciones.order_by('orden', 'id').first()
    if seccion is None:
        seccion = SeccionModulo.objects.create(
            modulo=modulo,
            orden=1,
            titulo='Bloque 1',
            activa=True,
        )
        created['seccion'] = True

    if modulo.pasos.exists():
        return created

    for i in range(1, max(1, int(n_pasos)) + 1):
        PasoModulo.objects.create(
            modulo=modulo,
            seccion=seccion,
            orden=i,
            titulo=f'Microcontenido {i}',
            contenido='',
            activo=False,
            requiere_listo_para_avanzar=True,
        )
        created['pasos'] += 1
    return created




class ModuloInline(admin.TabularInline):
    """Módulos dentro del curso"""
    model = Modulo
    extra = 1
    fields = ('numero', 'titulo', 'descripcion', 'duracion_dias')
    ordering = ['numero']


class DocumentoRAGInline(admin.StackedInline):
    """Documentos RAG para la base de conocimiento IA del curso"""
    model = DocumentoRAG
    extra = 0
    verbose_name = '📄 Documento RAG'
    verbose_name_plural = 'DOCUMENTOS RAG — Base de Conocimiento para Agentes IA'
    readonly_fields = ('estado_badge', 'chunks_indexados', 'fecha_subida', 'fecha_indexado')
    fields = ('nombre', 'archivo', 'tipo', 'descripcion', 'estado_badge', 'chunks_indexados', 'fecha_subida', 'fecha_indexado')

    def estado_badge(self, obj):
        if not obj.pk:
            return '-'
        colors = {'pendiente': '#ffc107', 'indexado': '#28a745', 'error': '#dc3545'}
        color = colors.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:12px;font-size:11px;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado RAG'


class PreguntaAbiertaFinalInline(admin.TabularInline):
    """Preguntas abiertas finales dentro del curso (máximo 3)."""
    model = PreguntaAbiertaFinalCurso
    extra = 1
    max_num = 3
    fields = ('orden', 'pregunta', 'activa')
    ordering = ('orden', 'id')
    verbose_name = '📝 Pregunta Abierta Final'
    verbose_name_plural = 'PREGUNTAS ABIERTAS FINALES (MAX 3)'


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    """Administración de cursos"""
    change_form_template = 'admin/core/curso/change_form.html'
    # Listado limpio P1: ≤6 columnas (RAG/GEI/IA/orden → ficha o acciones).
    list_display = (
        'nombre',
        'cliente_nombre',
        'total_modulos_display',
        'activo',
        'visible_en_aula',
        'visible_en_studio',
    )
    list_filter = (
        'activo', 'visible_en_studio', 'visible_en_aula', 'cliente',
        'usar_gamificacion', 'usar_agentes_ia', 'tiene_formulario_gei',
    )
    search_fields = ('nombre', 'descripcion', 'cliente__nombre')
    list_editable = ()
    inlines = [ModuloInline, DocumentoRAGInline, PreguntaAbiertaFinalInline]
    actions = [
        'ver_todos_modulos', 'indexar_documentos_rag', 'indexar_contenido_modulos',
        'activar_cursos', 'desactivar_cursos', 'copiar_a_otro_cliente', 'copiar_a_analytics_pruebas',
    ]
    # change_list_template = 'admin/curso_changelist.html'  # Eliminado para usar el template estándar de Django
    
    fieldsets = (
        ('Datos del curso', {
            'fields': (
                'nombre', 'descripcion', 'cliente', 'duracion_semanas',
                'activo', 'visible_en_studio', 'visible_en_aula', 'orden',
            ),
        }),
        ('Ritmo drip y acceso', {
            'classes': ('collapse',),
            'fields': (
                'dias_espera_entre_modulos',
                'usar_gamificacion',
                'habilitar_pregunta_abierta_final',
            ),
            'description': mark_safe(
                '<p><strong>0</strong> = avance inmediato con <em>listo</em>. '
                '<strong>&gt; 0</strong> = días de espera entre módulos.</p>'
                '<p>Override por cliente: tabla <em>Ritmo drip por curso</em> en la ficha Cliente.</p>'
            ),
        }),
        ('IA y retos', {
            'classes': ('collapse',),
            'fields': (
                'usar_agentes_ia',
                'nombre_agente_tutor',
                'nombre_agente_asistente',
                'preguntas_ejemplo_ia',
            ),
            'description': mark_safe(
                '<p>Retos Darío/Claudia, nombres de agentes (override) y preguntas ejemplo para el tutor.</p>'
                '<p>Si los nombres van vacíos, se usan los del Cliente o los por defecto.</p>'
            ),
        }),
        ('GEI y WhatsApp', {
            'classes': ('collapse',),
            'fields': ('tiene_formulario_gei', 'enlace_grupo_whatsapp'),
            'description': mark_safe(
                '<p>Recolección GEI al completar el módulo disparador (Formulario → Tipos de formulario). '
                '<a href="/admin/gei/panel/" target="_blank">Panel GEI</a></p>'
            ),
        }),
    )
    
    def cliente_nombre(self, obj):
        """Muestra si es curso específico de un cliente"""
        if obj.cliente:
            return obj.cliente.nombre
        return format_html('<span style="color:#999;font-style:italic;">General (eki)</span>')
    cliente_nombre.short_description = "Organización"
    
    def total_modulos_display(self, obj):
        count = obj.modulos.count()
        return format_html(
            '<span style="font-variant-numeric:tabular-nums;">{}</span>',
            count
        )
    total_modulos_display.short_description = "Módulos"
    
    def ver_modulos_link(self, obj):
        """Link para ver todos los módulos del curso"""
        url = f"/admin/core/modulo/?curso__id__exact={obj.id}"
        count = obj.modulos.count()
        
        # Contar archivos multimedia totales
        from django.db.models import Count
        total_archivos = ArchivoModulo.objects.filter(modulo__curso=obj, activo=True).count()
        
        html = f'<a href="{url}" style="color:#2196F3;">📋 {count} módulo(s)</a>'
        if total_archivos > 0:
            html += f' <span style="color:#999;font-size:11px;">• {total_archivos} archivos</span>'
        return format_html(html)
    ver_modulos_link.short_description = "Gestión"

    def docs_rag_count(self, obj):
        """Muestra cantidad de documentos RAG indexados"""
        total = obj.documentos_rag.count()
        indexados = obj.documentos_rag.filter(estado='indexado').count()
        if total == 0:
            return format_html('<span style="color:#999;font-size:11px;">Sin docs</span>')
        color = '#28a745' if indexados == total else '#ffc107'
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:4px;font-size:11px;">'
            '📚 {}/{}</span>',
            color, indexados, total
        )
    docs_rag_count.short_description = "RAG"

    @admin.action(description='🤖 Indexar documentos RAG de cursos seleccionados')
    def indexar_documentos_rag(self, request, queryset):
        """Encola indexación RAG (nunca bloquea el request HTTP)."""
        from core.admin.commercial import _encolar_o_indexar_rag_doc

        queued = 0
        for curso in queryset:
            for doc in curso.documentos_rag.filter(estado__in=['pendiente', 'error']):
                if not doc.archivo:
                    continue
                doc.estado = 'pendiente'
                doc.save(update_fields=['estado'])
                _encolar_o_indexar_rag_doc(
                    request, self, 'DocumentoRAG', doc, show_index_message=False,
                )
                queued += 1
        self.message_user(
            request,
            f'✅ {queued} documentos en cola (segundo plano).'
            if queued else 'Nada pendiente que indexar.',
        )

    @admin.action(description='📝 Indexar contenido de módulos en RAG')
    def indexar_contenido_modulos(self, request, queryset):
        """Indexa el contenido educativo de los módulos en la BD vectorial."""
        from core.rag_manager import rag_manager
        total = 0
        for curso in queryset:
            n = rag_manager.indexar_modulos_curso(curso.id)
            total += n
        self.message_user(request, f"✅ {total} chunks indexados desde contenido de módulos.")

    def save_formset(self, request, form, formset, change):
        """Al guardar DocumentoRAG inline, encolar indexación (no bloquear request)."""
        from core.admin.commercial import _encolar_o_indexar_rag_doc

        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, DocumentoRAG):
                if not instance.subido_por_id:
                    instance.subido_por = request.user
                instance.save()
                if instance.estado == 'pendiente' and instance.archivo:
                    _encolar_o_indexar_rag_doc(
                        request, self, 'DocumentoRAG', instance, show_index_message=False,
                    )
            else:
                instance.save()
        formset.save_m2m()
        # Manejar eliminaciones
        for obj in formset.deleted_objects:
            if isinstance(obj, DocumentoRAG):
                from core.rag_manager import rag_manager
                rag_manager.eliminar_documento(obj.cliente_id, obj.curso_id, obj.nombre)
            obj.delete()

    @admin.action(description='📋 Ver módulos de cursos seleccionados')
    def ver_todos_modulos(self, request, queryset):
        """Redirige a la vista de módulos filtrando por los cursos seleccionados"""
        from django.shortcuts import redirect
        curso_ids = ','.join(str(c.id) for c in queryset)
        return redirect(f'/admin/core/modulo/?curso__id__in={curso_ids}')

    @admin.action(description='✅ Activar cursos seleccionados')
    def activar_cursos(self, request, queryset):
        count = queryset.update(activo=True)
        self.message_user(request, f"✅ {count} curso(s) activado(s)")

    @admin.action(description='❌ Desactivar cursos seleccionados')
    def desactivar_cursos(self, request, queryset):
        count = queryset.update(activo=False)
        self.message_user(request, f"❌ {count} curso(s) desactivado(s)")

    @admin.action(description='📋 Copiar a otro cliente…')
    def copiar_a_otro_cliente(self, request, queryset):
        from django.shortcuts import redirect

        ids = ','.join(str(c.pk) for c in queryset)
        return redirect(f'/admin/copiar-curso/?cursos={ids}')

    @admin.action(description='📋 Copiar a Analytics (Pruebas) — legacy')
    def copiar_a_analytics_pruebas(self, request, queryset):
        from core.copiar_cursos import (
            CLIENTE_ORIGEN_NOMBRE,
            ClienteOrigenNoEncontrado,
            copiar_cursos_a_pruebas,
            obtener_cliente_analytics_origen,
        )

        try:
            origen = obtener_cliente_analytics_origen()
        except ClienteOrigenNoEncontrado as e:
            self.message_user(request, str(e), level='error')
            return
        fuera = queryset.exclude(cliente=origen)
        if fuera.exists():
            self.message_user(
                request,
                f'Solo se copian cursos del cliente «{CLIENTE_ORIGEN_NOMBRE}» '
                f'(id={origen.pk}). {fuera.count()} curso(s) de otro cliente ignorados.',
                level='warning',
            )
        ids = list(queryset.filter(cliente=origen).values_list('pk', flat=True))
        if not ids:
            self.message_user(request, 'No hay cursos de Analytics seleccionados.', level='error')
            return
        result = copiar_cursos_a_pruebas(curso_ids=ids)
        self.message_user(
            request,
            f'✅ {result.total_copiados} curso(s) copiados a {result.destino.nombre}.',
        )


class PreguntaModuloInline(admin.StackedInline):
    """Preguntas de validación del módulo (Mini examen)"""
    model = PreguntaModulo
    extra = 0
    tab = True
    can_delete = True
    show_change_link = True
    verbose_name = 'Pregunta'
    verbose_name_plural = 'Examen'

    fieldsets = (
        ('Pregunta', {
            'fields': ('pregunta',),
            'description': (
                'Se envía cuando el estudiante ya recorrió todos los microcontenidos activos '
                '(no durante *listo* intermedio). Independiente de las evaluaciones por letras '
                'dentro de cada microcontenido.'
            ),
        }),
        ('Opciones de respuesta', {
            'fields': ('opcion_a', 'opcion_b', 'opcion_c', 'opcion_d', 'respuesta_correcta')
        }),
        ('Estado', {
            'fields': ('activa',)
        }),
    )


class SeccionModuloInline(admin.TabularInline):
    """Estructura: bloques que agrupan microcontenidos (título no se envía por WhatsApp)."""
    model = SeccionModulo
    extra = 0
    tab = True
    can_delete = True
    ordering = ('orden', 'id')
    ordering_field = 'orden'
    hide_ordering_field = True
    show_change_link = True
    verbose_name = 'Bloque'
    verbose_name_plural = 'Estructura'
    fields = ('mover_orden', 'orden', 'activa', 'titulo', 'resumen_pasos')
    readonly_fields = ('mover_orden', 'resumen_pasos')

    @admin.display(description='Orden')
    def mover_orden(self, obj):
        return _botones_mover_bloque(obj, 'seccion')

    @admin.display(description='Pasos activos')
    def resumen_pasos(self, obj):
        if not obj or not obj.pk:
            return format_html(
                '<span style="color:#94a3b8;font-size:12px;">—</span>'
            )
        n = obj.pasos.filter(activo=True).count()
        return format_html(
            '<span style="font-weight:600;color:#0f766e;">{}</span>'
            '<span style="color:#64748b;font-size:11px;"> en esta sección</span>',
            n,
        )


class PasoModuloForm(forms.ModelForm):
    media_file_upload = forms.FileField(
        label='Subir archivo desde PC',
        required=False,
        help_text=(
            'Opcional. Si subes un archivo aquí, se guarda en el storage configurado '
            '(S3 en producción) y se copia su URL pública a “Media url”.'
        ),
    )

    class Meta:
        model = PasoModulo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst and inst.pk and getattr(inst, 'tipo', None) == PasoModulo.TIPO_EVAL_OPC:
            data = inst.opciones_json
            if isinstance(data, dict):
                for letter in ('A', 'B', 'C', 'D'):
                    fname = f'eval_opcion_{letter.lower()}'
                    cur = (getattr(inst, fname, None) or '').strip()
                    if cur:
                        continue
                    val = data.get(letter)
                    if val:
                        self.initial[fname] = str(val)

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded_file = self.cleaned_data.get('media_file_upload')
        if uploaded_file:
            modulo_id = instance.modulo_id or 'sin_modulo'
            instance.media_url = guardar_upload_admin_media(
                uploaded_file,
                carpeta='modulos/pasos',
                prefix=f'modulo_{modulo_id}',
            )
            if not (instance.media_url or '').strip():
                raise ValidationError(
                    {
                        'media_file_upload': (
                            'El archivo se subió pero no se obtuvo URL pública. '
                            'Reintente o pegue la URL en «Media url».'
                        )
                    }
                )

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ModuloAdminForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.module_steps import cuenta_microcontenidos_modulo

        self.fields['contenido'].required = False
        if 'modo_entrega' in self.fields:
            self.fields['modo_entrega'].help_text = (
                'Recomendado: «Por pasos con listo». Legacy envía todo el módulo de una vez '
                'e ignora microcontenidos. Automático hereda según haya pasos o no.'
            )
        n_micro = cuenta_microcontenidos_modulo(self.instance)
        if not self.instance.pk:
            self.fields['contenido'].help_text = (
                'Opcional al crear: se siembra una plantilla (Estructura + Microcontenidos). '
                'Complete el texto en cada paso; use este campo solo en modo Legacy.'
            )
        elif n_micro > 0:
            self.fields['contenido'].help_text = (
                f'Opcional: este módulo ya tiene {n_micro} microcontenido(s). '
                'El estudiante recibe el texto de cada paso en «Microcontenidos». '
                'Solo úselo en modo Legacy o como intro extra.'
            )
        else:
            self.fields['contenido'].help_text = (
                'Obligatorio solo si aún no hay microcontenidos. Tras crear estructura y pasos, '
                'puede vaciar este campo.'
            )

    def clean_contenido(self):
        from core.module_steps import validar_contenido_modulo

        contenido = self.cleaned_data.get('contenido', '')
        # Alta: plantilla de pasos se siembra en save_related; no exigir texto aquí.
        if not self.instance.pk:
            return contenido
        validar_contenido_modulo(contenido, self.instance)
        return contenido


class PasoModuloInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        from core.module_steps import validar_contenido_modulo

        contenido = (self.data.get('contenido') or '').strip()
        try:
            validar_contenido_modulo(contenido, self.instance, pasos_formset=self)
        except ValidationError as exc:
            raise ValidationError(exc.messages) from exc


class PasoModuloInline(admin.StackedInline):
    """Microcontenidos WhatsApp dentro del módulo (orden + listo)."""
    model = PasoModulo
    form = PasoModuloForm
    formset = PasoModuloInlineFormSet
    extra = 0
    tab = True
    can_delete = True
    ordering = ('orden', 'id')
    ordering_field = 'orden'
    hide_ordering_field = True
    show_change_link = True
    verbose_name = 'Paso'
    verbose_name_plural = 'Microcontenidos'
    fieldsets = (
        (None, {
            'fields': (
                'mover_orden', 'orden', 'seccion', 'activo',
                'requiere_listo_para_avanzar', 'tipo',
            ),
        }),
        ('Texto y multimedia (WhatsApp)', {
            'fields': ('titulo', 'contenido', 'media_url', 'media_file_upload'),
            'description': (
                'Título = referencia interna. El estudiante recibe «Contenido» + media. '
                'Pegá una URL o subí archivo (en prod se guarda en S3 y completa Media URL).'
            ),
        }),
        ('Evaluación tipo opciones', {
            'fields': (
                'eval_opcion_a', 'eval_opcion_b', 'eval_opcion_c', 'eval_opcion_d',
                'respuesta_correcta',
            ),
        }),
        ('Retroalimentación', {
            'fields': ('feedback_correcto', 'feedback_incorrecto'),
            'classes': ('collapse',),
        }),
        ('Avanzado / legado', {
            'fields': ('opciones_json',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('mover_orden',)
    formfield_overrides = {
        models.TextField: {
            'widget': forms.Textarea(attrs={'rows': 3, 'cols': 50, 'style': 'min-width:280px;'}),
        },
    }

    @admin.display(description='Mover')
    def mover_orden(self, obj):
        return _botones_mover_bloque(obj, 'paso')

    def get_formset(self, request, obj=None, **kwargs):
        self._modulo_inline_parent = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'seccion':
            mod = getattr(self, '_modulo_inline_parent', None)
            if mod is not None and mod.pk:
                kwargs['queryset'] = SeccionModulo.objects.filter(modulo_id=mod.pk).order_by(
                    'orden', 'id'
                )
            # Módulo nuevo sin PK: no filtramos; el admin no muestra este inline (ver ModuloAdmin).
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ArchivoModuloInline(admin.StackedInline):
    """Multimedia a nivel módulo (Legacy / complemento). Preferir media en cada microcontenido."""
    model = ArchivoModulo
    extra = 0
    tab = True
    can_delete = True
    ordering = ('orden', 'id')
    ordering_field = 'orden'
    hide_ordering_field = True
    show_change_link = True
    verbose_name = 'Archivo'
    verbose_name_plural = 'Multimedia legacy'

    fieldsets = (
        (None, {
            'fields': ('mover_orden', 'tipo', 'titulo', 'descripcion'),
            'description': (
                'Uso secundario: envío del módulo completo (modo Legacy) o archivos extra. '
                'Para el flujo por *listo*, preferí media en cada fila de Microcontenidos.'
            ),
        }),
        ('Archivo o URL', {
            'fields': ('archivo', 'preview_multimedia', 'url_externa'),
            'description': (
                'Subí un archivo (S3 en producción) o pegá una URL pública (YouTube, Drive, etc.).'
            ),
        }),
        ('Configuración', {
            'fields': ('disponible_offline', 'orden', 'activo'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('preview_multimedia', 'mover_orden')

    @admin.display(description='Mover')
    def mover_orden(self, obj):
        return _botones_mover_bloque(obj, 'archivo')

    def preview_multimedia(self, obj):
        """Vista previa del archivo multimedia"""
        if not obj.archivo:
            if obj.url_externa:
                return format_html(
                    '<div style="background:#e0f2fe;padding:12px;border-radius:6px;border-left:4px solid #0284c7;">'
                    '<strong>🔗 URL Externa:</strong><br>'
                    '<a href="{}" target="_blank" style="color:#0284c7;word-break:break-all;">{}</a>'
                    '</div>',
                    obj.url_externa, obj.url_externa
                )
            return format_html('<span style="color:#999;font-style:italic;">⚠️ Sin archivo subido</span>')

        url = obj.archivo.url

        if obj.tipo == 'imagen':
            return format_html(
                '<div style="text-align:center;background:#f9fafb;padding:16px;border-radius:8px;border:2px solid #e5e7eb;">'
                '<img src="{}" style="max-width:100%;max-height:400px;border-radius:6px;box-shadow:0 4px 6px rgba(0,0,0,0.1);" />'
                '<p style="margin-top:12px;color:#6b7280;font-size:12px;">📸 Imagen cargada correctamente</p>'
                '</div>',
                url
            )
        if obj.tipo == 'video':
            return format_html(
                '<div style="background:#f9fafb;padding:16px;border-radius:8px;border:2px solid #e5e7eb;">'
                '<video controls style="max-width:100%;border-radius:6px;box-shadow:0 4px 6px rgba(0,0,0,0.1);">'
                '<source src="{}" type="video/mp4">'
                'Tu navegador no soporta video HTML5.'
                '</video>'
                '<p style="margin-top:12px;color:#6b7280;font-size:12px;">🎥 Video cargado - URL: '
                '<code style="background:#e5e7eb;padding:2px 6px;border-radius:4px;font-size:11px;">{}</code></p>'
                '</div>',
                url, url
            )
        if obj.tipo == 'pdf':
            return format_html(
                '<div style="background:#fef2f2;padding:14px;border-radius:6px;border-left:4px solid #dc2626;">'
                '<a href="{}" target="_blank" style="background:#dc2626;color:white;padding:10px 20px;'
                'text-decoration:none;border-radius:6px;display:inline-block;font-weight:bold;">'
                '📄 Abrir PDF en Nueva Pestaña'
                '</a>'
                '<p style="margin-top:10px;color:#991b1b;font-size:12px;">Archivo: {}</p>'
                '</div>',
                url, obj.archivo.name
            )
        if obj.tipo == 'audio':
            return format_html(
                '<div style="background:#f9fafb;padding:16px;border-radius:8px;border:2px solid #e5e7eb;">'
                '<audio controls style="width:100%;">'
                '<source src="{}" type="audio/mpeg">'
                'Tu navegador no soporta audio HTML5.'
                '</audio>'
                '<p style="margin-top:12px;color:#6b7280;font-size:12px;">🎵 Audio cargado</p>'
                '</div>',
                url
            )
        return format_html(
            '<div style="background:#f0fdf4;padding:14px;border-radius:6px;border-left:4px solid #16a34a;">'
            '<a href="{}" target="_blank" style="color:#16a34a;font-weight:bold;">📎 Ver Archivo</a>'
            '<p style="margin-top:8px;color:#166534;font-size:12px;">{}</p>'
            '</div>',
            url, obj.archivo.name
        )
    preview_multimedia.short_description = "Vista Previa"


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    """Administración de módulos"""
    form = ModuloAdminForm
    class Media:
        css = {
            'all': ('admin/css/modulo_whatsapp_bloques.css',),
        }
        js = ('admin/js/eki_modulo_jump.js',)

    # Listado ops: curso + número; preview largo → ficha del módulo.
    list_display = (
        'numero_titulo',
        'curso',
        'modo_entrega_badge',
        'pasos_activos_count',
        'examen_badge',
        'archivos_link',
        'ver_curso_link',
    )
    list_filter = ('curso', 'modo_entrega', 'examen_obligatorio')
    search_fields = ('titulo', 'descripcion', 'curso__nombre')
    list_select_related = ('curso', 'curso__cliente')
    list_per_page = 50
    ordering = ['curso__nombre', 'numero']
    readonly_fields = ('guia_microcontenidos_whatsapp',)
    inlines = [SeccionModuloInline, PasoModuloInline, ArchivoModuloInline, PreguntaModuloInline]
    actions = ['enviar_archivos_multimedia', 'ver_archivos_multimedia', 'renumerar_modulos']

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:modulo_id>/mover/<str:kind>/<int:obj_id>/<str:direction>/',
                self.admin_site.admin_view(self.mover_bloque_view),
                name='core_modulo_mover_bloque',
            ),
            path(
                '<int:modulo_id>/mover/<str:kind>/<int:obj_id>/<str:direction>',
                self.admin_site.admin_view(self.mover_bloque_view),
            ),
        ]
        return custom + urls

    def mover_bloque_view(self, request, modulo_id, kind, obj_id, direction):
        """↑↓ de secciones / pasos / multimedia sin salir del change del módulo."""
        from core.models import ArchivoModulo

        if not self.has_change_permission(request):
            raise PermissionDenied

        kind_map = {
            'seccion': SeccionModulo,
            'paso': PasoModulo,
            'archivo': ArchivoModulo,
        }
        model = kind_map.get(kind)
        if model is None or direction not in ('up', 'down'):
            messages.error(request, 'Movimiento no válido.')
            return redirect('admin:core_modulo_change', modulo_id)

        try:
            modulo = Modulo.objects.get(pk=modulo_id)
            obj = model.objects.get(pk=obj_id, modulo_id=modulo.pk)
        except (Modulo.DoesNotExist, model.DoesNotExist):
            messages.error(request, 'Bloque no encontrado.')
            return redirect('admin:core_modulo_changelist')

        if intercambiar_orden(obj, direction):
            messages.success(request, 'Orden actualizado.')
        else:
            messages.info(request, 'Ya está al extremo; no hay cambio.')
        return redirect('admin:core_modulo_change', modulo_id)

    def get_inline_instances(self, request, obj=None):
        """Módulo nuevo: Microcontenidos aparecen tras el 1.er guardado (necesitan PK + sección)."""
        instances = []
        for inline_class in self.inlines:
            if inline_class is PasoModuloInline and obj is None:
                continue
            instances.append(inline_class(self.model, self.admin_site))
        return instances

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        data.setdefault('modo_entrega', Modulo.MODO_ENTREGA_PASOS)
        return data

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if change:
            return
        created = sembrar_plantilla_modulo(form.instance)
        if not (created['seccion'] or created['pasos']):
            return
        bits = []
        if created['seccion']:
            bits.append('1 bloque de estructura')
        if created['pasos']:
            bits.append(
                f'{created["pasos"]} microcontenido(s) vacío(s) (inactivos)'
            )
        self.message_user(
            request,
            (
                'Plantilla lista: ' + ' + '.join(bits) + '. '
                'Active y complete el texto en la pestaña Microcontenidos.'
            ),
            level=messages.INFO,
        )

    def response_add(self, request, obj, post_url_continue=None):
        """Tras crear, abrir el módulo (plantilla ya sembrada) para completar Microcontenidos."""
        if '_addanother' in request.POST:
            return super().response_add(request, obj, post_url_continue)
        self.message_user(
            request,
            (
                'Módulo creado. Use las pestañas Estructura → Microcontenidos. '
                'Cada paso debe tener sección; active los microcontenidos cuando el texto esté listo.'
            ),
            level=messages.SUCCESS,
        )
        return redirect('admin:core_modulo_change', obj.pk)

    def ver_curso_link(self, obj):
        """Link directo al curso padre"""
        url = reverse('admin:core_curso_change', args=[obj.curso.id])
        return format_html('<a href="{}" style="color:#2196F3;">Ver curso</a>', url)
    ver_curso_link.short_description = "Curso"

    @admin.display(description='')
    def guia_microcontenidos_whatsapp(self, obj):
        """Guía corta + detalle colapsable (la barra sticky la inyecta JS)."""
        return format_html(
            '<div class="eki-modulo-guia">'
            '<p style="margin:0 0 0.5rem;font-size:0.9rem;font-weight:650;color:#5F3A6E;">'
            'Flujo: Datos → Estructura → Microcontenidos. Media va en cada paso; '
            'Multimedia legacy es secundario. Arrastre las cajas o use ↑↓ para reordenar.'
            '</p>'
            '<details>'
            '<summary>Ayuda rápida</summary>'
            '<p>1) En <b>Estructura</b> defina bloques (secciones). '
            '2) En <b>Microcontenidos</b> complete texto/media y active. '
            '3) Modo Legacy ignora microcontenidos y usa el texto del módulo.</p>'
            '</details>'
            '</div>'
        )

    def save_formset(self, request, form, formset, change):
        """Drag Unfold escribe orden 0..n; UniqueConstraint (modulo, orden) exige temp + renúmero 1..n."""
        models_con_unique = (SeccionModulo, PasoModulo)
        if formset.model in models_con_unique and form.instance.pk:
            with transaction.atomic():
                preparar_ordenes_temporales(formset.model, form.instance.pk)
                super().save_formset(request, form, formset, change)
                renumerar_orden_1_based(formset.model, form.instance.pk)
            return
        super().save_formset(request, form, formset, change)

    fieldsets = (
        (
            'Datos',
            {
                'classes': ['tab'],
                'fields': (
                    'guia_microcontenidos_whatsapp',
                    'curso',
                    'numero',
                    'titulo',
                    'descripcion',
                ),
                'description': (
                    'Número de módulo: entero ≥ 0 (0 = bienvenida; luego 1, 2, 3…). '
                    'Use las pestañas superiores para Estructura y Microcontenidos.'
                ),
            },
        ),
        (
            'Entrega',
            {
                'classes': ['tab'],
                'fields': ('modo_entrega', 'secciones_por_listo', 'facilitador_checkpoint'),
                'description': (
                    'Por pasos = flujo *listo* (recomendado). Legacy = módulo completo de una vez. '
                    'Secciones por *listo*: cuántos bloques salen juntos. '
                    'Checkpoint facilitadora: solo con agentes IA al cerrar el módulo.'
                ),
            },
        ),
        (
            'Texto legacy',
            {
                'classes': ['tab'],
                'fields': ('contenido',),
                'description': (
                    'Principal solo en modo Legacy. Con microcontenidos, deje vacío.'
                ),
            },
        ),
        (
            'Examen',
            {
                'classes': ['tab'],
                'fields': ('examen_obligatorio', 'puntaje_minimo_aprobacion'),
                'description': (
                    'Si el examen es obligatorio, el estudiante no avanza al siguiente módulo '
                    'hasta aprobar.'
                ),
            },
        ),
        (
            'Calendario',
            {
                'classes': ['tab'],
                'fields': ('duracion_dias', 'habilitado_desde'),
                'description': (
                    'Disponible desde: opcional; bloquea el envío hasta esa fecha '
                    '(salvo habilitación distinta en Cliente).'
                ),
            },
        ),
    )
    
    def modo_entrega_badge(self, obj):
        from core.models import Modulo
        labels = dict(Modulo.MODOS_ENTREGA)
        t = labels.get(obj.modo_entrega, obj.modo_entrega)
        return format_html('<span style="font-size:11px;">{}</span>', t)
    modo_entrega_badge.short_description = 'Entrega'

    def pasos_activos_count(self, obj):
        count = obj.pasos.filter(activo=True, seccion__activa=True).count()
        if obj.modo_entrega == 'pasos' and count == 0:
            return format_html(
                '<span style="color:#c62828;font-weight:bold;">'
                '⚠️ Modo PASOS pero sin pasos activos (count: {})'
                '</span>',
                count,
            )
        return count
    pasos_activos_count.short_description = 'Pasos activos'

    def numero_titulo(self, obj):
        return f"Módulo {obj.numero}: {obj.titulo}"
    numero_titulo.short_description = "Módulo"
    
    def examen_badge(self, obj):
        if obj.examen_obligatorio:
            return format_html(
                '<span style="background:#ffebee;color:#c62828;padding:4px 10px;border-radius:12px;font-size:11px;font-weight:600;">🔒 OBLIGATORIO ({0}%)</span>',
                obj.puntaje_minimo_aprobacion
            )
        return format_html('<span style="color:#999;">Sin examen</span>')
    examen_badge.short_description = "Examen"
    
    def archivos_link(self, obj):
        count = obj.archivos_multimedia.filter(activo=True).count()
        if count > 0:
            url = f"/admin/core/archivomodulo/?modulo__id__exact={obj.id}"
            return format_html(
                '<a href="{}" style="background:#e3f2fd;color:#1976d2;padding:4px 10px;border-radius:12px;font-size:11px;font-weight:600;text-decoration:none;">📁 {} archivo(s)</a>',
                url, count
            )
        return format_html('<span style="color:#999;">Sin archivos</span>')
    archivos_link.short_description = "Multimedia"
    
    def tiene_pregunta(self, obj):
        count = obj.preguntas.filter(activa=True).count()
        if count > 0:
            return format_html('<span style="color:green;">✅ {} pregunta(s)</span>', count)
        return format_html('<span style="color:red;">❌ Sin pregunta</span>')
    tiene_pregunta.short_description = "Mini Examen"
    
    def contenido_preview(self, obj):
        preview = obj.contenido[:60] + "..." if len(obj.contenido) > 60 else obj.contenido
        return format_html('<span style="color:#666;font-style:italic;">{}</span>', preview)
    contenido_preview.short_description = "Vista Previa"
    
    def enviar_archivos_multimedia(self, request, queryset):
        """Envía los archivos multimedia de los módulos seleccionados a estudiantes inscritos"""
        from core.utils import enviar_whatsapp_twilio
        import json
        
        enviados = 0
        errores = 0
        
        for modulo in queryset:
            archivos = modulo.archivos_multimedia.filter(activo=True)
            if not archivos.exists():
                continue
            
            # Obtener estudiantes inscritos en el curso
            estudiantes = Estudiante.objects.filter(
                progreso__curso=modulo.curso,
                activo=True
            ).distinct()
            
            for estudiante in estudiantes:
                try:
                    # Mensaje con lista de archivos
                    mensaje = f"📚 *{modulo.titulo}*\n\n"
                    mensaje += f"Tienes {archivos.count()} archivo(s) multimedia disponible(s):\n\n"
                    
                    for i, archivo in enumerate(archivos, 1):
                        icono = {
                            'video': '🎥',
                            'imagen': '🖼️',
                            'infografia': '📊',
                            'pdf': '📄',
                            'audio': '🎵'
                        }.get(archivo.tipo, '📁')
                        
                        mensaje += f"{icono} *{i}. {archivo.titulo}*\n"
                        if archivo.descripcion:
                            mensaje += f"   {archivo.descripcion}\n"
                        
                        if archivo.disponible_offline:
                            url_descarga = f"{request.build_absolute_uri('/media/descargar-archivo/')}{archivo.id}/"
                            mensaje += f"   🔗 Descarga: {url_descarga}\n"
                        
                        if archivo.url_externa:
                            mensaje += f"   🌐 Ver online: {archivo.url_externa}\n"
                        
                        mensaje += "\n"
                    
                    # Enviar por WhatsApp
                    enviar_whatsapp_twilio(estudiante.telefono, mensaje)
                    enviados += 1
                    
                except Exception as e:
                    print(f"Error enviando archivos a {estudiante.telefono}: {e}")
                    errores += 1
        
        self.message_user(
            request,
            f'✅ {enviados} mensaje(s) enviado(s) con archivos multimedia. ❌ {errores} error(es).'
        )
    enviar_archivos_multimedia.short_description = "📤 Enviar archivos multimedia a estudiantes"
    
    @admin.action(description='� Renumerar módulos (1, 2, 3...)')
    def renumerar_modulos(self, request, queryset):
        """Renumera los módulos seleccionados empezando desde 1"""
        # Agrupar por curso
        modulos_por_curso = {}
        for modulo in queryset.order_by('curso', 'numero', 'id'):
            if modulo.curso not in modulos_por_curso:
                modulos_por_curso[modulo.curso] = []
            modulos_por_curso[modulo.curso].append(modulo)
        
        total_renumerados = 0
        for curso, modulos in modulos_por_curso.items():
            for idx, modulo in enumerate(modulos, start=1):
                if modulo.numero != idx:
                    modulo.numero = idx
                    modulo.save()
                    total_renumerados += 1
        
        self.message_user(
            request,
            f"✅ {total_renumerados} módulos renumerados correctamente",
            level='success'
        )
    renumerar_modulos.short_description = "🔢 Renumerar módulos (1, 2, 3...)"
    
    @admin.action(description='�📁 Ver archivos multimedia de módulos')
    def ver_archivos_multimedia(self, request, queryset):
        """Redirige a ver los archivos multimedia de los módulos seleccionados"""
        from django.shortcuts import redirect
        modulo_ids = ','.join(str(m.id) for m in queryset)
        return redirect(f'/admin/core/archivomodulo/?modulo__id__in={modulo_ids}')


class PreguntaExamenInline(admin.TabularInline):
    """Preguntas dentro del examen"""
    model = PreguntaExamen
    extra = 1
    fields = ('numero', 'pregunta', 'respuesta_correcta', 'puntos')
    ordering = ['numero']


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
    list_display = ('estudiante', 'curso', 'barra_progreso', 'modulo_actual', 'completado_badge', 'certificado_status', 'fecha_ultimo_avance', 'fecha_inicio')
    list_filter = ('completado', 'curso', 'fecha_inicio')
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'curso__nombre')
    readonly_fields = ('fecha_inicio', 'porcentaje_avance', 'info_certificado')
    list_per_page = 50
    ordering = ('-fecha_inicio',)
    actions = ['exportar_progreso_excel', 'exportar_progreso_csv', 'generar_certificados_pendientes']  # ✅ Nuevas acciones
    
    fieldsets = (
        ('👤 Estudiante y Curso', {
            'fields': ('estudiante', 'curso')
        }),
        ('📊 Progreso', {
            'fields': ('modulo_actual', 'completado', 'porcentaje_avance')
        }),
        ('📅 Fechas', {
            'fields': ('fecha_inicio', 'fecha_ultimo_avance', 'fecha_completado')
        }),
    )
    
    def barra_progreso(self, obj):
        """Muestra una barra de progreso visual"""
        porcentaje = obj.porcentaje_avance()
        
        # Colores según progreso
        if porcentaje >= 80:
            color = '#4caf50'
        elif porcentaje >= 50:
            color = '#ff9800'
        else:
            color = '#f44336'
        
        return format_html(
            '<div style="width:100px;height:20px;background:#f0f0f0;border-radius:10px;overflow:hidden;border:1px solid #ddd;">'
            '<div style="width:{}%;height:100%;background:{};transition:width 0.3s;display:flex;align-items:center;justify-content:center;color:white;font-size:11px;font-weight:bold;">'
            '{}%'
            '</div></div>',
            porcentaje, color, porcentaje
        )
    barra_progreso.short_description = "Progreso"
    
    def certificado_status(self, obj):
        """Muestra si hay certificado generado"""
        if obj.completado:
            certificado = Certificado.objects.filter(estudiante=obj.estudiante, curso=obj.curso, emitido=True).first()
            if certificado:
                return format_html(
                    '<span style="color:#4caf50;font-weight:bold;">🏆 Emitido</span>'
                )
            else:
                return format_html(
                    '<span style="color:#ff9800;font-weight:bold;">⏳ Pendiente</span>'
                )
        return format_html('<span style="color:#999;">-</span>')
    certificado_status.short_description = "Certificado"
    
    def info_certificado(self, obj):
        """Información del certificado en los detalles"""
        if obj.completado:
            certificado = Certificado.objects.filter(estudiante=obj.estudiante, curso=obj.curso).first()
            if certificado:
                return format_html(
                    '<div style="background:#f5f5f5;padding:10px;border-radius:4px;border-left:4px solid #4caf50;">'
                    '<strong>✅ Certificado Generado</strong><br>'
                    'Código: <code>{}</code><br>'
                    'Calificación: <strong>{}</strong>%<br>'
                    'Emitido: {}'
                    '</div>',
                    certificado.codigo_verificacion,
                    int(certificado.calificacion_final),
                    certificado.fecha_emision.strftime('%d/%m/%Y') if certificado.fecha_emision else 'N/A'
                )
            else:
                return format_html(
                    '<div style="background:#fff3cd;padding:10px;border-radius:4px;border-left:4px solid #ff9800;">'
                    '<strong>⏳ Certificado Pendiente</strong><br>'
                    'El curso está completo pero el certificado aún no se ha generado'
                    '</div>'
                )
        return format_html(
            '<div style="background:#f5f5f5;padding:10px;border-radius:4px;border-left:4px solid #999;">'
            '<span style="color:#999;">El curso aún no está completo</span>'
            '</div>'
        )
    info_certificado.short_description = "Estado del Certificado"
    
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
    
    @admin.action(description='🏆 Generar certificados pendientes')
    def generar_certificados_pendientes(self, request, queryset):
        """Genera certificados para cursos completados que no los tienen"""
        from core.certificado_service import generar_y_guardar_certificado, crear_certificado_automatico, enviar_certificado_whatsapp
        
        generados = 0
        errores = 0
        
        for progreso in queryset.filter(completado=True):
            certificado = Certificado.objects.filter(estudiante=progreso.estudiante, curso=progreso.curso).first()
            if not certificado:
                try:
                    certificado = crear_certificado_automatico(progreso.estudiante, progreso.curso)
                    if certificado and not certificado.emitido:
                        generar_y_guardar_certificado(certificado)
                    if certificado and certificado.emitido:
                        enviar_certificado_whatsapp(certificado)
                    generados += 1
                except Exception as e:
                    logger.error(f"Error al generar certificado para {progreso.estudiante.nombre}: {str(e)}")
                    errores += 1
        
        if generados > 0:
            self.message_user(request, f'✅ {generados} certificado(s) generado(s) y enviado(s)', messages.SUCCESS)
        if errores > 0:
            self.message_user(request, f'❌ {errores} error(es) al generar', messages.ERROR)
    
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
admin.site.site_header = "eki - Chatbot Agro 🌱"
admin.site.site_title = "Administración eki"
admin.site.index_title = "Panel de Control - Chatbot Educativo"


