"""Ficha y listado nuevo de Cliente. Solo se registra si ADMIN_CLIENTES_V2 está activo."""
from django import forms
from django.contrib import admin

from core.admin.clientes import (
    ClienteAdmin,
    ConfiguracionDripClienteInline,
    FaqOrganizacionInline,
    HabilitacionModuloDripClienteInline,
    PortalUsuarioInline,
    ProductoCatalogoInline,
)
from core.models import ProductoComercial
from portal.forms import ClientePortalAdminForm


class ClienteAdminFormV2(ClientePortalAdminForm):
    """Mismo guardado que el formulario actual. No reescribe portal_productos si las casillas no cambian."""

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
    )

    fieldsets = (
        ('Datos', {
            'classes': ['tab'],
            'fields': (
                ('nombre', 'nit'),
                ('contacto_principal', 'telefono'),
                'email',
                'notas_internas',
                'activo',
                'es_demo',
                'fecha_registro',
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
                ('fecha_inicio_suscripcion', 'fecha_fin_suscripcion'),
                'cupos_portal',
                'plan_linea_meta',
            ),
        }),
        ('Productos y canales', {
            'classes': ['tab'],
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
            'fields': ('portal_usuarios_acciones',),
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
        ('Cobertura', {
            'classes': ['tab'],
            'fields': ('mapa_cobertura_rapido',),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        kwargs['form'] = self.form
        return super(ClienteAdmin, self).get_form(request, obj, **kwargs)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.blank and 'choices' not in kwargs:
            etiqueta = 'Sin plan' if db_field.name == 'plan_linea_meta' else 'Sin valor'
            kwargs['choices'] = db_field.get_choices(
                include_blank=True,
                blank_choice=[('', etiqueta)],
            )
        return super().formfield_for_choice_field(db_field, request, **kwargs)
