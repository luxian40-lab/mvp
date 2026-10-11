"""Admin Unfold: campañas Meta. Las plantillas viven en plantilla_meta_admin."""
from django.contrib import admin, messages

from core.admin._common import *  # noqa: F401,F403
from core.admin.plantilla_meta_admin import PlantillaMetaAdmin  # noqa: F401
from core.models_campana_meta import CampanaMeta, PlantillaMeta

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

            from core.models_campana_meta import CampanaMeta

            campana = CampanaMeta.objects.filter(pk=object_id).select_related('plantilla').first()
            extra['eki_meta_prueba_url'] = reverse(
                'admin:core_campanameta_enviar_prueba',
                args=[object_id],
            )
            extra['eki_meta_enviar_url'] = reverse(
                'admin:core_campanameta_enviar',
                args=[object_id],
            )
            if campana is not None:
                n = self._destinatarios_activos(campana)
                aprobada = bool(campana.plantilla_id and campana.plantilla.estado == 'APPROVED')
                extra['eki_meta_destinatarios'] = n
                extra['eki_meta_puede_enviar'] = aprobada and n > 0
                if not aprobada:
                    extra['eki_meta_envio_bloqueo'] = 'Meta todavía no aprobó esta plantilla.'
                elif n == 0:
                    extra['eki_meta_envio_bloqueo'] = 'Agregue un grupo o personas y guarde.'
        return super().changeform_view(request, object_id, form_url, extra_context=extra)

    def get_urls(self):
        from django.urls import path

        custom = [
            path(
                '<path:object_id>/enviar-prueba/',
                self.admin_site.admin_view(self.enviar_prueba_view),
                name='core_campanameta_enviar_prueba',
            ),
            path(
                '<path:object_id>/enviar/',
                self.admin_site.admin_view(self.enviar_campana_view),
                name='core_campanameta_enviar',
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

    def enviar_campana_view(self, request, object_id):
        from django.shortcuts import get_object_or_404, redirect

        from core.models_campana_meta import CampanaMeta

        campana = get_object_or_404(
            CampanaMeta.objects.select_related('plantilla', 'grupo'),
            pk=object_id,
        )
        destino = redirect('admin:core_campanameta_change', campana.pk)
        if request.method != 'POST':
            return destino
        self._lanzar_una(request, campana)
        return destino

    def conteo_destinatarios(self, obj):
        return self._destinatarios_activos(obj)
    conteo_destinatarios.short_description = 'Destinatarios'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'plantilla':
            kwargs['queryset'] = PlantillaMeta.objects.filter(activa=True, estado='APPROVED')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def _destinatarios_activos(self, campana):
        if campana.grupo_id:
            return campana.grupo.estudiantes.filter(activo=True).count()
        return campana.destinatarios.filter(activo=True).count()

    def _lanzar_una(self, request, campana):
        from core.meta_waba import encolar_campana_meta

        if not campana.plantilla_id or campana.plantilla.estado != 'APPROVED':
            estado = campana.plantilla.estado if campana.plantilla_id else 'sin plantilla'
            self.message_user(
                request,
                f'{campana.nombre}: la plantilla está en {estado}. Solo se envía Aprobada.',
                level=messages.ERROR,
            )
            return
        n = self._destinatarios_activos(campana)
        if n == 0:
            self.message_user(
                request,
                f'{campana.nombre}: no tiene destinatarios.',
                level=messages.WARNING,
            )
            return
        try:
            modo = encolar_campana_meta(campana.id)
        except Exception as exc:
            self.message_user(request, f'{campana.nombre}: {exc}', level=messages.ERROR)
            return
        self.message_user(
            request,
            f'{campana.nombre} encolada ({modo}) para {n} destinatario(s).',
            level=messages.SUCCESS,
        )

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
        for campana in queryset:
            self._lanzar_una(request, campana)
