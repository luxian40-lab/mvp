"""Ficha y listado nuevo de Cliente. Solo se registra si ADMIN_CLIENTES_V2 está activo."""
import csv
from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.decorators import action

from core.admin.cliente_v2_flag import admin_clientes_v2_activo
from core.admin.clientes import (
    ClienteAdmin,
    ConfiguracionDripClienteInline,
    FaqOrganizacionInline,
    HabilitacionModuloDripClienteInline,
    PortalUsuarioInline,
    ProductoCatalogoInline,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, ProductoComercial, ProgresoEstudiante, WhatsappLog
from core.planes_linea import PLAN_CHOICES
from portal.forms import PORTAL_PRODUCTO_CHOICES, ClientePortalAdminForm


def _conteo(qs):
    return Coalesce(
        Subquery(
            qs.order_by().values('cliente_id').annotate(total=Count('pk')).values('total')[:1],
            output_field=IntegerField(),
        ),
        Value(0),
    )


def mapa_avance_por_cliente():
    """Promedio de avance por organización, en tres consultas fijas.

    Misma regla que ProgresoEstudiante.porcentaje_avance: módulos publicados,
    o todos si el curso es de clases. Sin progresos, el listado muestra «Sin dato».
    """
    totales = {}
    for row in (
        Modulo.objects.values('curso_id', 'curso__modo_aula')
        .annotate(
            total=Count('id'),
            publicados=Count('id', filter=Q(publicado_wa=True)),
        )
    ):
        if row['curso__modo_aula'] == 'clases':
            totales[row['curso_id']] = row['total']
        else:
            totales[row['curso_id']] = row['publicados']

    hechos = {
        row['progreso_id']: row
        for row in (
            ModuloCompletado.objects.filter(
                progreso__estudiante__activo=True,
                progreso__estudiante__cliente_id__isnull=False,
            )
            .values('progreso_id')
            .annotate(
                n_pub=Count('id', filter=Q(modulo__publicado_wa=True)),
                n_all=Count('id'),
            )
        )
    }
    sumas = {}
    cantidades = {}
    progresos = ProgresoEstudiante.objects.filter(
        estudiante__activo=True,
        estudiante__cliente_id__isnull=False,
    ).values_list('id', 'estudiante__cliente_id', 'curso_id', 'curso__modo_aula')
    for prog_id, cliente_id, curso_id, modo in progresos:
        total = totales.get(curso_id) or 0
        info = hechos.get(prog_id) or {}
        if modo == 'clases':
            hechos_n = info.get('n_all') or 0
        else:
            hechos_n = info.get('n_pub') or 0
        pct = 0 if total <= 0 else min(100, int(round(hechos_n * 100 / total)))
        sumas[cliente_id] = sumas.get(cliente_id, 0) + pct
        cantidades[cliente_id] = cantidades.get(cliente_id, 0) + 1
    return {
        cliente_id: int(round(sumas[cliente_id] / cantidades[cliente_id]))
        for cliente_id in cantidades
    }


def _texto_sin_plan():
    from django.conf import settings

    default = (getattr(settings, 'LINEA_META_PLAN_DEFAULT', '') or '').strip()
    etiquetas = dict(PLAN_CHOICES)
    if default in etiquetas:
        return (
            f'Sin plan en la organización: el servidor usa {etiquetas[default]}. '
            'Un grupo puede tener otro plan.'
        )
    return (
        'Sin plan: no abre cursos nuevos ni el asesor. '
        'Un grupo puede tener otro plan.'
    )


def tabs_cliente(request):
    """Pestañas del listado. Sin conteos en el resto del admin."""
    if not admin_clientes_v2_activo():
        return []
    try:
        ruta = reverse('admin:core_cliente_changelist')
    except Exception:
        return []
    if not (request.path or '').startswith(str(ruta)):
        return []
    base = Cliente.objects.all()
    conteos = {
        '': base.count(),
        'reales': base.filter(es_demo=False).count(),
        'demo': base.filter(es_demo=True).count(),
        'sin_plan': base.filter(plan_linea_meta='').count(),
        'inactivos': base.filter(activo=False).count(),
    }
    vista = request.GET.get('eki_org') or ''
    if vista not in conteos:
        vista = ''

    def item(clave, titulo):
        enlace = str(ruta) if not clave else f'{ruta}?eki_org={clave}'
        return {
            'title': f'{titulo} · {conteos[clave]}',
            'link': enlace,
            'active': vista == clave,
            'has_permission': True,
        }

    return [{
        'models': ['core.cliente'],
        'items': [
            item('', 'Todos'),
            item('reales', 'Reales'),
            item('demo', 'Demo y pruebas'),
            item('sin_plan', 'Sin plan Meta'),
            item('inactivos', 'Inactivos'),
        ],
    }]


class OrganizacionVistaFilter(admin.SimpleListFilter):
    title = 'Vista'
    parameter_name = 'eki_org'

    def lookups(self, request, model_admin):
        return (
            ('reales', 'Reales'),
            ('demo', 'Demo y pruebas'),
            ('sin_plan', 'Sin plan Meta'),
            ('inactivos', 'Inactivos'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == 'reales':
            return queryset.filter(es_demo=False)
        if valor == 'demo':
            return queryset.filter(es_demo=True)
        if valor == 'sin_plan':
            return queryset.filter(plan_linea_meta='')
        if valor == 'inactivos':
            return queryset.filter(activo=False)
        return queryset


class ProductoContratadoFilter(admin.SimpleListFilter):
    title = 'Producto contratado'
    parameter_name = 'producto'

    def lookups(self, request, model_admin):
        return PORTAL_PRODUCTO_CHOICES

    def queryset(self, request, queryset):
        valor = self.value()
        if not valor:
            return queryset
        return queryset.filter(
            Q(portal_productos__contains=valor)
            | (Q(portal_productos='') & Q(tipo_proyecto=valor))
        )


class SuscripcionClienteFilter(admin.SimpleListFilter):
    title = 'Suscripción'
    parameter_name = 'suscripcion'

    def lookups(self, request, model_admin):
        return (
            ('vigente', 'Vigente'),
            ('por_vencer', 'Por vencer'),
            ('vencida', 'Vencida'),
        )

    def queryset(self, request, queryset):
        valor = self.value()
        if not valor:
            return queryset
        hoy = timezone.localdate()
        limite = hoy + timedelta(days=30)
        if valor == 'vencida':
            return queryset.filter(fecha_fin_suscripcion__lt=hoy)
        if valor == 'por_vencer':
            return queryset.filter(
                fecha_fin_suscripcion__gte=hoy,
                fecha_fin_suscripcion__lt=limite,
            )
        if valor == 'vigente':
            return queryset.filter(
                Q(fecha_fin_suscripcion__isnull=True)
                | Q(fecha_fin_suscripcion__gte=limite)
            )
        return queryset


class ClienteAdminFormV2(ClientePortalAdminForm):
    """Mismo guardado que el formulario actual. No reescribe portal_productos si las casillas no cambian."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ayudas = {
            'activo': 'Si lo desactiva, sus estudiantes dejan de recibir mensajes.',
            'es_demo': 'Marca organizaciones de prueba. No cambia envíos ni permisos.',
            'logo_archivo': 'Suba PNG, JPG, WebP o GIF. Máximo 5 MB. Se guarda al pulsar Guardar.',
            'logo_url': 'O pegue una URL. Si sube un archivo, esta URL se reemplaza.',
            'quitar_logo': 'Quita el logo y vuelve a la inicial del nombre.',
            'wallpaper_archivo': 'Fondo de Aprende. JPG, PNG o WebP. Máximo 2 MB.',
            'wallpaper_aula_url': 'O pegue la URL del fondo. Si sube un archivo, se completa al guardar.',
            'quitar_wallpaper': 'Quita el fondo y vuelve al de eki.',
            'portal_subtitulo': 'Texto corto bajo el nombre en el portal.',
            'plan_linea_meta': 'Vacío = sin plan. Un grupo puede tener otro plan.',
            'fecha_fin_suscripcion': 'Al pasar esta fecha, el plan de la organización deja de aplicar.',
            'numero_whatsapp_nat': 'Solo dígitos, entre 8 y 15, con indicativo de país.',
        }
        for nombre, texto in ayudas.items():
            if nombre in self.fields:
                self.fields[nombre].help_text = texto

    def clean_numero_whatsapp_nat(self):
        raw = (self.cleaned_data.get('numero_whatsapp_nat') or '').strip()
        anterior = ''
        if self.instance.pk:
            anterior = (self.instance.numero_whatsapp_nat or '').strip()
        if raw == anterior:
            return raw
        if raw and (not raw.isdigit() or not 8 <= len(raw) <= 15):
            raise forms.ValidationError(
                'Use solo dígitos, entre 8 y 15, con indicativo de país.'
            )
        if raw:
            from core.models import Cliente

            otro = Cliente.objects.filter(numero_whatsapp_nat=raw)
            if self.instance.pk:
                otro = otro.exclude(pk=self.instance.pk)
            tomado = otro.only('nombre').first()
            if tomado:
                raise forms.ValidationError(
                    f'Ese número ya lo usa {tomado.nombre}.'
                )
        return raw

    def save(self, commit=True):
        anterior = self.instance.portal_productos if self.instance.pk else None
        obj = super().save(commit=False)
        mods = list(self.cleaned_data.get('portal_modulos') or [])
        if anterior is not None:
            prev = [p.strip() for p in (anterior or '').split(',') if p.strip()]
            if set(prev) == set(mods) and len(prev) == len(mods):
                obj.portal_productos = anterior
        if commit:
            obj.save()
            self.save_m2m()
            if obj.pk:
                self.sync_media_fields(obj)
        return obj


class ProductoCatalogoInlineV2(ProductoCatalogoInline):
    per_page = 20


class HabilitacionModuloDripClienteInlineV2(HabilitacionModuloDripClienteInline):
    per_page = 25


class ProductoComercialInlineV2(admin.TabularInline):
    """Precios SKU. El admin propio y la importación Excel no se mueven."""

    model = ProductoComercial
    extra = 0
    tab = True
    per_page = 20
    show_change_link = True
    fields = (
        'sku', 'nombre', 'presentacion', 'unidad', 'stock', 'precio', 'moneda',
        'categoria', 'notas', 'vigencia_desde', 'vigencia_hasta', 'activo',
    )
    verbose_name = 'Precio comercial'
    verbose_name_plural = 'Precios comerciales (Nat)'


class ClienteAdminV2(ClienteAdmin):
    """Misma lógica de guardado, permisos y acciones. Cambia la disposición."""

    form = ClienteAdminFormV2
    change_form_template = 'admin/core/cliente/change_form_v2.html'
    change_form_before_template = 'admin/core/cliente/encabezado.html'
    change_list_template = 'admin/core/cliente/change_list_v2.html'
    search_help_text = 'Buscar por nombre, NIT, contacto o correo'
    list_display = (
        'columna_organizacion',
        'columna_plan',
        'columna_productos',
        'columna_estudiantes',
        'columna_cursos',
        'columna_suscripcion',
    )
    list_display_links = ('columna_organizacion',)
    list_filter = (
        OrganizacionVistaFilter,
        'activo',
        'plan_linea_meta',
        ProductoContratadoFilter,
        SuscripcionClienteFilter,
        'es_demo',
    )
    actions_list = ('nuevo_cliente', 'exportar_clientes')
    actions_row = ('abrir_cliente', 'ver_estudiantes', 'ver_campanas')
    actions = ClienteAdmin.actions + ['asignar_plan_linea_meta']
    inlines = [
        PortalUsuarioInline,
        FaqOrganizacionInline,
        ConfiguracionDripClienteInline,
        HabilitacionModuloDripClienteInlineV2,
        ProductoCatalogoInlineV2,
        ProductoComercialInlineV2,
    ]
    readonly_fields = ClienteAdmin.readonly_fields + (
        'fecha_registro',
        'peso_gamificacion_reto',
        'peso_gamificacion_abierta',
        'resumen_suscripcion',
        'personas_enlaces',
        'pqrs_resumen',
        'cobertura_departamentos',
        'actividad_reciente',
        'zona_peligro',
    )

    fieldsets = (
        ('Datos', {
            'classes': ['tab'],
            'description': 'Si desactiva el cliente, sus estudiantes dejan de recibir mensajes.',
            'fields': (
                ('nombre', 'nit'),
                ('contacto_principal', 'telefono'),
                ('email', 'es_demo'),
                'notas_internas',
                ('activo', 'fecha_registro'),
                'zona_peligro',
            ),
        }),
        ('Marca', {
            'classes': ['tab'],
            'fields': (
                'logo_archivo',
                'logo_url',
                'quitar_logo',
                'logo_preview',
                'portal_subtitulo',
                'wallpaper_archivo',
                'wallpaper_aula_url',
                'quitar_wallpaper',
                'wallpaper_preview',
            ),
        }),
        ('Suscripción y plan', {
            'classes': ['tab'],
            'fields': (
                'resumen_suscripcion',
                ('fecha_inicio_suscripcion', 'fecha_fin_suscripcion'),
                'cupos_portal',
                'plan_linea_meta',
            ),
        }),
        ('Productos y canales', {
            'classes': ['tab'],
            'description': 'Las casillas se guardan como el texto separado por comas de siempre.',
            'fields': (
                'tipo_proyecto',
                'portal_modulos',
                'numero_whatsapp_nat',
                'numero_whatsapp_autorizado',
                'whatsapp_numero',
                'twilio_account_sid',
                'twilio_auth_token',
                'twilio_whatsapp_from',
                'enlace_habeas_data',
                'content_sid_habeas_data_twilio',
                'enlace_grupo_whatsapp',
                'gei_factores_json',
            ),
        }),
        ('Enseñanza', {
            'classes': ['tab'],
            'fields': (
                'modo_gamificacion',
                'usar_gamificacion',
                'drip_modulos_solo_estudiantes_listados',
                'peso_gamificacion_reto',
                'peso_gamificacion_abierta',
                'enviar_certificados_email',
                'exigir_nota_minima_certificado',
                'nota_minima_certificado',
                'modo_avance_modulo',
                'content_sid_boton_listo',
                'habilitar_pregunta_abierta_final',
                'fecha_inicio_pregunta_abierta_final',
                'fecha_fin_pregunta_abierta_final',
                'habilitar_gamificacion_proximidad',
                'fecha_inicio_gamificacion_proximidad',
                'fecha_fin_gamificacion_proximidad',
                'cobertura_y_drip_acciones',
            ),
        }),
        ('Personas', {
            'classes': ['tab'],
            'description': 'Usuarios del portal, grupos y estudiantes de esta organización.',
            'fields': ('portal_usuarios_acciones', 'personas_enlaces'),
        }),
        ('Catálogo Nat', {
            'classes': ['tab'],
            'fields': (
                'empleabilidad_kpis_resumen',
                'empleabilidad_exploracion_activa',
                'empleabilidad_radio_metros',
                'empleabilidad_cooldown_horas',
                'empleabilidad_max_misiones_dia',
                'empleabilidad_puntos_validacion',
                'nombre_agente_tutor',
                'nombre_agente_asistente',
                'perfil_facilitador',
                'nombre_bot',
                'system_prompt_extra',
                'desactivar_llm_comercial',
            ),
        }),
        ('Atención PQRS', {
            'classes': ['tab'],
            'description': 'Las preguntas se editan en la pestaña FAQ organización.',
            'fields': ('pqrs_resumen',),
        }),
        ('Cobertura', {
            'classes': ['tab'],
            'description': 'El mapa es el mismo de Cobertura. Aquí solo el conteo por departamento.',
            'fields': ('mapa_cobertura_rapido', 'cobertura_departamentos'),
        }),
        ('Actividad', {
            'classes': ['tab'],
            'fields': ('actividad_reciente',),
        }),
    )

    @admin.display(description='Grupos y estudiantes')
    def personas_enlaces(self, obj):
        if not obj or not obj.pk:
            return 'Guarde para ver grupos y estudiantes.'
        from core.models_extras import GrupoEstudiantes

        n_est = Estudiante.objects.filter(cliente=obj).count()
        n_act = Estudiante.objects.filter(cliente=obj, activo=True).count()
        n_gru = GrupoEstudiantes.objects.filter(cliente=obj).count()
        est_url = (
            reverse('admin:core_estudiante_changelist')
            + f'?cliente__id__exact={obj.pk}'
        )
        gru_url = (
            reverse('admin:core_grupoestudiantes_changelist')
            + f'?cliente__id__exact={obj.pk}'
        )
        return format_html(
            '<p><a href="{}">{} estudiantes</a> ({} activos)</p>'
            '<p><a href="{}">{} grupos</a></p>',
            est_url,
            n_est,
            n_act,
            gru_url,
            n_gru,
        )

    @admin.display(description='Preguntas de la organización')
    def pqrs_resumen(self, obj):
        if not obj or not obj.pk:
            return 'Guarde para cargar las preguntas.'
        from core.models import FaqOrganizacion

        n = FaqOrganizacion.objects.filter(cliente=obj).count()
        if n == 0:
            return 'Sin dato. Agregue preguntas en la pestaña FAQ organización.'
        return f'{n} preguntas en la pestaña FAQ organización.'

    @admin.display(description='Estudiantes por departamento')
    def cobertura_departamentos(self, obj):
        if not obj or not obj.pk:
            return 'Sin dato'
        filas = (
            Estudiante.objects.filter(cliente=obj, activo=True)
            .values('departamento')
            .annotate(n=Count('pk'))
            .order_by('-n', 'departamento')
        )
        if not filas:
            return 'Sin dato'
        partes = []
        for fila in filas:
            nombre = (fila['departamento'] or '').strip() or 'Sin departamento'
            partes.append(f'{nombre}: {fila["n"]}')
        return format_html('<ul>{}</ul>', format_html(
            ''.join('<li>{}</li>' for _ in partes),
            *partes,
        ))

    @admin.display(description='Campañas, mensajes e historial')
    def actividad_reciente(self, obj):
        if not obj or not obj.pk:
            return 'Guarde para ver la actividad.'
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        from core.models import Campana

        n_camp = Campana.objects.filter(cliente=obj).count()
        camp_url = reverse('admin:core_campana_changelist') + f'?cliente__id__exact={obj.pk}'
        campanas = list(
            Campana.objects.filter(cliente=obj).order_by('-id').values_list('nombre', flat=True)[:5]
        )
        mensajes = list(
            WhatsappLog.objects.filter(estudiante__cliente=obj)
            .order_by('-fecha')
            .values_list('fecha', 'mensaje')[:5]
        )
        ct = ContentType.objects.get_for_model(Cliente)
        historial = list(
            LogEntry.objects.filter(content_type=ct, object_id=str(obj.pk))
            .select_related('user')
            .order_by('-action_time')[:8]
        )
        if campanas:
            lista_camp = format_html(
                '<ul>{}</ul>',
                format_html(''.join('<li>{}</li>' for _ in campanas), *campanas),
            )
        else:
            lista_camp = 'Sin dato'
        if mensajes:
            lineas = [
                f'{fecha:%d/%m/%Y %H:%M} · {(mensaje or "")[:60]}'
                for fecha, mensaje in mensajes
            ]
            lista_wa = format_html(
                '<ul>{}</ul>',
                format_html(''.join('<li>{}</li>' for _ in lineas), *lineas),
            )
        else:
            lista_wa = 'Sin dato'
        if historial:
            lineas_h = [
                f'{item.action_time:%d/%m/%Y %H:%M} · {item.user or "Sin dato"} · {item.change_message or item.get_action_flag_display()}'
                for item in historial
            ]
            lista_h = format_html(
                '<ul>{}</ul>',
                format_html(''.join('<li>{}</li>' for _ in lineas_h), *lineas_h),
            )
        else:
            lista_h = 'Sin dato'
        return format_html(
            '<p><a href="{}">{} campañas</a></p>{}'
            '<p><strong>Últimos WhatsApp</strong></p>{}'
            '<p><strong>Historial de cambios</strong></p>{}',
            camp_url,
            n_camp,
            lista_camp,
            lista_wa,
            lista_h,
        )

    @admin.display(description='Estado de la suscripción')
    def resumen_suscripcion(self, obj):
        if not obj or not obj.pk:
            return 'Guarde para ver el estado de la suscripción.'
        hoy = timezone.localdate()
        fin = obj.fecha_fin_suscripcion
        if not obj.activo:
            estado = 'Inactivo'
            detalle = 'Sus estudiantes dejan de recibir mensajes y el plan no aplica.'
        elif not fin:
            estado = 'Sin dato'
            detalle = 'No hay fecha de fin. El plan sigue mientras el cliente esté activo.'
        else:
            dias = (fin - hoy).days
            if dias < 0:
                estado = f'Vencida hace {abs(dias)} días'
                detalle = (
                    'La suscripción venció: el plan de la organización no aplica. '
                    'No abre cursos nuevos ni el asesor. Los cursos ya empezados siguen.'
                )
            elif dias < 30:
                estado = f'Por vencer, faltan {dias} días'
                detalle = 'Al pasar la fecha de fin, el plan de la organización deja de aplicar.'
            else:
                estado = f'Vigente, faltan {dias} días'
                detalle = 'Al pasar la fecha de fin, el plan de la organización deja de aplicar.'
        filas = format_html(
            '<tr><td>OP1</td><td>1 curso al mes y asesor (30 preguntas)</td></tr>'
            '<tr><td>OP2</td><td>2 cursos al mes, sin asesor</td></tr>'
            '<tr><td>OP3</td><td>Asesor, 60 preguntas al mes, sin cursos nuevos</td></tr>'
        )
        return format_html(
            '<p><strong>{}</strong> {}</p>'
            '<table><thead><tr><th>Plan</th><th>Qué incluye</th></tr></thead>'
            '<tbody>{}</tbody></table><p>{}</p>',
            estado,
            detalle,
            filas,
            _texto_sin_plan(),
        )

    def get_fieldsets(self, request, obj=None):
        salida = []
        for nombre, opciones in super().get_fieldsets(request, obj):
            opciones = dict(opciones)
            if nombre == 'Marca':
                opciones['description'] = self._panel_asi_se_ve(obj)
            salida.append((nombre, opciones))
        return salida

    def _panel_asi_se_ve(self, obj):
        if not obj or not obj.pk:
            return 'Guarde la organización para ver el logo y el fondo.'
        from portal.branding import contexto_identidad_org

        ctx = contexto_identidad_org(obj)
        logo = ctx.get('eki_org_logo') or ''
        fondo = ctx.get('eki_org_wallpaper') or ''
        if logo:
            logo_html = format_html(
                '<img src="{}" alt="" style="max-width:100%;max-height:6rem;object-fit:contain">',
                logo,
            )
        else:
            logo_html = 'Sin logo'
        if fondo:
            fondo_html = format_html(
                '<a href="{}" target="_blank" rel="noopener">Ver fondo actual</a>',
                fondo,
            )
        else:
            fondo_html = 'Sin fondo'
        subtitulo = (obj.portal_subtitulo or '').strip() or 'Sin subtítulo'
        return format_html(
            '<aside class="eki-marca-preview"><h3>Así se ve</h3>'
            '<p>{}</p><p><strong>Logo</strong><br>{}</p>'
            '<p><strong>Fondo Aprende</strong><br>{}</p></aside>',
            subtitulo,
            logo_html,
            fondo_html,
        )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            etiquetas = dict(PORTAL_PRODUCTO_CHOICES)
            raw = (obj.portal_productos or '').strip()
            if raw:
                productos = [
                    etiquetas.get(p.strip(), p.strip())
                    for p in raw.split(',')
                    if p.strip()
                ]
            elif obj.tipo_proyecto:
                productos = [obj.get_tipo_proyecto_display()]
            else:
                productos = []
            extra_context['eki_cli_productos'] = productos
            extra_context['eki_cli_sin_plan'] = not (obj.plan_linea_meta or '').strip()
            extra_context['eki_cli_plan'] = dict(PLAN_CHOICES).get(obj.plan_linea_meta, '')
            extra_context['eki_cli_texto_sin_plan'] = _texto_sin_plan()
        return super().change_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            n_estudiantes=_conteo(
                Estudiante.objects.filter(cliente_id=OuterRef('pk'), activo=True)
            ),
            n_cursos=_conteo(Curso.objects.filter(cliente_id=OuterRef('pk'))),
            ultima_wa=Subquery(
                WhatsappLog.objects.filter(estudiante__cliente_id=OuterRef('pk'))
                .order_by('-fecha')
                .values('fecha')[:1]
            ),
        )

    def changelist_view(self, request, extra_context=None):
        request.eki_avance_cliente = mapa_avance_por_cliente()
        return super().changelist_view(request, extra_context)

    @admin.display(description='Organización', ordering='nombre')
    def columna_organizacion(self, obj):
        from django.templatetags.static import static

        from core.client_logos import logo_estatico_para_nombre

        url = (obj.logo_url or '').strip()
        if not url:
            rel = logo_estatico_para_nombre(obj.nombre)
            if rel:
                url = static(rel)
        inicial = (obj.nombre or '?').strip()[:1].upper()
        if url:
            marca = format_html(
                '<img class="eki-cli-logo" src="{}" alt="" loading="lazy" '
                'referrerpolicy="no-referrer">',
                url,
            )
        else:
            marca = format_html('<span class="eki-cli-logo eki-cli-logo--ph">{}</span>', inicial)
        ultima = getattr(obj, 'ultima_wa', None)
        if ultima is None:
            cuando = 'Sin dato'
        else:
            dias = (timezone.localdate() - timezone.localtime(ultima).date()).days
            if dias <= 0:
                cuando = 'hoy'
            elif dias == 1:
                cuando = 'hace 1 día'
            else:
                cuando = f'hace {dias} días'
        estado = 'Activo' if obj.activo else 'Inactivo'
        demo = ''
        if obj.es_demo:
            demo = format_html(' <span class="eki-cli-chip">Demo</span>')
        return format_html(
            '<div class="eki-cli-org">{}<div><strong>{}</strong>{}'
            '<div class="eki-cli-meta">{} · {}</div></div></div>',
            marca,
            obj.nombre,
            demo,
            estado,
            cuando,
        )

    @admin.display(description='Plan Meta', ordering='plan_linea_meta')
    def columna_plan(self, obj):
        chips = {
            'curso_asesor': 'OP1',
            'dos_cursos': 'OP2',
            'asesor_60': 'OP3',
        }
        clave = (obj.plan_linea_meta or '').strip()
        if clave in chips:
            return format_html('<span class="eki-cli-chip">{}</span>', chips[clave])
        return format_html(
            '<span class="eki-cli-chip eki-cli-chip--ambar" title="{}">Sin plan</span>',
            _texto_sin_plan(),
        )

    @admin.display(description='Productos contratados')
    def columna_productos(self, obj):
        etiquetas = dict(PORTAL_PRODUCTO_CHOICES)
        raw = (obj.portal_productos or '').strip()
        if raw:
            claves = [p.strip() for p in raw.split(',') if p.strip()]
        elif obj.tipo_proyecto:
            claves = [obj.tipo_proyecto]
        else:
            claves = []
        if not claves:
            return 'Sin dato'
        return format_html(
            '{}' * len(claves),
            *[
                format_html(
                    '<span class="eki-cli-chip">{}</span> ',
                    etiquetas.get(clave, clave),
                )
                for clave in claves
            ],
        )

    @admin.display(description='Estudiantes', ordering='n_estudiantes')
    def columna_estudiantes(self, obj):
        n = getattr(obj, 'n_estudiantes', 0) or 0
        mapa = getattr(getattr(self, 'request', None), 'eki_avance_cliente', None) or {}
        pct = mapa.get(obj.pk)
        if pct is None:
            barra = 'Sin dato'
        else:
            barra = format_html(
                '<span class="eki-cli-bar" title="Avance promedio">'
                '<span style="width:{}%"></span></span> {}%',
                pct,
                pct,
            )
        return format_html('<div>{}</div><div>{}</div>', n, barra)

    @admin.display(description='Cursos', ordering='n_cursos')
    def columna_cursos(self, obj):
        return getattr(obj, 'n_cursos', 0) or 0

    @admin.display(description='Suscripción', ordering='fecha_fin_suscripcion')
    def columna_suscripcion(self, obj):
        fin = obj.fecha_fin_suscripcion
        if not fin:
            return 'Sin dato'
        dias = (fin - timezone.localdate()).days
        if dias < 0:
            return format_html(
                '<span class="eki-cli-chip eki-cli-chip--rojo">Venció hace {} días</span>',
                abs(dias),
            )
        if dias < 30:
            return format_html(
                '<span class="eki-cli-chip eki-cli-chip--ambar">Vence en {} días</span>',
                dias,
            )
        return format_html('<span class="eki-cli-chip">Vence en {} días</span>', dias)

    @action(description='Nuevo cliente', url_path='nuevo-cliente', icon='add', permissions=['add'])
    def nuevo_cliente(self, request):
        return redirect('admin:core_cliente_add')

    @action(description='Exportar', url_path='exportar-clientes', icon='download', permissions=['view'])
    def exportar_clientes(self, request):
        qs = self.get_queryset(request).order_by('nombre')
        respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
        respuesta['Content-Disposition'] = 'attachment; filename="organizaciones.csv"'
        respuesta.write('\ufeff')
        writer = csv.writer(respuesta)
        writer.writerow([
            'Nombre', 'NIT', 'Activo', 'Demo', 'Plan Meta', 'Productos',
            'Estudiantes activos', 'Cursos', 'Fin de suscripción', 'Último WhatsApp',
        ])
        for obj in qs:
            writer.writerow([
                obj.nombre,
                obj.nit,
                'sí' if obj.activo else 'no',
                'sí' if obj.es_demo else 'no',
                obj.plan_linea_meta,
                obj.portal_productos or obj.tipo_proyecto,
                getattr(obj, 'n_estudiantes', 0) or 0,
                getattr(obj, 'n_cursos', 0) or 0,
                obj.fecha_fin_suscripcion.isoformat() if obj.fecha_fin_suscripcion else '',
                timezone.localtime(obj.ultima_wa).strftime('%Y-%m-%d %H:%M') if getattr(obj, 'ultima_wa', None) else '',
            ])
        return respuesta

    @action(description='Abrir', url_path='abrir', icon='open_in_new', permissions=['view'])
    def abrir_cliente(self, request, object_id):
        return redirect('admin:core_cliente_change', object_id)

    @action(description='Ver estudiantes', url_path='ver-estudiantes', icon='group', permissions=['view'])
    def ver_estudiantes(self, request, object_id):
        url = reverse('admin:core_estudiante_changelist') + f'?cliente__id__exact={object_id}'
        return redirect(url)

    @action(description='Ver campañas', url_path='ver-campanas', icon='campaign', permissions=['view'])
    def ver_campanas(self, request, object_id):
        url = reverse('admin:core_campana_changelist') + f'?cliente__id__exact={object_id}'
        return redirect(url)

    @admin.action(description='Asignar plan de línea Meta')
    def asignar_plan_linea_meta(self, request, queryset):
        if request.POST.get('aplicar') == '1':
            plan = request.POST.get('plan_linea_meta', '')
            validos = {clave for clave, _etiqueta in PLAN_CHOICES} | {''}
            if plan not in validos:
                self.message_user(request, 'Ese plan no existe.', level=messages.ERROR)
                return None
            n_org = queryset.count()
            n_est = Estudiante.objects.filter(cliente__in=queryset).count()
            queryset.update(plan_linea_meta=plan)
            self.message_user(
                request,
                f'Plan actualizado en {n_org} organizaciones. Afecta a {n_est} estudiantes.',
            )
            return None
        context = {
            **self.admin_site.each_context(request),
            'title': 'Asignar plan de línea Meta',
            'queryset': queryset,
            'n_org': queryset.count(),
            'n_est': Estudiante.objects.filter(cliente__in=queryset).count(),
            'planes': PLAN_CHOICES,
            'action_checkbox_name': ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
        }
        return render(request, 'admin/core/cliente/asignar_plan.html', context)

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                '<int:cliente_id>/eliminar/',
                self.admin_site.admin_view(self.eliminar_cliente_view),
                name='core_cliente_eliminar',
            ),
        ]
        return extra + urls

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if change and obj is not None:
            context['show_delete'] = False
        return super().render_change_form(
            request, context, add, change, form_url, obj,
        )

    def response_change(self, request, obj):
        if '_desactivar' in request.POST:
            obj.activo = False
            obj.save(update_fields=['activo'])
            self.message_user(
                request,
                'Organización desactivada. Sus estudiantes dejan de recibir mensajes.',
            )
            return redirect('admin:core_cliente_change', obj.pk)
        return super().response_change(request, obj)

    def _tiene_trabajo(self, obj):
        from core.models import Campana

        return (
            Estudiante.objects.filter(cliente=obj).exists()
            or Curso.objects.filter(cliente=obj).exists()
            or Campana.objects.filter(cliente=obj).exists()
        )

    @admin.display(description='Zona de peligro')
    def zona_peligro(self, obj):
        if not obj or not obj.pk:
            return 'Guarde la organización antes de eliminarla.'
        url = reverse('admin:core_cliente_eliminar', args=[obj.pk])
        return format_html(
            '<p>Eliminar sale de esta barra. Desactivar deja el registro y corta los mensajes.</p>'
            '<p><button type="submit" name="_desactivar" class="button">Desactivar</button> '
            '<a class="button" href="{}">Eliminar cliente</a></p>',
            url,
        )

    def eliminar_cliente_view(self, request, cliente_id):
        from django.core.exceptions import PermissionDenied

        obj = self.get_object(request, str(cliente_id))
        if obj is None:
            return redirect('admin:core_cliente_changelist')
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied
        bloqueado = self._tiene_trabajo(obj)
        error = ''
        if request.method == 'POST' and not bloqueado:
            if (request.POST.get('confirmacion') or '').strip() == obj.nombre:
                nombre = obj.nombre
                self.delete_model(request, obj)
                self.message_user(request, f'Se eliminó {nombre}.')
                return redirect('admin:core_cliente_changelist')
            error = 'Escriba el nombre exacto de la organización.'
        context = {
            **self.admin_site.each_context(request),
            'title': 'Eliminar cliente',
            'opts': self.model._meta,
            'original': obj,
            'bloqueado': bloqueado,
            'error': error,
            'desactivar_url': reverse('admin:core_cliente_change', args=[obj.pk]),
        }
        return render(request, 'admin/core/cliente/eliminar.html', context)

    def get_form(self, request, obj=None, **kwargs):
        kwargs['form'] = self.form
        return super(ClienteAdmin, self).get_form(request, obj, **kwargs)

    class Media:
        css = {'all': ('admin/css/eki_cliente_v2.css',)}

    def get_action_choices(self, request, default_choices=None):
        from django.contrib.admin.options import ModelAdmin

        return ModelAdmin.get_action_choices(self, request, [('', 'Elegir acción')])

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.blank and 'choices' not in kwargs:
            etiqueta = 'Sin plan' if db_field.name == 'plan_linea_meta' else 'Sin valor'
            kwargs['choices'] = db_field.get_choices(
                include_blank=True,
                blank_choice=[('', etiqueta)],
            )
        return super().formfield_for_choice_field(db_field, request, **kwargs)
