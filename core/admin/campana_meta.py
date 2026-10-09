"""Admin Unfold: plantillas y campañas Meta (Graph API)."""
from django.contrib import admin, messages

from core.admin._common import *  # noqa: F401,F403
from core.models_campana_meta import CampanaMeta, PlantillaMeta, TarjetaPlantillaMeta


class TarjetaPlantillaMetaInline(admin.TabularInline):
    model = TarjetaPlantillaMeta
    extra = 0
    fields = (
        'orden',
        'titulo',
        'cuerpo',
        'boton_ver_texto',
        'boton_info_texto',
        'info_url',
    )


@admin.register(PlantillaMeta)
class PlantillaMetaAdmin(admin.ModelAdmin):
    list_display = ('nombre_interno', 'tipo', 'estado_badge', 'activa')
    list_filter = ('estado', 'tipo', 'categoria', 'activa', 'idioma')
    search_fields = ('nombre_interno', 'meta_name', 'meta_template_id', 'cuerpo')
    list_per_page = 50
    actions = ['sincronizar_seleccionadas', 'enviar_a_meta', 'traer_catalogo_meta']
    readonly_fields = (
        'meta_template_id',
        'waba_id',
        'rejected_reason',
        'ultimo_error_code',
        'ultimo_error_mensaje',
        'enviada_en',
        'sincronizada_en',
    )

    fieldsets = (
        ('Mensaje', {
            'fields': ('nombre_interno', 'tipo', 'cuerpo', 'estado'),
            'description': (
                '1. Nombre y tipo. 2. Escribe el mensaje. '
                '3. En el listado, la acción «Enviar plantilla a Meta para aprobación». '
                'Cuando Meta la acepte, el estado queda en Aprobada.'
            ),
        }),
        ('Más opciones', {
            'classes': ('collapse',),
            'fields': (
                'meta_name',
                'idioma',
                'categoria',
                'activa',
                'header_texto',
                'header_ejemplo',
                'ejemplos_cuerpo',
                'footer',
                'boton_1_tipo',
                'boton_1_texto',
                'boton_1_url',
                'boton_1_ejemplo',
                'boton_2_tipo',
                'boton_2_texto',
                'boton_2_url',
                'boton_2_ejemplo',
            ),
            'description': 'Encabezado, botones y ejemplos. El mensaje de texto no los necesita.',
        }),
        ('Estado en Meta', {
            'classes': ('collapse',),
            'fields': (
                'meta_template_id',
                'waba_id',
                'rejected_reason',
                'ultimo_error_code',
                'ultimo_error_mensaje',
                'enviada_en',
                'sincronizada_en',
            ),
        }),
    )

    def get_inlines(self, request, obj=None):
        if obj is not None and obj.tipo == 'CARRUSEL':
            return [TarjetaPlantillaMetaInline]
        return []

    def get_urls(self):
        from django.urls import path

        custom = [
            path(
                'nueva/',
                self.admin_site.admin_view(self.tipo_view),
                name='core_plantillameta_tipo',
            ),
            path(
                'escribir/<str:tipo>/',
                self.admin_site.admin_view(self.escribir_view),
                name='core_plantillameta_escribir',
            ),
            path(
                '<int:pk>/escribir/',
                self.admin_site.admin_view(self.escribir_view),
                name='core_plantillameta_escribir_una',
            ),
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import render

        if not self.has_view_permission(request):
            raise PermissionDenied
        q = (request.GET.get('q') or '').strip()
        qs = self.get_queryset(request)
        if q:
            qs = qs.filter(nombre_interno__icontains=q)
        return render(request, 'admin/plantilla_meta/lista.html', {
            'plantillas': qs[:200],
            'q': q,
            'title': 'Plantillas',
        })

    def add_view(self, request, form_url='', extra_context=None):
        from django.shortcuts import redirect
        return redirect('admin:core_plantillameta_tipo')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from django.shortcuts import redirect
        return redirect('admin:core_plantillameta_escribir_una', pk=object_id)

    def tipo_view(self, request):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import render

        from core.plantilla_builder import TARJETAS_TIPO

        if not self.has_add_permission(request):
            raise PermissionDenied
        return render(request, 'admin/plantilla_meta/tipo.html', {
            'tarjetas': TARJETAS_TIPO,
            'title': 'Nueva plantilla',
        })

    def escribir_view(self, request, tipo='TEXTO', pk=None):
        from django.contrib import messages
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import get_object_or_404, redirect, render

        from core.plantilla_builder import TIPOS_EDITOR, guardar_editor

        plantilla = None
        if pk is not None:
            plantilla = get_object_or_404(self.get_queryset(request), pk=pk)
            tipo = plantilla.tipo if plantilla.tipo in TIPOS_EDITOR else 'TEXTO'
            if not self.has_change_permission(request, plantilla):
                raise PermissionDenied
        else:
            tipo = (tipo or 'TEXTO').upper()
            if tipo not in TIPOS_EDITOR:
                tipo = 'TEXTO'
            if not self.has_add_permission(request):
                raise PermissionDenied

        errores = []
        if request.method == 'POST':
            guardada, errores = guardar_editor(request.POST, tipo, plantilla)
            if guardada is not None and not errores:
                if request.POST.get('accion') == 'enviar':
                    from core.meta_waba import crear_plantilla_en_meta
                    resultado = crear_plantilla_en_meta(guardada)
                    nivel = messages.SUCCESS if resultado.get('success') else messages.WARNING
                    self.message_user(
                        request,
                        resultado.get('message') or f'Enviada. Estado {resultado.get("status")}.',
                        level=nivel,
                    )
                else:
                    self.message_user(request, 'Plantilla guardada.', level=messages.SUCCESS)
                return redirect('admin:core_plantillameta_escribir_una', pk=guardada.pk)
            if guardada is not None:
                plantilla = guardada

        ctx = self._ctx_editor(plantilla, tipo, errores)
        if request.method == 'POST' and errores:
            ctx['nombre'] = request.POST.get('nombre_interno') or ''
            ctx['cuerpo'] = request.POST.get('cuerpo') or ''
            ctx['ejemplos'] = request.POST.get('ejemplos_cuerpo') or ''
            ctx['boton'] = request.POST.get('boton_texto') or ''
        return render(request, 'admin/plantilla_meta/editor.html', ctx)

    def _ctx_editor(self, plantilla, tipo, errores):
        titulos = {'TEXTO': 'Texto', 'IMAGEN': 'Imagen', 'CARRUSEL': 'Carrusel'}
        tarjetas = []
        if plantilla is not None and plantilla.pk and tipo == 'CARRUSEL':
            tarjetas = [
                {
                    'titulo': t.titulo,
                    'cuerpo': t.cuerpo,
                    'imagen_url': t.imagen_url,
                    'boton_ver_texto': t.boton_ver_texto,
                    'boton_info_texto': t.boton_info_texto,
                }
                for t in plantilla.tarjetas.all()
            ]
        if tipo == 'CARRUSEL' and len(tarjetas) < 2:
            while len(tarjetas) < 2:
                tarjetas.append({
                    'titulo': '',
                    'cuerpo': '',
                    'imagen_url': '',
                    'boton_ver_texto': 'Ver curso',
                    'boton_info_texto': 'Más información',
                })
        return {
            'title': titulos.get(tipo, 'Plantilla'),
            'titulo_tipo': titulos.get(tipo, 'Plantilla'),
            'tipo': tipo,
            'errores': errores,
            'nombre': plantilla.nombre_interno if plantilla else '',
            'cuerpo': plantilla.cuerpo if plantilla else '',
            'ejemplos': plantilla.ejemplos_cuerpo if plantilla else '',
            'boton': (plantilla.boton_1_texto if plantilla else '') or '',
            'tarjetas': tarjetas,
        }

    @admin.display(description='Aprobación', ordering='estado')
    def estado_badge(self, obj):
        label = obj.get_estado_display()
        if obj.estado == 'APPROVED':
            bg, color = '#e8f5e9', '#2e7d32'
        elif obj.estado in ('REJECTED', 'ERROR', 'DISABLED'):
            bg, color = '#ffebee', '#c62828'
        elif obj.estado in ('PENDING', 'IN_APPEAL'):
            bg, color = '#fff3e0', '#e65100'
        else:
            bg, color = '#f5f5f5', '#424242'
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:700;">{}</span>',
            bg,
            color,
            label,
        )

    @admin.action(description='Sincronizar estado con Meta')
    def sincronizar_seleccionadas(self, request, queryset):
        from core.meta_waba import sincronizar_plantilla

        ok = 0
        for plantilla in queryset:
            resultado = sincronizar_plantilla(plantilla)
            if resultado.get('success'):
                ok += 1
            else:
                self.message_user(
                    request,
                    f'{plantilla.nombre_interno}: {resultado.get("message")}',
                    level=messages.WARNING,
                )
        self.message_user(request, f'{ok} plantilla(s) sincronizada(s).', level=messages.SUCCESS)

    @admin.action(description='Enviar plantilla a Meta para aprobación')
    def enviar_a_meta(self, request, queryset):
        from core.meta_waba import crear_plantilla_en_meta

        for plantilla in queryset:
            resultado = crear_plantilla_en_meta(plantilla)
            nivel = messages.SUCCESS if resultado.get('success') else messages.ERROR
            texto = resultado.get('message') or f'Enviada. ID {resultado.get("template_id")} ({resultado.get("status")})'
            if resultado.get('success'):
                texto = f'{plantilla.nombre_interno}: ID {resultado.get("template_id")} ({resultado.get("status")})'
            else:
                texto = f'{plantilla.nombre_interno}: {resultado.get("message")}'
            self.message_user(request, texto, level=nivel)

    @admin.action(description='Traer de Meta si están aprobadas')
    def traer_catalogo_meta(self, request, queryset):
        del queryset
        from core.meta_waba import sincronizar_catalogo_meta

        resultado = sincronizar_catalogo_meta()
        if not resultado.get('ok'):
            self.message_user(request, resultado.get('message'), level=messages.ERROR)
            return
        for fila in resultado.get('filas') or []:
            self.message_user(
                request,
                f"{fila['nombre']}: {fila['estado']}",
                level=messages.SUCCESS if fila['estado'] == 'APPROVED' else messages.WARNING,
            )
        if not resultado.get('filas'):
            self.message_user(request, 'Meta no devolvió plantillas.', level=messages.WARNING)


