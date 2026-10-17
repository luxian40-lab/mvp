from django import forms
from django.utils import timezone
from django.utils.html import format_html
from unfold.decorators import action

from core.admin._common import *  # noqa: F401,F403
from core.admin.agentes_v2_flag import admin_agentes_v2_activo
from core.admin import agentes_v2_textos as textos
from core.models import ConfiguracionGlobal as _ConfiguracionGlobal
from core.webhook_evento import WebhookFallido

@admin.register(_ConfiguracionGlobal)
class ConfiguracionGlobalAdmin(admin.ModelAdmin):
    """Singleton: solo permite editar la fila id=1, no agregar ni borrar."""
    list_display = ('__str__', 'content_sid_habeas_data_global', 'meta_plantilla_diploma', 'fecha_actualizacion')
    readonly_fields = ('fecha_actualizacion', 'aviso_linea_2')
    fieldsets = (
        ('Diploma por Meta', {
            'classes': ['tab'],
            'fields': ('meta_plantilla_diploma',),
            'description': (
                'Nombre de la plantilla ya aprobada en Meta. Encabezado de imagen y cuerpo '
                'con {{1}} nombre, {{2}} curso y {{3}} código. Con el nombre lleno, el botón '
                'Enviar certificados por WhatsApp usa esa plantilla (también pasadas 24 horas). '
                'Si Meta la rechaza, se intenta la imagen de la sesión. Vacío: solo la imagen, '
                'y la persona tiene que haber escrito en las últimas 24 horas.'
            ),
        }),
        ('Línea 2', {
            'classes': ['tab'],
            'description': (
                'Las dos líneas se ven en Mensajería → Líneas. '
                'eki inicia con una campaña. Aquí no se elige catálogo: '
                'la línea 2 es curso lineal hasta que la persona acaba.'
            ),
            'fields': (
                'aviso_linea_2',
            ),
        }),
        ('🛡️ Habeas Data — Plantilla Twilio general', {
            'classes': ['tab'],
            'fields': ('content_sid_habeas_data_global',),
            'description': (
                'Content SID (HX...) de la plantilla Twilio aprobada que se usa por defecto '
                'para enviar el Habeas Data cuando un cliente no tiene la suya propia. '
                'Cada Cliente puede sobrescribir este valor desde su ficha en '
                '"Habeas Data → Plantilla Twilio (Content SID del cliente)".'
            ),
        }),
        ('Auditoría', {
            'classes': ['tab'],
            'fields': ('fecha_actualizacion',),
        }),
    )

    @admin.display(description='Esta línea')
    def aviso_linea_2(self, obj):
        from django.conf import settings

        e164 = (getattr(settings, 'WHATSAPP_NUMERO_2_E164', '') or '').strip()
        if e164:
            num = f'+{e164}' if not e164.startswith('+') else e164
        else:
            num = 'sin número en el entorno'
        return format_html(
            '{} · curso lineal. eki inicia con una campaña; '
            'la persona sigue hasta acabar el curso.<br>'
            '<a href="/admin/lineas/">Ver las dos líneas</a>',
            num,
        )

    def has_add_permission(self, request):
        return not _ConfiguracionGlobal.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        from django.urls import reverse
        obj = _ConfiguracionGlobal.get_solo()
        return redirect(reverse('admin:core_configuracionglobal_change', args=[obj.pk]))


class EventoIAAdmin(admin.ModelAdmin):
    """Solo lectura — audit trail IA (Parte 2A/2B)."""

    list_display = (
        'created_at', 'tipo', 'trace_id', 'estudiante', 'regla_aplicada',
        'agente', 'es_reto', 'canal',
    )
    list_filter = ('tipo', 'canal', 'regla_aplicada', 'created_at')
    search_fields = ('trace_id', 'input_preview', 'output_preview', 'agente')
    readonly_fields = [
        f.name for f in EventoIA._meta.fields
    ]
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class ContextoAgroSessionAdmin(admin.ModelAdmin):
    list_display = ('sesion', 'cultivo', 'etapa', 'region', 'problema', 'updated_at')
    list_filter = ('cultivo', 'region')
    search_fields = ('sesion__telefono', 'cultivo', 'problema', 'region', 'municipio')
    readonly_fields = ('updated_at',)


