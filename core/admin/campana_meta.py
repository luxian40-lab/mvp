"""Admin Unfold: campañas Meta. El envío a Graph sigue en meta_waba."""
import json

from django import forms
from django.contrib import admin, messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.decorators import action, display
from unfold.forms import BaseDialogForm

from core.admin._common import *  # noqa: F401,F403
from core.admin.plantilla_meta_admin import PlantillaMetaAdmin  # noqa: F401
from core.campana_audiencia import (
    ORIGENES,
    SI_FALTA,
    avisos_compatibilidad,
    con_conteos,
    embudo,
    estado_campana,
    etiqueta_grupo,
    etiqueta_persona,
    filtrar_estado,
    motivo_fallo,
    nombre_linea,
    numeros_de_prueba,
    numero_de_prueba_permitido,
    personas_que_reciben,
    puede_reintentar,
    reglas_efectivas,
    resumir_audiencia,
    sugerir_plantilla,
    texto_confirmacion,
    texto_embudo,
    vista_previa,
)
from core.models_campana_meta import CampanaMeta, EnvioCampanaMeta, PlantillaMeta
from core.plantilla_meta_editor import lineas_disponibles


class ConfirmarEnvioForm(BaseDialogForm):
    confirma = forms.BooleanField(label='Confirmo estos números', required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.campana = (
            CampanaMeta.objects.filter(pk=self.object_id).select_related('plantilla').first()
            if self.object_id else None
        )
        if self.campana is not None:
            self.fields['confirma'].label = texto_confirmacion(self.campana)

    def clean(self):
        limpio = super().clean()
        campana = self.campana
        if campana is None or not campana.plantilla_id or campana.plantilla.estado != 'APPROVED':
            self.add_error('confirma', 'Meta todavía no aprobó esta plantilla.')
        elif resumir_audiencia(campana)['reciben'] == 0:
            self.add_error('confirma', 'No hay personas que reciban esta campaña.')
        return limpio


class CampanaVistaFilter(admin.SimpleListFilter):
    title = 'Estado'
    parameter_name = 'eki_cm'

    def lookups(self, request, model_admin):
        return (
            ('borradores', 'Borradores'),
            ('programadas', 'Programadas'),
            ('enviadas', 'Enviadas'),
            ('errores', 'Con errores'),
        )

    def queryset(self, request, queryset):
        return filtrar_estado(queryset, self.value() or '')


class CampanaMetaForm(forms.ModelForm):
    personas_ids = forms.CharField(required=False, widget=forms.HiddenInput)
    grupos_ids = forms.CharField(required=False, widget=forms.HiddenInput)
    reglas_json = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = CampanaMeta
        fields = (
            'nombre',
            'cliente',
            'plantilla',
            'phone_number_id',
            'fecha_programada',
            'dias_repeticion',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = PlantillaMeta.objects.filter(activa=True, estado='APPROVED')
        instancia = self.instance
        if instancia.pk and instancia.plantilla_id and instancia.plantilla.estado != 'APPROVED':
            qs = PlantillaMeta.objects.filter(pk__in=list(qs.values_list('pk', flat=True)) + [instancia.plantilla_id])
        self.fields['plantilla'].queryset = qs.order_by('nombre_interno')
        self.fields['plantilla'].label_from_instance = lambda obj: obj.nombre_interno
        self.fields['plantilla'].label = 'Plantilla'
        lineas = lineas_disponibles()
        self.fields['phone_number_id'] = forms.ChoiceField(
            label='Línea',
            required=False,
            choices=lineas or [('', 'Sin línea configurada')],
        )
        if instancia.pk and instancia.phone_number_id:
            self.fields['phone_number_id'].initial = instancia.phone_number_id
        elif lineas:
            self.fields['phone_number_id'].initial = lineas[0][0]
        self.fields['fecha_programada'].label = 'Fecha y hora'
        self.fields['fecha_programada'].help_text = 'Vacío envía ahora. La hora es la de Bogotá.'
        self.fields['dias_repeticion'].label = 'No repetir esta plantilla antes de (días)'
        self.fields['nombre'].label = 'Nombre de la campaña'
        self.fields['cliente'].label = 'Cliente'
        self.fields['cliente'].required = False
        self.fields['cliente'].help_text = 'Opcional. Solo acota los grupos y las personas que se ofrecen.'
        if instancia.pk:
            self.fields['personas_ids'].initial = ','.join(
                str(pk) for pk in instancia.destinatarios.values_list('pk', flat=True)
            )
            grupos = list(instancia.grupos.values_list('pk', flat=True))
            if instancia.grupo_id and instancia.grupo_id not in grupos:
                grupos.append(instancia.grupo_id)
            self.fields['grupos_ids'].initial = ','.join(str(pk) for pk in grupos)
            self.fields['reglas_json'].initial = json.dumps(reglas_efectivas(instancia), ensure_ascii=False)
        else:
            self.fields['reglas_json'].initial = '{}'


def tabs_campana_meta(request):
    try:
        ruta = reverse('admin:core_campanameta_changelist')
    except Exception:
        return []
    if not (request.path or '').startswith(str(ruta)):
        return []
    from core.campana_audiencia import conteos_estado

    conteos = conteos_estado(CampanaMeta.objects.all())
    vista = request.GET.get('eki_cm') or ''
    if vista not in conteos:
        vista = ''

    def item(clave, titulo):
        enlace = str(ruta) if not clave else f'{ruta}?eki_cm={clave}'
        return {
            'title': f'{titulo} · {conteos[clave]}',
            'link': enlace,
            'active': vista == clave,
            'has_permission': True,
        }

    return [{
        'models': ['core.campanameta'],
        'items': [
            item('', 'Todas'),
            item('borradores', 'Borradores'),
            item('programadas', 'Programadas'),
            item('enviadas', 'Enviadas'),
            item('errores', 'Con errores'),
        ],
    }]


def _ids(texto: str) -> list[int]:
    salida = []
    for parte in (texto or '').split(','):
        parte = parte.strip()
        if parte.isdigit():
            salida.append(int(parte))
    return salida


def _guardar_audiencia(campana, datos: dict) -> None:
    from core.campana_audiencia import aplicar_mapeo

    if 'reglas_json' in datos:
        try:
            reglas = json.loads(datos.get('reglas_json') or '{}')
        except json.JSONDecodeError:
            reglas = {}
        if isinstance(reglas, dict):
            campana.reglas_variables = reglas
    if campana.plantilla_id:
        aplicar_mapeo(campana)
    campana.grupo_id = None
    campana.save()
    if 'personas_ids' in datos:
        campana.destinatarios.set(_ids(datos.get('personas_ids') or ''))
    if 'grupos_ids' in datos:
        campana.grupos.set(_ids(datos.get('grupos_ids') or ''))


def _contexto_ficha(campana: CampanaMeta) -> dict:
    resumen = resumir_audiencia(campana) if campana.pk else {
        'suma': 0, 'repetidas': 0, 'optout': 0, 'recientes': 0,
        'sin_whatsapp': 0, 'sin_variable': 0, 'reciben': 0, 'dias': 14,
        'ejemplo_id': None, 'sin_organizacion': 0,
    }
    previa = vista_previa(campana)
    alternativa = sugerir_plantilla(campana, resumen) if campana.pk and campana.plantilla_id else None
    personas = []
    grupos = []
    if campana.pk:
        from core.models import Estudiante
        from core.models_extras import GrupoEstudiantes

        ids_personas = list(campana.destinatarios.values_list('pk', flat=True))
        for est in Estudiante.objects.filter(pk__in=ids_personas).select_related('cliente'):
            personas.append({'id': est.pk, 'etiqueta': etiqueta_persona(est)})
        ids_grupos = list(campana.grupos.values_list('pk', flat=True))
        if campana.grupo_id and campana.grupo_id not in ids_grupos:
            ids_grupos.append(campana.grupo_id)
        for grupo in GrupoEstudiantes.objects.filter(pk__in=ids_grupos):
            grupos.append({'id': grupo.pk, 'etiqueta': etiqueta_grupo(grupo)})
    envios = []
    datos_embudo = embudo(campana)
    if campana.pk:
        for envio in campana.envios.select_related('estudiante', 'estudiante__cliente').order_by('estudiante__nombre'):
            envios.append({
                'etiqueta': etiqueta_persona(envio.estudiante),
                'estado': envio.get_estado_display(),
                'entrega': _etiqueta_entrega(envio),
                'motivo': motivo_fallo(envio) if envio.estado in ('ERROR', 'FALLIDO', 'ERROR_REINTENTABLE') else '',
                'reintentar': puede_reintentar(envio),
            })
    aprobada = bool(campana.plantilla_id and campana.plantilla.estado == 'APPROVED')
    return {
        'resumen': resumen,
        'previa': previa,
        'avisos': avisos_compatibilidad(campana, resumen) if campana.pk else [],
        'alternativa': alternativa,
        'personas_ui': personas,
        'grupos_ui': grupos,
        'reglas_ui': reglas_efectivas(campana) if campana.plantilla_id else {},
        'origenes': ORIGENES,
        'si_falta': SI_FALTA,
        'embudo': datos_embudo,
        'envios_ui': envios,
        'hay_reintento': any(fila['reintentar'] for fila in envios),
        'confirmacion': texto_confirmacion(campana, resumen) if campana.pk else '',
        'linea': nombre_linea(campana) if campana.pk else 'Línea principal',
        'aprobada': aprobada,
        'mostrar_resultado': bool(campana.pk and (campana.ejecutada or campana.envios.exists())),
        'prueba_numero': (numeros_de_prueba() or ['573026480629'])[0],
        'programada': bool(campana.fecha_programada),
    }


def _etiqueta_entrega(envio) -> str:
    entrega = (envio.estado_entrega or '').strip()
    return {
        'sent': 'Enviado a Meta',
        'delivered': 'Entregado',
        'read': 'Leído',
        'failed': 'Falló la entrega',
    }.get(entrega, 'Sin dato')


@admin.register(CampanaMeta)
class CampanaMetaAdmin(admin.ModelAdmin):
    form = CampanaMetaForm
    change_form_template = 'admin/core/campanameta/change_form.html'
    list_display = ('col_campana', 'col_audiencia', 'col_estado', 'col_resultado')
    list_display_links = ('col_campana',)
    list_filter = (CampanaVistaFilter, 'cliente')
    search_fields = ('nombre', 'plantilla__meta_name', 'plantilla__nombre_interno')
    search_help_text = 'Buscar'
    autocomplete_fields = ('cliente',)
    list_per_page = 50
    actions_list = ('nueva_campana',)
    actions_list_hide_default = True
    actions_row = ('enviar_ahora', 'programar', 'duplicar_campana', 'ver_resultado')
    actions = ['ejecutar_campanas', 'pausar_campanas', 'reanudar_campanas', 'reenviar_reintentables']

    fieldsets = (
        ('Campaña', {'fields': ('nombre',)}),
        ('Plantilla de Meta', {'fields': ('cliente', 'plantilla')}),
        ('Envío', {'fields': ('phone_number_id', 'fecha_programada', 'dias_repeticion')}),
    )

    class Media:
        css = {'all': ('admin/css/campana_meta_admin.css',)}
        js = ('admin/js/campana_meta_admin.js',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'plantilla':
            kwargs['queryset'] = PlantillaMeta.objects.filter(activa=True, estado='APPROVED')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('plantilla', 'cliente', 'grupo')
        return con_conteos(qs)

    def get_urls(self):
        custom = [
            path(
                'buscar-personas/',
                self.admin_site.admin_view(self.buscar_personas_view),
                name='core_campanameta_buscar_personas',
            ),
            path(
                'buscar-grupos/',
                self.admin_site.admin_view(self.buscar_grupos_view),
                name='core_campanameta_buscar_grupos',
            ),
            path(
                'plantilla/<int:plantilla_id>/variables/',
                self.admin_site.admin_view(self.variables_plantilla_view),
                name='core_campanameta_variables',
            ),
            path(
                '<path:object_id>/autoguardar/',
                self.admin_site.admin_view(self.autoguardar_view),
                name='core_campanameta_autoguardar',
            ),
            path(
                '<path:object_id>/audiencia/',
                self.admin_site.admin_view(self.audiencia_view),
                name='core_campanameta_audiencia',
            ),
            path(
                '<path:object_id>/lista/',
                self.admin_site.admin_view(self.lista_view),
                name='core_campanameta_lista',
            ),
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
            path(
                '<path:object_id>/reintentar/',
                self.admin_site.admin_view(self.reintentar_view),
                name='core_campanameta_reintentar',
            ),
        ]
        return custom + super().get_urls()

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra = extra_context or {}
        campana = None
        if object_id:
            campana = (
                CampanaMeta.objects.filter(pk=object_id)
                .select_related('plantilla', 'cliente')
                .first()
            )
        if campana is not None:
            extra.update(_contexto_ficha(campana))
            extra['eki_meta_prueba_url'] = reverse('admin:core_campanameta_enviar_prueba', args=[object_id])
            extra['eki_meta_enviar_url'] = reverse('admin:core_campanameta_enviar', args=[object_id])
            extra['eki_meta_reintentar_url'] = reverse('admin:core_campanameta_reintentar', args=[object_id])
            extra['eki_meta_lista_url'] = reverse('admin:core_campanameta_lista', args=[object_id])
            extra['eki_meta_autoguardar_url'] = reverse('admin:core_campanameta_autoguardar', args=[object_id])
            extra['eki_meta_audiencia_url'] = reverse('admin:core_campanameta_audiencia', args=[object_id])
            n = extra['resumen']['reciben']
            extra['eki_meta_destinatarios'] = n
            extra['eki_meta_puede_enviar'] = extra['aprobada'] and n > 0
            if not extra['aprobada']:
                extra['eki_meta_envio_bloqueo'] = 'Meta todavía no aprobó esta plantilla.'
            elif n == 0:
                extra['eki_meta_envio_bloqueo'] = 'Agregue un grupo o personas y guarde.'
        extra['eki_buscar_personas'] = reverse('admin:core_campanameta_buscar_personas')
        extra['eki_buscar_grupos'] = reverse('admin:core_campanameta_buscar_grupos')
        extra.setdefault('previa', {'cuerpo': '', 'header': '', 'footer': '', 'botones': [], 'persona': ''})
        extra.setdefault('resumen', {'reciben': 0, 'suma': 0, 'repetidas': 0, 'optout': 0, 'recientes': 0, 'sin_whatsapp': 0, 'sin_variable': 0, 'dias': 14})
        extra.setdefault('avisos', [])
        extra.setdefault('reglas_ui', {})
        extra.setdefault('origenes', ORIGENES)
        extra.setdefault('si_falta', SI_FALTA)
        extra.setdefault('grupos_ui', [])
        extra.setdefault('personas_ui', [])
        extra.setdefault('mostrar_resultado', False)
        extra.setdefault('linea', 'Línea principal')
        extra.setdefault('embudo', {})
        extra.setdefault('envios_ui', [])
        return super().changeform_view(request, object_id, form_url, extra_context=extra)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        datos = {
            'personas_ids': request.POST.get('personas_ids', ''),
            'grupos_ids': request.POST.get('grupos_ids', ''),
            'reglas_json': request.POST.get('reglas_json', ''),
        }
        if not request.POST.get('fecha_programada'):
            form.instance.fecha_programada = None
        _guardar_audiencia(form.instance, datos)

    def col_campana(self, obj):
        linea = nombre_linea(obj)
        if not obj.plantilla_id:
            return format_html('<div class="eki-cm-campana"><strong>{}</strong><div class="eki-cm-sub">{}</div></div>', obj.nombre, linea)
        url = reverse('admin:core_plantillameta_change', args=[obj.plantilla_id])
        chip = ''
        if obj.plantilla.estado != 'APPROVED':
            chip = format_html(
                ' <span class="eki-cm-chip">{}</span>',
                obj.plantilla.get_estado_display(),
            )
        return format_html(
            '<div class="eki-cm-campana"><strong>{}</strong>'
            '<div class="eki-cm-sub"><a href="{}">{}</a>{} · {}</div></div>',
            obj.nombre,
            url,
            obj.plantilla.nombre_interno,
            chip,
            linea,
        )
    col_campana.short_description = 'Campaña'

    def col_audiencia(self, obj):
        resumen = resumir_audiencia(obj)
        n_grupos = obj.grupos.count()
        if obj.grupo_id and not obj.grupos.filter(pk=obj.grupo_id).exists():
            n_grupos += 1
        n_personas = obj.destinatarios.count()
        if n_grupos and n_personas:
            tipo = f'{n_grupos} grupos y {n_personas} personas'
        elif n_grupos == 1:
            tipo = '1 grupo'
        elif n_grupos:
            tipo = f'{n_grupos} grupos'
        elif n_personas:
            tipo = f'{n_personas} personas'
        else:
            tipo = 'Sin audiencia'
        extra = ''
        clave, _etiqueta = estado_campana(obj)
        if clave == 'programada' and obj.fecha_programada:
            extra = format_html(
                '<div class="eki-cm-sub">{} · {} personas recibirán el mensaje</div>',
                timezone.localtime(obj.fecha_programada).strftime('%d/%m/%Y %H:%M'),
                resumen['reciben'],
            )
        return format_html(
            '<div>{}<div class="eki-cm-sub">{} personas</div>{}</div>',
            tipo,
            resumen['reciben'],
            extra,
        )
    col_audiencia.short_description = 'Audiencia'

    @display(
        description='Estado',
        label={
            'Borrador': 'info',
            'Programada': 'warning',
            'Enviando': 'warning',
            'Enviada': 'success',
            'Con errores': 'danger',
        },
    )
    def col_estado(self, obj):
        _clave, etiqueta = estado_campana(obj)
        return etiqueta

    def col_resultado(self, obj):
        datos = embudo(obj)
        fallo = ''
        if datos['fallidos']:
            fallo = format_html(' <span class="eki-cm-chip">{} fallidos</span>', datos['fallidos'])
        return format_html('<span class="eki-cm-funnel">{}</span>{}', texto_embudo(datos), fallo)
    col_resultado.short_description = 'Resultado'

    @action(description='Nueva campaña', url_path='nueva', icon='add', permissions=['add'])
    def nueva_campana(self, request):
        return redirect('admin:core_campanameta_add')

    @action(
        description='Enviar ahora',
        url_path='enviar-ahora',
        icon='send',
        permissions=['change'],
        dialog={
            'title': 'Enviar ahora',
            'description': 'Revise los números antes de enviar. Esta acción no se puede deshacer.',
            'form_class': ConfirmarEnvioForm,
            'form_submit_text': 'Enviar',
        },
    )
    def enviar_ahora(self, request, form, object_id):
        campana = get_object_or_404(CampanaMeta.objects.select_related('plantilla'), pk=object_id)
        self._lanzar_una(request, campana)
        return redirect('admin:core_campanameta_changelist')

    @action(description='Programar', url_path='programar', icon='schedule', permissions=['change'])
    def programar(self, request, object_id):
        return redirect(reverse('admin:core_campanameta_change', args=[object_id]) + '#envio')

    @action(description='Duplicar', url_path='duplicar', icon='content_copy', permissions=['add'])
    def duplicar_campana(self, request, object_id):
        origen = get_object_or_404(
            CampanaMeta.objects.select_related('plantilla'),
            pk=object_id,
        )
        copia = CampanaMeta.objects.create(
            nombre=f'{origen.nombre} (copia)'[:120],
            cliente=origen.cliente,
            plantilla=origen.plantilla,
            mapeo_header=origen.mapeo_header,
            mapeo_body=origen.mapeo_body,
            mapeo_boton=origen.mapeo_boton,
            phone_number_id=origen.phone_number_id,
            dias_repeticion=origen.dias_repeticion,
            reglas_variables=origen.reglas_variables or {},
        )
        copia.destinatarios.set(origen.destinatarios.all())
        copia.grupos.set(origen.grupos.all())
        if origen.grupo_id:
            copia.grupos.add(origen.grupo_id)
        self.message_user(request, 'Campaña duplicada. Sigue en borrador.', level=messages.SUCCESS)
        return redirect('admin:core_campanameta_change', copia.pk)

    @action(description='Ver resultado', url_path='ver-resultado', icon='insights', permissions=['view'])
    def ver_resultado(self, request, object_id):
        return redirect(reverse('admin:core_campanameta_change', args=[object_id]) + '#resultado')

    def buscar_personas_view(self, request):
        from core.models import Estudiante

        q = (request.GET.get('q') or '').strip()
        cliente = (request.GET.get('cliente') or '').strip()
        qs = Estudiante.objects.filter(activo=True).select_related('cliente')
        if cliente.isdigit():
            qs = qs.filter(cliente_id=int(cliente))
        if q:
            qs = qs.filter(
                models.Q(nombre__icontains=q)
                | models.Q(telefono__icontains=q)
                | models.Q(cliente__nombre__icontains=q)
            )
        filas = [{'id': est.pk, 'etiqueta': etiqueta_persona(est)} for est in qs.order_by('nombre')[:20]]
        return JsonResponse({'resultados': filas})

    def buscar_grupos_view(self, request):
        from core.models_extras import GrupoEstudiantes

        q = (request.GET.get('q') or '').strip()
        cliente = (request.GET.get('cliente') or '').strip()
        qs = GrupoEstudiantes.objects.filter(activo=True)
        if cliente.isdigit():
            qs = qs.filter(cliente_id=int(cliente))
        if q:
            qs = qs.filter(models.Q(nombre__icontains=q) | models.Q(cliente__nombre__icontains=q))
        filas = [{'id': grupo.pk, 'etiqueta': etiqueta_grupo(grupo)} for grupo in qs.order_by('nombre')[:20]]
        return JsonResponse({'resultados': filas})

    def variables_plantilla_view(self, request, plantilla_id):
        plantilla = get_object_or_404(PlantillaMeta, pk=plantilla_id, estado='APPROVED', activa=True)
        campana = CampanaMeta(plantilla=plantilla, mapeo_body='', reglas_variables={})
        return JsonResponse({'reglas': reglas_efectivas(campana), 'nombre': plantilla.nombre_interno})

    def autoguardar_view(self, request, object_id):
        if request.method != 'POST':
            return JsonResponse({'ok': False}, status=405)
        campana = get_object_or_404(CampanaMeta.objects.select_related('plantilla'), pk=object_id)
        nombre = (request.POST.get('nombre') or campana.nombre).strip()
        if nombre:
            campana.nombre = nombre[:120]
        plantilla_id = (request.POST.get('plantilla') or '').strip()
        if plantilla_id.isdigit():
            plantilla = PlantillaMeta.objects.filter(pk=int(plantilla_id), estado='APPROVED', activa=True).first()
            if plantilla is not None:
                campana.plantilla = plantilla
        cliente_id = (request.POST.get('cliente') or '').strip()
        if cliente_id.isdigit():
            campana.cliente_id = int(cliente_id)
        elif cliente_id == '':
            campana.cliente_id = None
        linea = (request.POST.get('phone_number_id') or '').strip()
        if linea:
            campana.phone_number_id = linea[:32]
        dias = (request.POST.get('dias_repeticion') or '').strip()
        if dias.isdigit():
            campana.dias_repeticion = max(0, min(int(dias), 3650))
        fecha = (request.POST.get('fecha_programada') or '').strip()
        if fecha:
            from django.utils.dateparse import parse_datetime

            momento = parse_datetime(fecha)
            if momento is not None:
                if timezone.is_naive(momento):
                    momento = timezone.make_aware(momento, timezone.get_current_timezone())
                campana.fecha_programada = momento
        else:
            campana.fecha_programada = None
        _guardar_audiencia(campana, request.POST)
        campana.refresh_from_db()
        ficha = _contexto_ficha(campana)
        return JsonResponse({
            'ok': True,
            'resumen': ficha['resumen'],
            'confirmacion': ficha['confirmacion'],
            'previa': ficha['previa'],
            'reglas': ficha['reglas_ui'],
            'avisos': ficha['avisos'],
            'alternativa_id': ficha['alternativa'].pk if ficha['alternativa'] else None,
            'alternativa_nombre': ficha['alternativa'].nombre_interno if ficha['alternativa'] else '',
        })

    def audiencia_view(self, request, object_id):
        campana = get_object_or_404(CampanaMeta.objects.select_related('plantilla'), pk=object_id)
        if request.method == 'POST':
            _guardar_audiencia(campana, request.POST)
            campana.refresh_from_db()
        resumen = resumir_audiencia(campana)
        return JsonResponse({'ok': True, 'resumen': resumen, 'confirmacion': texto_confirmacion(campana, resumen)})

    def lista_view(self, request, object_id):
        campana = get_object_or_404(CampanaMeta.objects.select_related('plantilla'), pk=object_id)
        resumen = resumir_audiencia(campana)
        from core.models import Estudiante

        orden = {pk: n for n, pk in enumerate(resumen['reciben_ids'])}
        personas = list(Estudiante.objects.filter(pk__in=resumen['reciben_ids']).select_related('cliente'))
        personas.sort(key=lambda est: orden.get(est.pk, 0))
        return render(request, 'admin/core/campanameta/lista.html', {
            'title': f'Lista de {campana.nombre}',
            'campana': campana,
            'filas': [etiqueta_persona(est) for est in personas],
            'opts': self.model._meta,
        })

    def enviar_prueba_view(self, request, object_id):
        from core.meta_waba import enviar_prueba_meta

        campana = get_object_or_404(CampanaMeta.objects.select_related('plantilla'), pk=object_id)
        destino = redirect('admin:core_campanameta_change', campana.pk)
        if request.method != 'POST':
            return destino
        telefono = request.POST.get('telefono') or (numeros_de_prueba() or ['573026480629'])[0]
        if not numero_de_prueba_permitido(telefono):
            self.message_user(
                request,
                'La prueba solo sale a los números autorizados. No se usa un número de cliente.',
                level=messages.ERROR,
            )
            return destino
        if not campana.plantilla_id or campana.plantilla.estado != 'APPROVED':
            self.message_user(request, 'Meta todavía no aprobó esta plantilla.', level=messages.ERROR)
            return destino
        resultado = enviar_prueba_meta(campana, telefono)
        nivel = messages.SUCCESS if resultado.get('success') else messages.ERROR
        self.message_user(request, resultado.get('message') or 'Listo.', level=nivel)
        return destino

    def enviar_campana_view(self, request, object_id):
        campana = get_object_or_404(
            CampanaMeta.objects.select_related('plantilla', 'grupo'),
            pk=object_id,
        )
        destino = redirect('admin:core_campanameta_change', campana.pk)
        if request.method != 'POST':
            return destino
        if campana.plantilla_id and campana.plantilla.estado != 'APPROVED':
            campana.pausada = True
            campana.pausa_motivo = 'plantilla_no_aprobada'
            campana.save(update_fields=['pausada', 'pausa_motivo'])
            self.message_user(request, 'Meta todavía no aprobó esta plantilla.', level=messages.ERROR)
            return destino
        resumen = resumir_audiencia(campana)
        esperado = (request.POST.get('reciben') or '').strip()
        if esperado and esperado != str(resumen['reciben']):
            self.message_user(
                request,
                'La audiencia cambió. Revise los números y confirme otra vez.',
                level=messages.ERROR,
            )
            return destino
        self._lanzar_una(request, campana)
        return destino

    def reintentar_view(self, request, object_id):
        from core.meta_waba import encolar_campana_meta

        campana = get_object_or_404(CampanaMeta.objects.select_related('plantilla'), pk=object_id)
        destino = redirect('admin:core_campanameta_change', campana.pk)
        if request.method != 'POST':
            return destino
        if not any(puede_reintentar(envio) for envio in campana.envios.all()):
            self.message_user(request, 'No hay fallos transitorios para reintentar.', level=messages.WARNING)
            return destino
        if not campana.plantilla_id or campana.plantilla.estado != 'APPROVED':
            self.message_user(request, 'Meta todavía no aprobó esta plantilla.', level=messages.ERROR)
            return destino
        try:
            modo = encolar_campana_meta(campana.id)
        except Exception as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return destino
        self.message_user(request, f'Reintento encolado ({modo}).', level=messages.SUCCESS)
        return destino

    def _destinatarios_activos(self, campana):
        return resumir_audiencia(campana)['reciben']

    def _lanzar_una(self, request, campana):
        from core.meta_waba import encolar_campana_meta

        if not campana.plantilla_id or campana.plantilla.estado != 'APPROVED':
            self.message_user(
                request,
                'Meta todavía no aprobó esta plantilla.',
                level=messages.ERROR,
            )
            return
        n = self._destinatarios_activos(campana)
        if n == 0:
            self.message_user(request, f'{campana.nombre}: no tiene destinatarios.', level=messages.WARNING)
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

    @admin.action(description='Ejecutar campañas Meta (envío Cloud API)')
    def ejecutar_campanas(self, request, queryset):
        for campana in queryset.select_related('plantilla'):
            self._lanzar_una(request, campana)

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
        n = EnvioCampanaMeta.objects.filter(
            campana__in=queryset, estado='ERROR_REINTENTABLE',
        ).update(estado='PENDIENTE')
        self.message_user(request, f'{n} envío(s) volvieron a pendiente.')