@admin.register(CampanaMeta)
class CampanaMetaAdmin(admin.ModelAdmin):
    change_form_template = 'admin/core/campanameta/change_form.html'
    list_display = (
        'nombre', 'plantilla', 'estado_plantilla', 'conteo_destinatarios',
        'ejecutada', 'total_enviados',
    )
    list_filter = ('ejecutada', 'pausada', 'cliente', 'plantilla__estado')
    search_fields = ('nombre', 'plantilla__meta_name', 'plantilla__nombre_interno')
    filter_horizontal = ('destinatarios',)
    autocomplete_fields = ('cliente', 'grupo')
    actions = ['ejecutar_campanas', 'pausar_campanas', 'reanudar_campanas', 'reenviar_reintentables']
    readonly_fields = ('ejecutada', 'total_enviados', 'panel_envios')

    fieldsets = (
        ('Campaña', {
            'fields': ('nombre', 'cliente', 'plantilla'),
            'description': (
                'Elige una plantilla ya Aprobada. '
                'Para mandarla, en el listado usa «Ejecutar campañas Meta».'
            ),
        }),
        ('Destinatarios', {
            'fields': ('grupo', 'destinatarios'),
            'description': 'Si eliges grupo, sale al grupo. Si no, a las personas marcadas.',
        }),
        ('Variables y programación', {
            'classes': ('collapse',),
            'fields': (
                'fecha_programada',
                'mapeo_header',
                'mapeo_body',
                'mapeo_boton',
                'phone_number_id',
            ),
            'description': 'Solo si el mensaje lleva {{1}} o sale por otro número.',
        }),
        ('Resultado', {
            'classes': ('collapse',),
            'fields': ('ejecutada', 'pausada', 'pausa_motivo', 'total_enviados', 'panel_envios'),
        }),
    )

    def panel_envios(self, obj):
        from django.db.models import Count

        if obj is None or not obj.pk:
            return '—'
        estados = {
            fila['estado']: fila['n']
            for fila in obj.envios.values('estado').annotate(n=Count('id'))
        }
        entregas = {
            fila['estado_entrega'] or 'sin_entrega': fila['n']
            for fila in obj.envios.values('estado_entrega').annotate(n=Count('id'))
        }
        enviados = estados.get('ENVIADO', 0)
        entregados = entregas.get('delivered', 0) + entregas.get('read', 0)
        leidos = entregas.get('read', 0)
        pct_e = round(100 * entregados / enviados, 1) if enviados else 0
        pct_l = round(100 * leidos / enviados, 1) if enviados else 0
        inciertos = estados.get('INCIERTO', 0)
        return (
            f'estados {estados} · entrega {entregas} · '
            f'entregado {pct_e}% · leido {pct_l}% · inciertos {inciertos}'
        )
    panel_envios.short_description = 'Panel'

    def estado_plantilla(self, obj):
        return obj.plantilla.estado if obj.plantilla_id else '—'
    estado_plantilla.short_description = 'Estado plantilla'

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra = extra_context or {}
        if object_id:
            from django.urls import reverse

            extra['eki_meta_prueba_url'] = reverse(
                'admin:core_campanameta_enviar_prueba',
                args=[object_id],
            )
        return super().changeform_view(request, object_id, form_url, extra_context=extra)

    def get_urls(self):
        from django.urls import path

        custom = [
            path(
                '<path:object_id>/enviar-prueba/',
                self.admin_site.admin_view(self.enviar_prueba_view),
                name='core_campanameta_enviar_prueba',
            ),
        ]
        return custom + super().get_urls()

    def enviar_prueba_view(self, request, object_id):
        from django.shortcuts import get_object_or_404, redirect

        from core.meta_waba import enviar_prueba_meta
        from core.models_campana_meta import CampanaMeta

        campana = get_object_or_404(CampanaMeta, pk=object_id)
        destino = redirect('admin:core_campanameta_change', campana.pk)
        if request.method != 'POST':
            return destino
        resultado = enviar_prueba_meta(campana, request.POST.get('telefono') or '')
        nivel = messages.SUCCESS if resultado.get('success') else messages.ERROR
        self.message_user(request, resultado.get('message') or 'Listo.', level=nivel)
        return destino

    def conteo_destinatarios(self, obj):
        if obj.grupo_id:
            return obj.grupo.estudiantes.filter(activo=True).count()
        return obj.destinatarios.filter(activo=True).count()
    conteo_destinatarios.short_description = 'Destinatarios'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'plantilla':
            kwargs['queryset'] = PlantillaMeta.objects.filter(activa=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.action(description='Pausar campañas Meta')
    def pausar_campanas(self, request, queryset):
        queryset.update(pausada=True, pausa_motivo='manual')

    @admin.action(description='Reanudar campañas Meta')
    def reanudar_campanas(self, request, queryset):
        from core.campana_meta_ritmo import reanudar

        for campana in queryset:
            reanudar(campana)

    @admin.action(description='Reenviar errores reintentables (nunca inciertos)')
    def reenviar_reintentables(self, request, queryset):
        from core.models_campana_meta import EnvioCampanaMeta

        n = EnvioCampanaMeta.objects.filter(
            campana__in=queryset, estado='ERROR_REINTENTABLE',
        ).update(estado='PENDIENTE')
        self.message_user(request, f'{n} envío(s) volvieron a pendiente.')

    @admin.action(description='Ejecutar campañas Meta (envío Cloud API)')
    def ejecutar_campanas(self, request, queryset):
        from core.meta_waba import encolar_campana_meta

        for campana in queryset:
            if campana.plantilla.estado != 'APPROVED':
                self.message_user(
                    request,
                    f'{campana.nombre}: la plantilla está en {campana.plantilla.estado}. '
                    f'Solo se envía Aprobada.',
                    level=messages.ERROR,
                )
                continue
            if campana.grupo_id:
                n = campana.grupo.estudiantes.filter(activo=True).count()
            else:
                n = campana.destinatarios.filter(activo=True).count()
            if n == 0:
                self.message_user(
                    request,
                    f'{campana.nombre}: no tiene destinatarios.',
                    level=messages.WARNING,
                )
                continue
            try:
                modo = encolar_campana_meta(campana.id)
            except Exception as exc:
                self.message_user(request, f'{campana.nombre}: {exc}', level=messages.ERROR)
                continue
            self.message_user(
                request,
                f'{campana.nombre} encolada ({modo}) para {n} destinatario(s).',
                level=messages.SUCCESS,
            )
