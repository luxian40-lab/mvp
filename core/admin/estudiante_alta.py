"""Alta y edición de Estudiante en tres bloques. El flag apagado no usa esto."""
from __future__ import annotations

from django import forms
from django.contrib.admin.widgets import AutocompleteSelect
from django.urls import reverse
from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import mark_safe

from core.admin.estudiantes import EstudianteAdminForm
from core.admin.estudiantes_crm import iniciales
from core.cursos_permitidos import (
    curso_esta_permitido,
    cursos_agrupados,
    cursos_permitidos,
    inscripcion_fuera_de_regla,
    texto_cursos,
)
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.models_extras import GrupoEstudiantes
from core.planes_linea import PLAN_CHOICES, plan_por_clave
from core.utils_telefono import normalizar_telefono

# Campos del modelo que el formulario de hoy no muestra. Siguen con su default.
CAMPOS_EXCLUIDOS = {
    'id': 'Clave interna.',
    'region': 'No está en el formulario actual.',
    'territory_id': 'No está en el formulario actual.',
    'impacto_respuestas': 'No está en el formulario actual.',
    'foto_perfil': 'No está en el formulario actual.',
    'fecha_registro': 'Se llena sola al crear.',
    'acepto_terminos': 'No está en el formulario actual. El alta sigue en habeas.',
    'fecha_aceptacion_terminos': 'No está en el formulario actual.',
    'wa_optin_fecha': 'No está en el formulario actual.',
    'wa_optin_version': 'No está en el formulario actual.',
    'wa_optin_origen': 'No está en el formulario actual.',
    'wa_optout_fecha': 'No está en el formulario actual.',
    'estado_chat': 'No está en el formulario actual. El alta queda en habeas.',
    'estado_onboarding': 'No está en el formulario actual.',
    'preguntas_ia_restantes': 'No está en el formulario actual.',
    'contexto_temporal': 'No está en el formulario actual.',
}

FIELDSETS_V2 = (
    ('1. Organización', {
        'fields': ('cliente', 'grupo'),
        'description': (
            'Primero la organización y el grupo. '
            'Si elige un plan en los datos de la persona, ese manda.'
        ),
    }),
    ('2. Datos de la persona', {
        'fields': (('tipo_documento', 'cedula'), 'nombre', 'telefono', 'plan_persona', 'activo'),
        'description': (
            'Documento único y teléfono de WhatsApp. '
            'El plan vacío usa el del grupo y, si el grupo no tiene, el de la organización.'
        ),
    }),
    ('3. Curso', {
        'fields': ('cursos_a_inscribir',),
        'description': 'Opcional. Puede elegir varios. Sin curso por ahora también vale.',
    }),
    ('Ubicación y perfil', {
        'classes': ('collapse',),
        'fields': (
            'municipio', 'departamento', 'ubicacion_detalle',
            'genero', 'edad', 'rango_edad',
            'rural_disperso', 'pdet', 'consentimiento_impacto',
            'consentimiento_impacto_en', 'consentimiento_impacto_acudiente',
            'area_unidad_ha',
        ),
    }),
    ('Así quedará', {
        'classes': ('eki-alta-panel',),
        'fields': ('enviar_bienvenida',),
    }),
)

FIELDSETS_V2_EDICION = (
    FIELDSETS_V2[0],
    FIELDSETS_V2[1],
    ('3. Curso', {
        'fields': ('cursos_a_inscribir', 'mostrar_cursos_inscritos'),
        'description': 'Opcional. Los cursos ya inscritos no se borran al guardar.',
    }),
    FIELDSETS_V2[3],
    FIELDSETS_V2[4],
)

MENSAJE_CURSO = 'Ese curso no pertenece a la organización ni es general de eki.'
MENSAJE_GRUPO = 'Elija el grupo. El plan OP1, OP2 u OP3 sale de ese grupo.'


def campos_del_alta(edicion: bool) -> set[str]:
    fieldsets = FIELDSETS_V2_EDICION if edicion else FIELDSETS_V2
    nombres = set()
    for _titulo, opciones in fieldsets:
        for campo in opciones['fields']:
            if isinstance(campo, (tuple, list)):
                nombres.update(campo)
            else:
                nombres.add(campo)
    return nombres


class ClienteAltaAutocomplete(AutocompleteSelect):
    """El autocompletado de Django deja el placeholder vacío. Aquí va en español."""

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs['data-placeholder'] = 'Sin organización (B2C)'
        return attrs

    def optgroups(self, name, value, attr=None):
        grupos = super().optgroups(name, value, attr)
        for _nombre, opciones, _indice in grupos:
            for opcion in opciones:
                if opcion.get('value') in ('', None):
                    opcion['label'] = 'Sin organización (B2C)'
        return grupos


