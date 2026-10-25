"""Listado y asistente de Plantillas Meta dentro de Unfold."""
from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.decorators import action, display
from unfold.forms import BaseDialogForm

from core.models_campana_meta import CampanaMeta, PlantillaMeta, TIPOS_PLANTILLA, TarjetaPlantillaMeta, variables_en
from core.plantilla_meta_editor import (
    SOLO_LECTURA,
    app_id_listo,
    guardar_asistente,
    lineas_disponibles,
    nombre_copia,
    sugerir_mapeo,
    valores_de_prueba,
    variables_para_formulario,
)
from core.plantilla_meta_reglas import bloqueo_envio, etiqueta_calidad

_ESTADO_LABEL = {
    'APPROVED': 'success',
    'PENDING': 'warning',
    'IN_APPEAL': 'warning',
    'REJECTED': 'danger',
    'ERROR': 'danger',
    'DISABLED': 'danger',
    'PAUSED': 'info',
    'NO_EXISTE': 'info',
    'BORRADOR': 'info',
}


class PlantillaVistaFilter(admin.SimpleListFilter):
    title = 'Vista'
    parameter_name = 'eki_pm'

    def lookups(self, request, model_admin):
        return (
            ('aprobadas', 'Aprobadas'),
            ('pendientes', 'Pendientes'),
            ('rechazadas', 'Rechazadas'),
            ('borradores', 'Borradores'),
            ('importadas', 'Importadas'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == 'aprobadas':
            return queryset.filter(estado='APPROVED')
        if valor == 'pendientes':
            return queryset.filter(estado__in=('PENDING', 'IN_APPEAL'))
        if valor == 'rechazadas':
            return queryset.filter(estado='REJECTED')
        if valor == 'borradores':
            return queryset.filter(estado='BORRADOR')
        if valor == 'importadas':
            return queryset.filter(origen='IMPORTADA')
        return queryset


class PlantillaLineaFilter(admin.SimpleListFilter):
    title = 'Línea'
    parameter_name = 'linea'

    def lookups(self, request, model_admin):
        from core.lineas.campana import fichas_admin

        return [(f['phone_id'], f['nombre']) for f in fichas_admin() if f['phone_id']]

    def queryset(self, request, queryset):
        phone = self.value()
        if not phone:
            return queryset
        from core.lineas.campana import waba_de_linea
        from core.lineas.variante import perfil_de
        from core.meta_waba import _waba

        waba = waba_de_linea(phone)
        if not perfil_de(phone).usa_waba_principal:
            if waba:
                return queryset.filter(waba_id=waba)
            principal = _waba()
            if principal:
                return queryset.exclude(waba_id__in=['', principal])
            return queryset.none()
        principal = _waba()
        if principal:
            return queryset.filter(waba_id__in=['', principal])
        return queryset


class PlantillaMetaAdminForm(forms.ModelForm):
    linea = forms.ChoiceField(
        required=False,
        label='Línea',
        help_text='La plantilla se crea en la cuenta Meta de esa línea. No cruza de WABA.',
    )

    class Meta:
        model = PlantillaMeta
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.lineas.campana import waba_de_linea

        opciones = lineas_disponibles()
        self.fields['linea'].choices = opciones
        obj = self.instance
        if obj and getattr(obj, 'waba_id', ''):
            for phone, _nombre in opciones:
                if waba_de_linea(phone) == obj.waba_id:
                    self.initial['linea'] = phone
                    break
        elif opciones and 'linea' not in self.initial:
            self.initial['linea'] = opciones[0][0]
        enviado = bool(obj and obj.pk and obj.estado not in ('BORRADOR', 'ERROR', ''))
        self.fields['linea'].required = bool(opciones) and not enviado
        if enviado:
            self.fields['linea'].disabled = True

    def clean_linea(self):
        from core.lineas.campana import waba_de_linea

        phone = (self.cleaned_data.get('linea') or '').strip()
        if not phone:
            return phone
        if not waba_de_linea(phone):
            raise forms.ValidationError(
                'Esa línea no tiene cuenta Meta (WABA) en el entorno. '
                'No se puede crear la plantilla ahí.'
            )
        return phone

    def save(self, commit=True):
        from core.lineas.campana import waba_de_linea

        obj = super().save(commit=False)
        if obj.estado in ('BORRADOR', 'ERROR', '') or not obj.pk:
            phone = (self.cleaned_data.get('linea') or '').strip()
            if phone:
                obj.waba_id = waba_de_linea(phone)
        if commit:
            obj.save()
            self.save_m2m()
        return obj


def tabs_plantilla_meta(request):
    """Pestañas del listado. Vacío fuera de Plantillas Meta."""
    try:
        ruta = reverse('admin:core_plantillameta_changelist')
    except Exception:
        return []
    if not (request.path or '').startswith(str(ruta)):
        return []
    base = PlantillaMeta.objects.all()
    conteos = {
        '': base.count(),
        'aprobadas': base.filter(estado='APPROVED').count(),
        'pendientes': base.filter(estado__in=('PENDING', 'IN_APPEAL')).count(),
        'rechazadas': base.filter(estado='REJECTED').count(),
        'borradores': base.filter(estado='BORRADOR').count(),
        'importadas': base.filter(origen='IMPORTADA').count(),
    }
    vista = request.GET.get('eki_pm') or ''
    if vista not in conteos:
        vista = ''

    def item(clave, titulo):
        enlace = str(ruta) if not clave else f'{ruta}?eki_pm={clave}'
        return {
            'title': f'{titulo} · {conteos[clave]}',
            'link': enlace,
            'active': vista == clave,
            'has_permission': True,
        }

    return [{
        'models': ['core.plantillameta'],
        'items': [
            item('', 'Todas'),
            item('aprobadas', 'Aprobadas'),
            item('pendientes', 'Pendientes'),
            item('rechazadas', 'Rechazadas'),
            item('borradores', 'Borradores'),
            item('importadas', 'Importadas'),
        ],
    }]


class EnviarPruebaPlantillaForm(BaseDialogForm):
    linea = forms.ChoiceField(label='Línea', choices=[])
    telefono = forms.CharField(label='Número destino', initial='573026480629', max_length=20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        opciones = lineas_disponibles()
        self.fields['linea'].choices = opciones or [('', 'Sin línea configurada')]
        plantilla = PlantillaMeta.objects.filter(pk=self.object_id).first()
        self.plantilla = plantilla
        if plantilla is None:
            return
        for numero in sorted(set(variables_en(plantilla.cuerpo))):
            self.fields[f'var_{numero}'] = forms.CharField(
                label=f'Variable {{{{{numero}}}}} del mensaje',
                required=True,
            )
        for numero in sorted(set(variables_en(plantilla.header_texto))):
            self.fields[f'var_h_{numero}'] = forms.CharField(
                label=f'Variable {{{{{numero}}}}} del encabezado',
                required=True,
            )
        botones = variables_en(plantilla.boton_1_url) + variables_en(plantilla.boton_2_url)
        for numero in sorted(set(botones)):
            self.fields[f'var_b_{numero}'] = forms.CharField(
                label=f'Variable {{{{{numero}}}}} del botón',
                required=True,
            )

    def clean(self):
        limpio = super().clean()
        motivo = bloqueo_envio(self.plantilla)
        if motivo:
            self.add_error('telefono', motivo)
        if not limpio.get('linea'):
            self.add_error('linea', 'No hay una línea de Meta configurada.')
        return limpio


class CampanasDePlantillaInline(admin.TabularInline):
    model = CampanaMeta
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('nombre', 'estado_en_linea', 'embudo_en_linea')
    readonly_fields = ('nombre', 'estado_en_linea', 'embudo_en_linea')
    tab = True
    verbose_name = 'Campaña'
    verbose_name_plural = 'Campañas'

    def has_add_permission(self, request, obj=None):
        return False

    def estado_en_linea(self, obj):
        from core.campana_audiencia import estado_campana

        if not obj or not obj.pk:
            return '—'
        return estado_campana(obj)[1]
    estado_en_linea.short_description = 'Estado'

    def embudo_en_linea(self, obj):
        from core.campana_audiencia import embudo, texto_embudo

        if not obj or not obj.pk:
            return '—'
        datos = embudo(obj)
        return f'{texto_embudo(datos)} · Fallidos {datos["fallidos"]}'
    embudo_en_linea.short_description = 'Resultado'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('plantilla')


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


def _texto_resumen(resumen: dict) -> str:
    return (
        f"Nuevas: {resumen.get('nuevas', 0)}. "
        f"Actualizadas: {resumen.get('actualizadas', 0)}. "
        f"Sin cambios: {resumen.get('sin_cambios', 0)}. "
        f"Con error: {resumen.get('con_error', 0)}. "
        f"No existen en Meta: {resumen.get('ausentes', 0)}."
    )


@admin.register(PlantillaMeta)
class PlantillaMetaAdmin(admin.ModelAdmin):
    form = PlantillaMetaAdminForm
    list_display = (
        'col_nombre',
        'col_linea',
        'col_tipo',
        'col_categoria',
        'idioma',
        'col_estado',
        'col_calidad',
        'col_usos',
        'col_actualizada',
    )
    list_display_links = ('col_nombre',)
    list_filter = (PlantillaVistaFilter, PlantillaLineaFilter, 'estado', 'tipo', 'categoria', 'idioma')
    search_fields = ('nombre_interno', 'meta_name')
    list_per_page = 50
    actions = ['sincronizar_seleccionadas']
    actions_list = ('nueva_plantilla', 'traer_de_meta')
    actions_list_hide_default = True
    actions_row = (
        'enviar_a_aprobacion',
        'sincronizar_estado',
        'enviar_prueba',
        'usar_en_campana',
        'duplicar',
    )
    readonly_fields = (
        'meta_template_id',
        'waba_id',
        'rejected_reason',
        'ultimo_error_code',
        'ultimo_error_mensaje',
        'enviada_en',
        'sincronizada_en',
    )
    conditional_fields = {
        'header_texto': "tipo == 'IMAGEN'",
        'header_ejemplo': "tipo == 'IMAGEN'",
        'footer': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_1_tipo': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_1_texto': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_1_url': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_1_ejemplo': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_2_tipo': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_2_texto': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_2_url': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
        'boton_2_ejemplo': "tipo == 'TEXTO' || tipo == 'IMAGEN'",
    }
    fieldsets = (
        ('Mensaje', {
            'fields': ('nombre_interno', 'linea', 'tipo', 'cuerpo', 'estado'),
            'description': (
                '1. Nombre, línea y tipo. 2. Escribe el mensaje. '
                '3. En el listado, la acción «Enviar plantilla a Meta para aprobación». '
                'Cuando Meta la acepte, el estado queda en Aprobada. '
                'La plantilla nace en la cuenta de esa línea y no cruza.'
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

    class Media:
        css = {'all': ('admin/css/plantilla_meta_editor.css',)}
        js = ('admin/js/plantilla_meta_editor.js',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            n_campanas=Count('campanas', distinct=True),
            n_envios=Count('campanas__envios', distinct=True),
        )

    def get_inlines(self, request, obj=None):
        inlines = []
        if obj is not None and obj.tipo == 'CARRUSEL':
            inlines.append(TarjetaPlantillaMetaInline)
        if obj is not None and obj.pk:
            inlines.append(CampanasDePlantillaInline)
        return inlines

    def get_urls(self):
        custom = [
            path('nueva/', self.admin_site.admin_view(self._redir_alta), name='core_plantillameta_tipo'),
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

    def _redir_alta(self, request, tipo=None):
        destino = reverse('admin:core_plantillameta_add')
        tipo_q = (tipo or request.GET.get('tipo') or '').upper()
        if tipo_q in {codigo for codigo, _nombre in TIPOS_PLANTILLA}:
            destino = f'{destino}?tipo={tipo_q}'
        return redirect(destino)

    def add_view(self, request, form_url='', extra_context=None):
        return self.escribir_view(request, tipo=(request.GET.get('tipo') or 'TEXTO'))

    def change_view(self, request, object_id, form_url='', extra_context=None):
        return self.escribir_view(request, pk=object_id)

    def escribir_view(self, request, tipo='TEXTO', pk=None):
        plantilla = None
        if pk is not None:
            plantilla = self.get_object(request, str(pk))
        return self._editor(request, plantilla, tipo=tipo)

    def _editor(self, request, plantilla, tipo=None):
        from django.core.exceptions import PermissionDenied

        if plantilla is None:
            if not self.has_add_permission(request):
                raise PermissionDenied
        elif not self.has_change_permission(request, plantilla):
            raise PermissionDenied
        errores = []
        if request.method == 'POST' and plantilla is not None and request.POST.get('accion') == 'duplicar':
            return self.duplicar(request, plantilla.pk)
        if request.method == 'POST' and plantilla is not None and request.POST.get('accion') == 'probar':
            datos_prueba = request.POST.copy()
            datos_prueba['_form_submitted'] = 'on'
            if not datos_prueba.get('linea'):
                lineas = lineas_disponibles()
                datos_prueba['linea'] = lineas[0][0] if lineas else ''
            for fila in variables_para_formulario(plantilla):
                for prefijo in ('var_', 'var_h_', 'var_b_'):
                    clave = f"{prefijo}{fila['n']}"
                    if not (datos_prueba.get(clave) or '').strip():
                        datos_prueba[clave] = fila['ejemplo'] or 'ejemplo'
            formulario = EnviarPruebaPlantillaForm(request, plantilla.pk, datos_prueba)
            if formulario.is_valid():
                return self.enviar_prueba(request, formulario, plantilla.pk)
            errores = []
            for lista in formulario.errors.values():
                errores.extend(list(lista))
        if request.method == 'POST' and plantilla is not None and plantilla.estado in SOLO_LECTURA:
            if request.POST.get('accion') == 'probar':
                from core.meta_waba import enviar_prueba_de_plantilla

                resultado = enviar_prueba_de_plantilla(
                    plantilla,
                    request.POST.get('telefono') or '573026480629',
                )
                nivel = messages.SUCCESS if resultado.get('success') else messages.ERROR
                texto = resultado.get('message') or 'No se envió.'
                if resultado.get('wamid'):
                    texto = f'{texto} Id del mensaje: {resultado.get("wamid")}.'
                self.message_user(request, texto, level=nivel)
            return redirect('admin:core_plantillameta_escribir_una', pk=plantilla.pk)
        if request.method == 'POST' and (plantilla is None or plantilla.estado not in SOLO_LECTURA):
            enviar = request.POST.get('accion') == 'enviar'
            datos = request.POST.copy()
            if 'boton_1_texto' not in datos and 'boton_texto' in datos:
                datos['boton_1_texto'] = datos.get('boton_texto') or ''
                datos['boton_1_tipo'] = 'QUICK_REPLY' if (datos.get('boton_texto') or '').strip() else ''
            if 'footer' not in datos and plantilla is not None:
                datos['footer'] = plantilla.footer or ''
            guardada, errores = guardar_asistente(datos, plantilla, enviar=enviar)
            if guardada is not None and guardada.pk and not errores:
                texto = 'Plantilla guardada.'
                if enviar:
                    texto = f'Enviada. Estado {guardada.get_estado_display()}.'
                self.message_user(request, texto, level=messages.SUCCESS)
                return redirect('admin:core_plantillameta_change', guardada.pk)
            if guardada is not None and guardada.pk and errores and any('registro' in e for e in errores):
                self.message_user(request, errores[0], level=messages.WARNING)
                return redirect('admin:core_plantillameta_change', guardada.pk)
            if guardada is not None:
                plantilla = guardada
        posted = request.POST if request.method == 'POST' and errores else None
        from django.templatetags.static import static

        from core.plantilla_builder import armar_inicial

        tipo_inicial = (request.POST.get('tipo') if request.method == 'POST' else None) or self._tipo_inicial(request, plantilla)
        inicial = armar_inicial(
            plantilla,
            tipo_inicial,
            posted,
            foto_muestra=static('certificados/eki-wordmark.png'),
        )
        titulo = 'Nueva plantilla' if plantilla is None or not plantilla.pk else (plantilla.nombre_interno or 'Plantilla')
        campanas_ui = self._campanas_de(plantilla)
        contexto = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'original': plantilla,
            'title': titulo,
            'titulo': titulo,
            'estado_label': plantilla.get_estado_display() if plantilla is not None and plantilla.pk else 'Borrador',
            'plantilla': plantilla,
            'errores': errores,
            'inicial': inicial,
            'app_id_listo': app_id_listo(),
            'solo_lectura': inicial['soloLectura'],
            'variables': variables_para_formulario(plantilla),
            'tarjetas': self._tarjetas(plantilla),
            'tipo_inicial': tipo_inicial,
            'vista_otro': self._vista_otro(plantilla),
            'campanas_ui': campanas_ui,
            'usos_campana': len(campanas_ui),
            'posted': request.POST if request.method == 'POST' else {},
            'media': self.media,
        }
        return render(request, 'admin/plantilla_meta/editor.html', contexto)

    def _campanas_de(self, plantilla):
        if plantilla is None or not plantilla.pk:
            return []
        from core.campana_audiencia import embudo, estado_campana, texto_embudo

        filas = []
        for campana in plantilla.campanas.select_related('plantilla').order_by('-id'):
            _clave, etiqueta = estado_campana(campana)
            datos = embudo(campana)
            filas.append({
                'nombre': campana.nombre,
                'estado': etiqueta,
                'embudo': f'{texto_embudo(datos)} · Fallidos {datos["fallidos"]}',
                'url': reverse('admin:core_campanameta_change', args=[campana.pk]),
            })
        return filas

    def _tipo_inicial(self, request, plantilla):
        codigos = {codigo for codigo, _nombre in TIPOS_PLANTILLA}
        if plantilla is not None and plantilla.pk:
            return plantilla.tipo if plantilla.tipo in codigos else 'TEXTO'
        tipo = (request.GET.get('tipo') or 'TEXTO').upper()
        if tipo not in codigos or tipo == 'OTRO':
            tipo = 'TEXTO'
        return tipo

    def _tarjetas(self, plantilla):
        if plantilla is None or not plantilla.pk or plantilla.tipo != 'CARRUSEL':
            return [
                {'titulo': '', 'cuerpo': '', 'imagen_url': '', 'boton_ver_texto': 'Ver curso', 'boton_info_texto': 'Más información'},
                {'titulo': '', 'cuerpo': '', 'imagen_url': '', 'boton_ver_texto': 'Ver curso', 'boton_info_texto': 'Más información'},
            ]
        filas = [
            {
                'titulo': t.titulo,
                'cuerpo': t.cuerpo,
                'imagen_url': t.imagen_url,
                'boton_ver_texto': t.boton_ver_texto,
                'boton_info_texto': t.boton_info_texto,
            }
            for t in plantilla.tarjetas.all()
        ]
        return filas or self._tarjetas(None)

    def _vista_otro(self, plantilla):
        if plantilla is None or plantilla.tipo != 'OTRO':
            return []
        crudo = plantilla.components_raw
        if isinstance(crudo, dict):
            crudo = [crudo]
        if not isinstance(crudo, list):
            return ['Sin dato']
        filas = []
        for comp in crudo:
            if not isinstance(comp, dict):
                filas.append('Sin dato')
                continue
            tipo = str(comp.get('type') or 'Sin dato')
            texto = str(comp.get('text') or '').strip()
            filas.append(f'{tipo}: {texto}' if texto else tipo)
        return filas or ['Sin dato']

    @display(description='Nombre', ordering='nombre_interno')
    def col_nombre(self, obj):
        tecnico = obj.meta_name or 'Sin dato'
        return format_html(
            '<span class="block">{}</span><code class="pm-tecnico">{}</code>',
            obj.nombre_interno,
            tecnico,
        )

    @display(description='Línea', ordering='waba_id')
    def col_linea(self, obj):
        from core.lineas.campana import fichas_admin

        waba = (obj.waba_id or '').strip()
        for ficha in fichas_admin():
            if waba and ficha['waba'] == waba:
                return ficha['nombre']
            if not waba and not ficha['lineal']:
                return ficha['nombre']
        return waba or '—'

    @display(description='Tipo', ordering='tipo')
    def col_tipo(self, obj):
        return obj.get_tipo_display()

    @display(description='Categoría', ordering='categoria')
    def col_categoria(self, obj):
        return obj.get_categoria_display() or 'Sin dato'

    @display(
        description='Estado',
        ordering='estado',
        label=_ESTADO_LABEL,
    )
    def col_estado(self, obj):
        return obj.estado, obj.get_estado_display()

    @display(description='Calidad', ordering='calidad')
    def col_calidad(self, obj):
        return etiqueta_calidad(obj.calidad)

    @display(description='Usos')
    def col_usos(self, obj):
        campanas = getattr(obj, 'n_campanas', None)
        envios = getattr(obj, 'n_envios', None)
        if campanas is None:
            campanas = obj.campanas.count()
        if envios is None:
            envios = obj.campanas.aggregate(n=Count('envios'))['n'] or 0
        return f'{campanas} campañas · {envios} envíos'

    @display(description='Actualizada', ordering='actualizada_en')
    def col_actualizada(self, obj):
        momento = obj.actualizada_en or obj.sincronizada_en or obj.fecha_creacion
        if not momento:
            return 'Sin dato'
        return momento.strftime('%Y-%m-%d %H:%M')

    @action(description='Nueva plantilla', url_path='abrir-nueva', icon='add', permissions=['add'])
    def nueva_plantilla(self, request):
        return redirect('admin:core_plantillameta_add')

    @action(description='Traer de Meta', url_path='traer-de-meta', icon='download', permissions=['change'])
    def traer_de_meta(self, request):
        from core.meta_waba import sincronizar_catalogo_meta

        resultado = sincronizar_catalogo_meta()
        if not resultado.get('ok'):
            self.message_user(request, resultado.get('message') or 'No se pudo leer Meta.', level=messages.ERROR)
        else:
            self.message_user(request, _texto_resumen(resultado.get('resumen') or {}), level=messages.SUCCESS)
        return redirect('admin:core_plantillameta_changelist')

    @action(description='Enviar a aprobación', url_path='enviar-aprobacion', icon='publish', permissions=['change'])
    def enviar_a_aprobacion(self, request, object_id):
        plantilla = self.get_object(request, object_id)
        lista = redirect('admin:core_plantillameta_changelist')
        if plantilla is None:
            self.message_user(request, 'No se encontró la plantilla.', level=messages.ERROR)
            return lista
        if plantilla.estado != 'BORRADOR':
            self.message_user(
                request,
                f'{plantilla.nombre_interno} está en {plantilla.get_estado_display()}. '
                'Solo un borrador se envía a aprobación desde aquí.',
                level=messages.WARNING,
            )
            return lista
        from core.meta_waba import crear_plantilla_en_meta

        resultado = crear_plantilla_en_meta(plantilla)
        nivel = messages.SUCCESS if resultado.get('success') else messages.ERROR
        self.message_user(request, resultado.get('message') or 'Listo.', level=nivel)
        return lista

    @action(description='Sincronizar estado', url_path='sincronizar', icon='sync', permissions=['change'])
    def sincronizar_estado(self, request, object_id):
        from core.meta_waba import sincronizar_plantilla

        plantilla = self.get_object(request, object_id)
        lista = redirect('admin:core_plantillameta_changelist')
        if plantilla is None:
            return lista
        resultado = sincronizar_plantilla(plantilla)
        nivel = messages.SUCCESS if resultado.get('success') else messages.WARNING
        self.message_user(
            request,
            resultado.get('message') or f'{plantilla.nombre_interno}: {plantilla.estado}.',
            level=nivel,
        )
        return lista

    @action(
        description='Enviar prueba',
        url_path='enviar-prueba',
        icon='send',
        permissions=['change'],
        dialog={
            'title': 'Enviar prueba',
            'description': 'Sale por la línea que elija. El número de prueba es 573026480629.',
            'form_class': EnviarPruebaPlantillaForm,
            'form_submit_text': 'Enviar prueba',
        },
    )
    def enviar_prueba(self, request, form, object_id):
        from core.meta_waba import enviar_prueba_meta

        plantilla = self.get_object(request, object_id)
        lista = redirect('admin:core_plantillameta_changelist')
        motivo = bloqueo_envio(plantilla)
        if motivo:
            self.message_user(request, motivo, level=messages.ERROR)
            return lista
        campana = CampanaMeta(
            nombre=f'Prueba {plantilla.nombre_interno}'[:120],
            plantilla=plantilla,
            phone_number_id=form.cleaned_data.get('linea') or '',
            **valores_de_prueba(plantilla, form.cleaned_data),
        )
        resultado = enviar_prueba_meta(campana, form.cleaned_data.get('telefono') or '')
        if resultado.get('success'):
            wamid = resultado.get('wamid') or 'Sin dato'
            self.message_user(
                request,
                f'{resultado.get("message")} Id del mensaje: {wamid}.',
                level=messages.SUCCESS,
            )
        else:
            self.message_user(request, resultado.get('message') or 'No se envió.', level=messages.ERROR)
        return lista

    @action(description='Usar en campaña', url_path='usar-campana', icon='campaign', permissions=['change'])
    def usar_en_campana(self, request, object_id):
        plantilla = self.get_object(request, object_id)
        lista = redirect('admin:core_plantillameta_changelist')
        motivo = bloqueo_envio(plantilla)
        if motivo:
            self.message_user(request, motivo, level=messages.ERROR)
            return lista
        mapeo = sugerir_mapeo(plantilla)
        lineas = lineas_disponibles()
        campana = CampanaMeta.objects.create(
            nombre=plantilla.nombre_interno[:120],
            plantilla=plantilla,
            phone_number_id=lineas[0][0] if lineas else '',
            mapeo_body=mapeo['mapeo_body'],
            mapeo_header=mapeo['mapeo_header'],
            mapeo_boton=mapeo['mapeo_boton'],
        )
        if mapeo['aviso']:
            self.message_user(request, mapeo['aviso'], level=messages.WARNING)
        self.message_user(request, 'Campaña en borrador. Revise destinatarios y variables.', level=messages.SUCCESS)
        return redirect('admin:core_campanameta_change', campana.pk)

    def _duplicar_plantilla(self, request, plantilla):
        copia = PlantillaMeta.objects.get(pk=plantilla.pk)
        copia.pk = None
        copia.nombre_interno = f'{plantilla.nombre_interno} (copia)'[:120]
        copia.meta_name = nombre_copia(plantilla.meta_name or plantilla.nombre_interno, plantilla.idioma)
        copia.estado = 'BORRADOR'
        copia.origen = 'LOCAL'
        copia.meta_template_id = ''
        copia.rejected_reason = ''
        copia.ultimo_error_code = ''
        copia.ultimo_error_mensaje = ''
        copia.enviada_en = None
        copia.save()
        for tarjeta in plantilla.tarjetas.all():
            tarjeta.pk = None
            tarjeta.plantilla = copia
            tarjeta.save()
        self.message_user(
            request,
            f'Copia creada. El nombre técnico quedó en {copia.meta_name}.',
            level=messages.SUCCESS,
        )
        return redirect('admin:core_plantillameta_escribir_una', pk=copia.pk)

    @action(description='Duplicar', url_path='duplicar', icon='content_copy', permissions=['add'])
    def duplicar(self, request, object_id):
        plantilla = self.get_object(request, object_id)
        if plantilla is None:
            return redirect('admin:core_plantillameta_changelist')
        return self._duplicar_plantilla(request, plantilla)

    @admin.action(description='Sincronizar estado')
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