def tabs_bandeja(request):
    """Pestañas de la bandeja. En el resto del admin no consulta nada."""
    if not admin_agentes_v2_activo(request):
        return []
    try:
        ruta_candidata = reverse('admin:agents_commercial_conversacionragcandidata_changelist')
        ruta_conocimiento = reverse('admin:core_conocimientoagente_changelist')
    except Exception:
        return []
    path = request.path or ''
    if not (path.startswith(str(ruta_candidata)) or path.startswith(str(ruta_conocimiento))):
        return []
    from core.models_agentes import ConocimientoAgente

    vista = getattr(request, 'eki_rev', None)
    if vista is None:
        vista = (request.GET.get('eki_rev') or '').strip()
    if path.startswith(str(ruta_candidata)) and not vista:
        vista = 'pendientes'
    conteos = {
        'pendientes': ConversacionRAGCandidata.objects.filter(
            estado=ConversacionRAGCandidata.ESTADO_PENDIENTE,
        ).count(),
        'aprobadas': ConversacionRAGCandidata.objects.filter(
            estado__in=(
                ConversacionRAGCandidata.ESTADO_APROBADA,
                ConversacionRAGCandidata.ESTADO_PUBLICADA,
            ),
        ).count(),
        'rechazadas': ConversacionRAGCandidata.objects.filter(
            estado=ConversacionRAGCandidata.ESTADO_RECHAZADA,
        ).count(),
        'sugeridos': ConocimientoAgente.objects.filter(
            estado=ConocimientoAgente.ESTADO_SUGERIDO,
        ).count(),
    }

    def item(clave, titulo, enlace, activa):
        return {
            'title': f'{titulo} · {conteos[clave]}',
            'link': enlace,
            'active': activa,
            'has_permission': True,
        }

    base = str(ruta_candidata)
    sugeridos = f'{ruta_conocimiento}?estado__exact=sugerido'
    return [{
        'models': [
            'agents_commercial.conversacionragcandidata',
            'core.conocimientoagente',
        ],
        'items': [
            item('pendientes', 'Pendientes', f'{base}?eki_rev=pendientes', vista == 'pendientes'),
            item('aprobadas', 'Aprobadas', f'{base}?eki_rev=aprobadas', vista == 'aprobadas'),
            item('rechazadas', 'Rechazadas', f'{base}?eki_rev=rechazadas', vista == 'rechazadas'),
            item(
                'sugeridos',
                'Sugeridos',
                sugeridos,
                path.startswith(str(ruta_conocimiento)),
            ),
        ],
    }]


class BandejaRevisionForm(forms.ModelForm):
    agentes = forms.MultipleChoiceField(
        choices=(
            ('coach', 'Coach eki'),
            ('ia_campo', 'Profesor IA'),
            ('ventas', 'Ventas eki'),
            ('finanzas', 'Experto en finanzas'),
            ('cafe', 'Experto en café'),
        ),
        required=False,
        label=textos.APLICA_A,
        widget=forms.CheckboxSelectMultiple,
        help_text='Puede marcar varios. Si no marca ninguno, la candidata queda revisada y no entra al prompt.',
    )

    class Meta:
        model = ConversacionRAGCandidata
        fields = ('respuesta_revisada', 'agentes', 'alcance', 'cliente')
        labels = {'alcance': textos.ALCANCE}
        help_texts = {'alcance': textos.ALCANCE_AYUDA}

    def clean(self):
        datos = super().clean()
        if datos.get('alcance') == 'cliente' and not datos.get('cliente'):
            self.add_error('cliente', 'Elija el cliente.')
        return datos


class ConversacionRAGCandidataAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_creacion', 'estado', 'telefono', 'cliente', 'pregunta_corta', 'revisado_por',
    )
    list_filter = ('estado', 'fecha_creacion', 'cliente')
    search_fields = ('telefono', 'pregunta', 'respuesta_nati')
    readonly_fields = ('fecha_creacion', 'fecha_revision', 'trace_id')
    actions = ['marcar_aprobada']
    actions_row = ('revisar_bandeja',)
    actions_submit_line = (
        'bandeja_a_documento',
        'bandeja_rechazar',
        'bandeja_aprobar_siguiente',
        'bandeja_aprobar',
    )

    def _consumir_ui(self, request):
        """?ui=v2 enciende la sesión. Django no debe tratar «ui» ni «eki_rev» como filtros."""
        admin_agentes_v2_activo(request)
        request.eki_rev = (request.GET.get('eki_rev') or '').strip()
        if 'ui' in request.GET or 'eki_rev' in request.GET:
            limpio = request.GET.copy()
            limpio.pop('ui', None)
            limpio.pop('eki_rev', None)
            request.GET = limpio

    def changelist_view(self, request, extra_context=None):
        self._consumir_ui(request)
        return super().changelist_view(request, extra_context)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        self._consumir_ui(request)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_list_display(self, request):
        if not admin_agentes_v2_activo(request):
            return self.list_display
        return ('pregunta_resumida', 'cliente', 'hace', 'estado_chip')

    def get_search_fields(self, request):
        if admin_agentes_v2_activo(request):
            return ('pregunta', 'respuesta_nati', 'respuesta_revisada')
        return self.search_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not admin_agentes_v2_activo(request):
            return qs
        vista = getattr(request, 'eki_rev', '') or 'pendientes'
        if vista == 'aprobadas':
            return qs.filter(estado__in=(
                ConversacionRAGCandidata.ESTADO_APROBADA,
                ConversacionRAGCandidata.ESTADO_PUBLICADA,
            ))
        if vista == 'rechazadas':
            return qs.filter(estado=ConversacionRAGCandidata.ESTADO_RECHAZADA)
        if vista == 'pendientes':
            return qs.filter(estado=ConversacionRAGCandidata.ESTADO_PENDIENTE)
        return qs

    def get_fieldsets(self, request, obj=None):
        if not admin_agentes_v2_activo(request) or obj is None:
            return super().get_fieldsets(request, obj)
        return (
            (textos.PREGUNTA, {'fields': ('pregunta_limpia',)}),
            (textos.RESPUESTA, {'fields': ('respuesta_revisada',)}),
            (textos.APLICA_A, {'fields': ('agentes', 'alcance', 'cliente')}),
            (None, {'fields': ('tarjeta_origen', 'tarjeta_antes')}),
        )

    def get_form(self, request, obj=None, **kwargs):
        if admin_agentes_v2_activo(request) and obj is not None:
            kwargs['form'] = BandejaRevisionForm
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        base = list(super().get_readonly_fields(request, obj))
        if admin_agentes_v2_activo(request) and obj is not None:
            return base + ['pregunta_limpia', 'tarjeta_origen', 'tarjeta_antes']
        return base

    def get_actions_row(self, request):
        if not admin_agentes_v2_activo(request):
            return []
        return super().get_actions_row(request)

    def get_actions_submit_line(self, request, object_id):
        if not admin_agentes_v2_activo(request):
            return []
        return super().get_actions_submit_line(request, object_id)

    def _texto_limpio(self, texto):
        from core.conocimiento_agentes import _sin_datos_personales

        return _sin_datos_personales(texto or '')

    @admin.display(description='Pregunta')
    def pregunta_corta(self, obj):
        return (obj.pregunta or '')[:80]

    @admin.display(description='Pregunta')
    def pregunta_resumida(self, obj):
        texto = self._texto_limpio(obj.pregunta)
        if len(texto) > 90:
            texto = texto[:87].rstrip() + '…'
        return texto

    @admin.display(description='Hace')
    def hace(self, obj):
        if not obj.fecha_creacion:
            return '—'
        horas = int((timezone.now() - obj.fecha_creacion).total_seconds() // 3600)
        if horas < 1:
            return 'hace menos de 1 hora'
        if horas < 48:
            return f'hace {horas} horas'
        return f'hace {horas // 24} días'

    @admin.display(description='Estado')
    def estado_chip(self, obj):
        etiquetas = {
            ConversacionRAGCandidata.ESTADO_PENDIENTE: textos.CHIP_PENDIENTE,
            ConversacionRAGCandidata.ESTADO_APROBADA: textos.CHIP_APROBADO,
            ConversacionRAGCandidata.ESTADO_RECHAZADA: textos.CHIP_RECHAZADO,
            ConversacionRAGCandidata.ESTADO_PUBLICADA: textos.CHIP_LISTO,
        }
        return etiquetas.get(obj.estado, obj.estado)

    @admin.display(description=textos.PREGUNTA)
    def pregunta_limpia(self, obj):
        return self._texto_limpio(obj.pregunta) if obj else '—'

    @admin.display(description=textos.ORIGEN)
    def tarjeta_origen(self, obj):
        return format_html('<p>{}</p>', textos.ORIGEN_CUERPO)

    @admin.display(description=textos.ANTES)
    def tarjeta_antes(self, obj):
        return format_html('<p>{}</p>', textos.ANTES_CUERPO)

    def response_change(self, request, obj):
        if admin_agentes_v2_activo(request):
            nombre = (
                f'{self.model._meta.app_label}_{self.model._meta.model_name}'
                '_bandeja_aprobar_siguiente'
            )
            if nombre in request.POST:
                siguiente = (
                    ConversacionRAGCandidata.objects.filter(
                        estado=ConversacionRAGCandidata.ESTADO_PENDIENTE,
                    )
                    .exclude(pk=obj.pk)
                    .order_by('fecha_creacion')
                    .first()
                )
                if siguiente is not None:
                    return redirect(
                        f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change',
                        siguiente.pk,
                    )
        return super().response_change(request, obj)

    @admin.action(description='Marcar aprobada (sin publicar)')
    def marcar_aprobada(self, request, queryset):
        from core.knowledge_studio import revisar_candidata

        for c in queryset.filter(estado=ConversacionRAGCandidata.ESTADO_PENDIENTE):
            revisar_candidata(c, usuario=request.user, accion='aprobar')

    @action(description=textos.REVISAR, url_path='revisar-bandeja', icon='rate_review', permissions=['change'])
    def revisar_bandeja(self, request, object_id):
        return redirect(
            f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change',
            object_id,
        )

    def _revisar(self, request, obj, accion):
        from core.knowledge_studio import revisar_candidata

        revisar_candidata(
            obj,
            usuario=request.user,
            accion=accion,
            respuesta_revisada=obj.respuesta_revisada or '',
        )
        if accion == 'aprobar':
            from core.conocimiento_agentes import copiar_candidata_a_agentes

            copiar_candidata_a_agentes(obj, request.user)

    @action(description=textos.APROBAR, url_path='bandeja-aprobar', permissions=['change'])
    def bandeja_aprobar(self, request, obj):
        self._revisar(request, obj, 'aprobar')

    @action(description=textos.APROBAR_SIGUIENTE, url_path='bandeja-aprobar-siguiente', permissions=['change'])
    def bandeja_aprobar_siguiente(self, request, obj):
        self._revisar(request, obj, 'aprobar')

    @action(description=textos.RECHAZAR, url_path='bandeja-rechazar', permissions=['change'])
    def bandeja_rechazar(self, request, obj):
        self._revisar(request, obj, 'rechazar')

    @action(description=textos.A_DOCUMENTO, url_path='bandeja-documento', permissions=['change'])
    def bandeja_a_documento(self, request, obj):
        from core.knowledge_studio import publicar_candidata_en_rag

        publicar_candidata_en_rag(obj, usuario=request.user)


@admin.register(AlertaTerritorial)
class AlertaTerritorialAdmin(admin.ModelAdmin):
    list_display = (
        'actualizado_en', 'familia', 'subtipo', 'territory_id',
        'conteo', 'score', 'estado', 'ventana_horas',
    )
    list_filter = ('estado', 'familia')
    search_fields = ('territory_id', 'familia', 'explicacion')
    readonly_fields = ('creado_en', 'actualizado_en')
    actions = ('accion_validar', 'accion_cerrar')

    @admin.action(description='Validar (detectada → validada)')
    def accion_validar(self, request, queryset):
        from core.alerta_territorial_ops import transicionar_alerta

        ok = 0
        for a in queryset.filter(estado=AlertaTerritorial.ESTADO_DETECTADA):
            try:
                transicionar_alerta(
                    a,
                    nuevo_estado=AlertaTerritorial.ESTADO_VALIDADA,
                    usuario=request.user,
                    nota='admin_action',
                )
                ok += 1
            except ValueError:
                continue
        self.message_user(request, f'Validadas: {ok}')

    @admin.action(description='Cerrar alertas seleccionadas')
    def accion_cerrar(self, request, queryset):
        from core.alerta_territorial_ops import transicionar_alerta

        ok = 0
        for a in queryset.exclude(estado=AlertaTerritorial.ESTADO_CERRADA):
            try:
                transicionar_alerta(
                    a,
                    nuevo_estado=AlertaTerritorial.ESTADO_CERRADA,
                    usuario=request.user,
                    nota='admin_action',
                )
                ok += 1
            except ValueError:
                continue
        self.message_user(request, f'Cerradas: {ok}')


@admin.register(EventOutbox)
class EventOutboxAdmin(admin.ModelAdmin):
    list_display = (
        'ingested_at', 'event_type', 'territory_id', 'org_id',
        'published_at', 'pii_class',
    )
    list_filter = ('event_type', 'pii_class')
    search_fields = ('event_id', 'event_type', 'territory_id', 'lake_uri')
    readonly_fields = [f.name for f in EventOutbox._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(SenalTerritorial)
class SenalTerritorialAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'tipo', 'territory_id', 'confianza', 'fuente', 'org_id')
    list_filter = ('fuente', 'tipo')
    search_fields = ('tipo', 'territory_id')
    readonly_fields = ('creado_en',)


@admin.register(WebhookFallido)
class WebhookFallidoAdmin(admin.ModelAdmin):
    """Solo staff y solo lectura. El payload tiene el teléfono."""

    list_display = ('creado', 'canal', 'external_id', 'error_corto')
    list_filter = ('canal', 'creado')
    search_fields = ('external_id', 'canal')
    readonly_fields = ('canal', 'external_id', 'payload', 'error', 'creado')
    ordering = ('-creado',)

    def error_corto(self, obj):
        return (obj.error or '')[:80]

    error_corto.short_description = 'error'

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        return {
            clave: accion
            for clave, accion in actions.items()
            if 'export' not in clave.lower()
        }


@admin.register(SandboxCanalSesion)
class SandboxCanalSesionAdmin(admin.ModelAdmin):
    list_display = (
        'actualizado_en', 'telefono', 'phone_id', 'modo', 'plan',
        'preguntas_mes', 'racha_actual', 'creado_en',
    )
    list_filter = ('modo', 'plan', 'phone_id')
    search_fields = ('telefono',)
    readonly_fields = (
        'creado_en',
        'actualizado_en',
        'preguntas_mes',
        'preguntas_mes_desde',
        'racha_actual',
        'racha_maxima',
        'racha_ultimo_dia',
        'aviso_pendiente',
    )