class CursoCardsWidget(forms.CheckboxSelectMultiple):
    def __init__(self, *args, **kwargs):
        self.cursos_html = ''
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        return mark_safe(self.cursos_html or '')


class EstudianteAdminFormV2(EstudianteAdminForm):
    class Media:
        css = {'all': ('admin/css/estudiante_alta.css',)}
        js = ('admin/js/estudiante_alta.js',)
    grupo = forms.ModelChoiceField(
        queryset=GrupoEstudiantes.objects.none(),
        required=False,
        label='Grupo y plan',
        help_text='Se suma a ese grupo. Si ya estaba en otro con plan, manda el más nuevo que tenga plan.',
        empty_label='Seleccione un grupo',
    )
    enviar_bienvenida = forms.BooleanField(
        required=False,
        initial=False,
        label='Enviar bienvenida por WhatsApp',
        help_text='Apagado por defecto. Si el envío falla, la persona se guarda igual.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['activo'].help_text = 'Por defecto queda activo.'
        self.fields['cursos_a_inscribir'].label = 'Cursos'
        self.fields['cursos_a_inscribir'].widget = CursoCardsWidget()
        self.fields['cursos_a_inscribir'].error_messages['invalid_choice'] = MENSAJE_CURSO
        cliente = self._organizacion()
        self._armar_grupo(cliente)
        self._armar_cursos(cliente)
        self._espanol()
        self.fuera_de_regla = self._fuera()

    def _organizacion(self):
        bruto = None
        if self.data:
            bruto = self.data.get('cliente') or None
        elif self.initial.get('cliente'):
            bruto = self.initial.get('cliente')
        elif self.instance and self.instance.pk and self.instance.cliente_id:
            return self.instance.cliente
        if not bruto:
            return None
        try:
            return Cliente.objects.filter(pk=int(bruto)).first()
        except (TypeError, ValueError):
            return None

    def _armar_grupo(self, cliente):
        campo = self.fields['grupo']
        if cliente is None:
            campo.queryset = GrupoEstudiantes.objects.none()
            campo.required = False
            return
        qs = GrupoEstudiantes.objects.filter(cliente=cliente, activo=True).order_by('nombre')
        campo.queryset = qs
        campo.required = qs.exists() and not self.is_bound
        if self.is_bound:
            campo.required = qs.exists()
        campo.label_from_instance = _etiqueta_grupo
        if not self.is_bound and self.instance and self.instance.pk:
            actual = (
                self.instance.grupos.filter(activo=True, cliente=cliente)
                .order_by('-fecha_creacion', '-id')
                .first()
            )
            if actual is not None:
                campo.initial = actual.pk
        elif not self.is_bound and qs.count() == 1:
            campo.initial = qs.first().pk
        campo.error_messages['required'] = MENSAJE_GRUPO

    def _armar_cursos(self, cliente):
        permitidos = cursos_permitidos(cliente)
        ya = []
        if self.instance and self.instance.pk:
            ya = list(
                ProgresoEstudiante.objects.filter(estudiante=self.instance)
                .values_list('curso_id', flat=True)
            )
            # No se puede unir el queryset anotado con otro: Django lo rechaza.
            self.fields['cursos_a_inscribir'].queryset = Curso.objects.filter(
                pk__in=list(permitidos.values_list('pk', flat=True)) + ya,
            )
        else:
            self.fields['cursos_a_inscribir'].queryset = permitidos
        self.fields['cursos_a_inscribir'].help_text = texto_cursos(cliente, permitidos)
        self.fields['cursos_a_inscribir'].widget.cursos_html = html_cursos(
            cliente, ya_ids=ya,
        )

    def _espanol(self):
        cliente = self.fields['cliente']
        cliente.empty_label = 'Sin organización (B2C)'
        cliente.widget.attrs['data-placeholder'] = 'Escriba para buscar'
        for nombre in ('genero', 'rango_edad', 'tipo_documento'):
            campo = self.fields.get(nombre)
            if campo is None or not hasattr(campo, 'choices'):
                continue
            nuevas = []
            for clave, etiqueta in list(campo.choices):
                if str(etiqueta) in ('Select value', '---------'):
                    etiqueta = 'Seleccione'
                nuevas.append((clave, etiqueta))
            campo.choices = nuevas

    def _fuera(self):
        if not self.instance or not self.instance.pk:
            return []
        filas = []
        progresos = (
            ProgresoEstudiante.objects.filter(estudiante=self.instance)
            .select_related('curso', 'curso__cliente', 'estudiante', 'estudiante__cliente')
        )
        for progreso in progresos:
            if inscripcion_fuera_de_regla(progreso):
                filas.append(progreso)
        return filas

    def clean(self):
        cleaned = super().clean()
        cliente = cleaned.get('cliente')
        grupo = cleaned.get('grupo')
        if grupo is not None and (cliente is None or grupo.cliente_id != cliente.pk):
            self.add_error('grupo', 'Ese grupo no es de la organización.')
        cursos = cleaned.get('cursos_a_inscribir')
        if cursos:
            for curso in cursos:
                ya = False
                if self.instance and self.instance.pk:
                    ya = ProgresoEstudiante.objects.filter(
                        estudiante=self.instance, curso=curso,
                    ).exists()
                if ya:
                    continue
                if not curso_esta_permitido(curso, cliente):
                    self.add_error('cursos_a_inscribir', MENSAJE_CURSO)
                    break
        return cleaned


def _etiqueta_grupo(grupo) -> str:
    plan = _texto_plan(grupo, grupo.cliente)
    return f'{grupo.nombre} — {plan}'


def _texto_plan(grupo, organizacion) -> str:
    etiquetas = dict(PLAN_CHOICES)
    if grupo is not None and (grupo.plan_linea_meta or '').strip():
        plan = plan_por_clave(grupo.plan_linea_meta)
        return etiquetas.get(plan.clave, 'Sin plan')
    if organizacion is not None and (organizacion.plan_linea_meta or '').strip():
        plan = plan_por_clave(organizacion.plan_linea_meta)
        return etiquetas.get(plan.clave, 'Sin plan')
    return 'Sin plan'


def plan_incluye_cursos(grupo, organizacion) -> bool:
    if grupo is not None and (grupo.plan_linea_meta or '').strip():
        return plan_por_clave(grupo.plan_linea_meta).incluye_cursos
    if organizacion is not None and (organizacion.plan_linea_meta or '').strip():
        return plan_por_clave(organizacion.plan_linea_meta).incluye_cursos
    return False


def formato_telefono(raw: str) -> str:
    norm = normalizar_telefono(raw or '')
    if not norm:
        return 'Sin dato'
    if norm.startswith('57') and len(norm) == 12:
        local = norm[2:]
        return f'+57 {local[:3]} {local[3:6]} {local[6:]}'
    return f'+{norm}'


def estado_esperado(estudiante) -> str:
    if estudiante is None or not getattr(estudiante, 'pk', None):
        return 'Habeas pendiente'
    if (getattr(estudiante, 'estado_chat', '') or '') == 'ESPERANDO_HABEAS_DATA':
        return 'Habeas pendiente'
    from core.admin.estudiantes import etiqueta_estado_chat
    etiqueta, _slug = etiqueta_estado_chat(estudiante.estado_chat)
    return etiqueta


def html_cursos(organizacion, ya_ids=None, seleccion=None) -> str:
    ya = set(ya_ids or [])
    marcados = {int(valor) for valor in (seleccion or []) if str(valor).isdigit()}
    propios, generales, otras = cursos_agrupados(organizacion)
    visibles = [curso for curso in propios + generales + otras if curso.pk not in ya]
    buscador = ''
    if len(visibles) > 6:
        buscador = (
            '<input type="search" class="eki-cursos-buscar" '
            'placeholder="Buscar curso" autocomplete="off">'
        )
    titulo_propios = f'Cursos de {organizacion.nombre}' if organizacion else ''
    bloques = [
        _bloque_cursos(titulo_propios, [curso for curso in propios if curso.pk not in ya], marcados),
        _bloque_cursos(
            'Cursos generales de eki',
            [curso for curso in generales if curso.pk not in ya],
            marcados,
        ),
    ]
    if otras:
        bloques.append(_bloque_cursos(
            'Cursos de organizaciones demo',
            [curso for curso in otras if curso.pk not in ya],
            marcados,
        ))
    return (
        '<div class="eki-cursos" data-eki-cursos>'
        f'<p class="eki-cursos-ayuda">{escape(texto_cursos(organizacion))}</p>'
        '<button type="button" class="eki-curso-ninguno">Sin curso por ahora</button>'
        f'{buscador}{"".join(bloques)}</div>'
    )


def _bloque_cursos(titulo, cursos, marcados) -> str:
    if not cursos or not titulo:
        if not cursos:
            return ''
    tarjetas = format_html_join(
        '',
        '<label class="eki-curso-card">'
        '<input type="checkbox" name="cursos_a_inscribir" value="{}" {}>'
        '<span class="eki-curso-nombre">{}</span>'
        '<span class="eki-curso-mods">{}</span>'
        '<span class="eki-curso-chip">{}</span>'
        '</label>',
        (
            (
                curso.pk,
                mark_safe('checked') if curso.pk in marcados else '',
                curso.nombre,
                _mods(curso),
                'Clases · Aprende' if curso.es_modo_clases() else 'Módulos · WhatsApp',
            )
            for curso in cursos
        ),
    )
    if not titulo:
        return str(tarjetas)
    return str(format_html('<p class="eki-cursos-grupo">{}</p>{}', titulo, tarjetas))


def _mods(curso) -> str:
    n = getattr(curso, 'n_modulos', None)
    if n is None:
        n = curso.modulos.count()
    if n == 1:
        return '1 módulo'
    return f'{n} módulos'


def contexto_alta(organizacion, grupo, seleccion=None) -> dict:
    return {
        'texto': texto_cursos(organizacion),
        'plan': _texto_plan(grupo, organizacion),
        'aviso_cupo': plan_incluye_cursos(grupo, organizacion),
        'drip': bool(
            organizacion and organizacion.drip_modulos_solo_estudiantes_listados
        ),
        'grupos': [
            {'id': fila.pk, 'label': _etiqueta_grupo(fila)}
            for fila in GrupoEstudiantes.objects.filter(
                cliente=organizacion, activo=True,
            ).order_by('nombre')
        ] if organizacion is not None else [],
        'html': html_cursos(organizacion, seleccion=seleccion),
        'organizacion': organizacion.nombre if organizacion else 'Sin organización',
    }


def buscar_documento(numero: str, excluir_id=None) -> dict:
    from core.documento_identidad import normalizar_numero_documento

    limpio = normalizar_numero_documento(numero)
    if not limpio:
        return {'existe': False, 'limpio': ''}
    qs = Estudiante.objects.filter(cedula=limpio).select_related('cliente')
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    est = qs.first()
    if est is None:
        return {'existe': False, 'limpio': limpio}
    return {
        'existe': True,
        'limpio': limpio,
        'nombre': est.nombre,
        'organizacion': est.cliente.nombre if est.cliente_id else 'Sin organización',
        'url': reverse('admin:core_estudiante_change', args=[est.pk]),
    }


def buscar_telefono(raw: str, excluir_id=None) -> dict:
    norm = normalizar_telefono(raw or '')
    formato = formato_telefono(raw or '')
    if not norm:
        return {'existe': False, 'telefono': '', 'formato': 'Sin dato'}
    qs = Estudiante.objects.filter(telefono=norm).select_related('cliente')
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    est = qs.first()
    if est is None:
        return {'existe': False, 'telefono': norm, 'formato': formato}
    return {
        'existe': True,
        'telefono': norm,
        'formato': formato,
        'nombre': est.nombre,
        'organizacion': est.cliente.nombre if est.cliente_id else 'Sin organización',
        'url': reverse('admin:core_estudiante_change', args=[est.pk]),
    }


def _cliente_param(valor):
    if not valor:
        return None
    try:
        return Cliente.objects.filter(pk=int(valor)).first()
    except (TypeError, ValueError):
        return None


def _grupo_param(valor, organizacion):
    if not valor or organizacion is None:
        return None
    try:
        return GrupoEstudiantes.objects.filter(
            pk=int(valor), cliente=organizacion, activo=True,
        ).first()
    except (TypeError, ValueError):
        return None


def vista_contexto(request):
    from django.http import JsonResponse

    organizacion = _cliente_param(request.GET.get('cliente'))
    grupo = _grupo_param(request.GET.get('grupo'), organizacion)
    data = contexto_alta(organizacion, grupo, request.GET.getlist('cursos'))
    return JsonResponse(data)


def vista_documento(request):
    from django.http import JsonResponse

    excluir = request.GET.get('excluir')
    try:
        excluir_id = int(excluir) if excluir else None
    except (TypeError, ValueError):
        excluir_id = None
    return JsonResponse(buscar_documento(request.GET.get('numero') or '', excluir_id))


def vista_telefono(request):
    from django.http import JsonResponse

    excluir = request.GET.get('excluir')
    try:
        excluir_id = int(excluir) if excluir else None
    except (TypeError, ValueError):
        excluir_id = None
    return JsonResponse(buscar_telefono(request.GET.get('telefono') or '', excluir_id))


def resumen_panel(estudiante, organizacion, grupo, cursos) -> dict:
    nombre = (getattr(estudiante, 'nombre', None) or '').strip() or 'Sin dato'
    return {
        'iniciales': iniciales(nombre) if nombre != 'Sin dato' else '?',
        'nombre': nombre,
        'telefono': formato_telefono(getattr(estudiante, 'telefono', '') or ''),
        'organizacion': organizacion.nombre if organizacion else 'Sin organización',
        'estado': estado_esperado(estudiante),
        'plan': _texto_plan(grupo, organizacion),
        'cursos': [curso.nombre for curso in cursos] or ['Sin curso por ahora'],
        'aviso_cupo': plan_incluye_cursos(grupo, organizacion) and bool(cursos),
    }
