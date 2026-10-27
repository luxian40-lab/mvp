from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from unfold.admin import ModelAdmin
from unfold.decorators import action, display
from unfold.forms import BaseDialogForm

from core.aviso_modulo import aviso_habilitado, enviar_prueba, motivo_plantilla, vista_previa
from core.campana_audiencia import numero_de_prueba_permitido, numeros_de_prueba
from core.models import AvisoModuloDisponible, AvisoModuloEnviado
from core.models_campana_meta import PlantillaMeta
from core.plantilla_meta_editor import lineas_disponibles


class AvisoModuloForm(forms.ModelForm):
    class Meta:
        model = AvisoModuloDisponible
        fields = ('cliente', 'curso', 'grupo', 'phone_number_id', 'plantilla', 'activo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lineas = lineas_disponibles()
        self.fields['phone_number_id'] = forms.ChoiceField(
            label='Línea',
            choices=lineas or [('', 'Sin línea configurada')],
            help_text='La plantilla debe estar aprobada en la cuenta de esa línea.',
        )
        if not self.instance.pk and lineas:
            self.fields['phone_number_id'].initial = lineas[0][0]
        plantillas = PlantillaMeta.objects.filter(activa=True, estado='APPROVED')
        if self.instance.pk and self.instance.plantilla_id:
            plantillas = PlantillaMeta.objects.filter(pk=self.instance.plantilla_id) | plantillas
        self.fields['plantilla'].queryset = plantillas.order_by('nombre_interno')
        self.fields['plantilla'].label_from_instance = lambda obj: obj.nombre_interno

    def clean(self):
        limpio = super().clean()
        cliente = limpio.get('cliente')
        grupo = limpio.get('grupo')
        if grupo is not None and cliente is not None and grupo.cliente_id and grupo.cliente_id != cliente.pk:
            self.add_error('grupo', 'El grupo es de otro cliente.')
        plantilla = limpio.get('plantilla')
        if plantilla is not None:
            motivo = motivo_plantilla(plantilla, (limpio.get('phone_number_id') or '').strip())
            if motivo:
                self.add_error('plantilla', motivo)
        return limpio


class PruebaAvisoForm(BaseDialogForm):
    telefono = forms.ChoiceField(label='Número interno')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['telefono'].choices = [(n, f'+{n}') for n in numeros_de_prueba()]


@admin.register(AvisoModuloDisponible)
class AvisoModuloDisponibleAdmin(ModelAdmin):
    form = AvisoModuloForm
    list_display = ('cliente', 'curso', 'col_linea', 'col_plantilla', 'activo', 'col_enviados')
    list_filter = ('activo', 'cliente')
    list_select_related = ('cliente', 'curso', 'plantilla')
    readonly_fields = ('col_estado', 'col_calendario')
    actions_detail = ('enviar_prueba_aviso',)
    fieldsets = (
        ('Estado', {'fields': ('col_estado',)}),
        ('A quién', {'fields': ('cliente', 'curso', 'grupo')}),
        ('Envío', {'fields': ('phone_number_id', 'plantilla', 'activo')}),
        ('Calendario del cliente', {'fields': ('col_calendario',)}),
    )

    @display(description='Línea')
    def col_linea(self, obj):
        return dict(lineas_disponibles()).get(obj.phone_number_id, obj.phone_number_id)

    @display(description='Plantilla')
    def col_plantilla(self, obj):
        return obj.plantilla.nombre_interno if obj.plantilla_id else '—'

    @display(description='Enviados')
    def col_enviados(self, obj):
        return obj.envios.filter(estado='ENVIADO').count()

    @display(description='Funcionamiento')
    def col_estado(self, obj):
        if aviso_habilitado():
            return 'Encendido. Revisa el calendario cada 15 minutos.'
        return 'Apagado en el servidor. Guardar la configuración no envía nada todavía.'

    @display(description='Módulos y personas esperando')
    def col_calendario(self, obj):
        if not obj.pk:
            return 'Guarde para ver el calendario.'
        filas = vista_previa(obj)
        if not filas:
            return 'Este cliente no tiene fechas para este curso. Se cargan en el cliente, sección Calendario de módulos.'
        enviados = dict(
            AvisoModuloEnviado.objects.filter(aviso=obj, estado='ENVIADO')
            .order_by()
            .values_list('modulo_id')
            .annotate(n=Count('id'))
        )
        ahora = timezone.now()
        filas_html = format_html_join(
            '',
            '<tr><td>M{} · {}</td><td>{}</td><td>{}</td><td>{}</td></tr>',
            (
                (
                    f['modulo'].numero,
                    f['modulo'].titulo,
                    timezone.localtime(f['habilitado_desde']).strftime('%d/%m/%Y %H:%M'),
                    'Abierto' if f['habilitado_desde'] <= ahora else 'Pendiente',
                    f"{f['personas']} esperan · {enviados.get(f['modulo'].pk, 0)} avisados",
                )
                for f in filas
            ),
        )
        return format_html(
            '<table><thead><tr><th>Módulo</th><th>Abre (Bogotá)</th><th>Estado</th><th>Personas</th></tr>'
            '</thead><tbody>{}</tbody></table>',
            filas_html,
        )

    @action(
        description='Enviar prueba',
        url_path='enviar-prueba',
        icon='send',
        permissions=['change'],
        dialog={
            'title': 'Enviar prueba',
            'description': 'Sale solo al número interno. No cuenta como aviso enviado.',
            'form_class': PruebaAvisoForm,
            'form_submit_text': 'Enviar',
        },
    )
    def enviar_prueba_aviso(self, request, form, object_id):
        aviso = get_object_or_404(AvisoModuloDisponible.objects.select_related('curso', 'plantilla'), pk=object_id)
        destino = redirect('admin:core_avisomodulodisponible_change', aviso.pk)
        telefono = form.cleaned_data['telefono']
        if not numero_de_prueba_permitido(telefono):
            self.message_user(request, 'La prueba solo sale a los números autorizados.', level=messages.ERROR)
            return destino
        motivo = motivo_plantilla(aviso.plantilla, aviso.phone_number_id)
        if motivo:
            self.message_user(request, motivo, level=messages.ERROR)
            return destino
        resultado = enviar_prueba(aviso, telefono)
        if resultado.get('success'):
            self.message_user(request, 'Prueba enviada.', level=messages.SUCCESS)
        else:
            self.message_user(request, 'Meta no aceptó la prueba. Revise la plantilla y la línea.', level=messages.ERROR)
        return destino


@admin.register(AvisoModuloEnviado)
class AvisoModuloEnviadoAdmin(ModelAdmin):
    list_display = ('fecha', 'aviso', 'col_modulo', 'estado')
    list_filter = ('estado', 'aviso__cliente')
    list_select_related = ('aviso__cliente', 'aviso__curso', 'modulo')
    readonly_fields = ('aviso', 'estudiante', 'modulo', 'estado', 'wamid', 'respuesta', 'fecha')
    raw_id_fields = ('estudiante',)

    @display(description='Módulo')
    def col_modulo(self, obj):
        return f'M{obj.modulo.numero} · {obj.modulo.titulo}'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
