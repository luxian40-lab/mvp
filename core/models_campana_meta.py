"""Plantillas y campañas WhatsApp creadas directo en Meta (Graph API).

No comparte envío con Campana / Content SID de Twilio.
"""
from __future__ import annotations

import re
import unicodedata

from django.core.exceptions import ValidationError
from django.db import models

_VAR_RE = re.compile(r'\{\{(\d+)\}\}')
_NOMBRE_META_RE = re.compile(r'^[a-z0-9_]+$')

ESTADOS_PLANTILLA = [
    ('BORRADOR', 'Borrador'),
    ('PENDING', 'Pendiente'),
    ('APPROVED', 'Aprobada'),
    ('REJECTED', 'Rechazada'),
    ('PAUSED', 'Pausada'),
    ('DISABLED', 'Deshabilitada'),
    ('IN_APPEAL', 'En apelación'),
    ('ERROR', 'Error'),
]

CATEGORIAS_META = [
    ('MARKETING', 'Marketing'),
    ('UTILITY', 'Utilidad'),
    ('AUTHENTICATION', 'Autenticación'),
]


def sanitizar_nombre_meta(nombre: str) -> str:
    bruto = (nombre or '').strip().lower().replace(' ', '_').replace('-', '_')
    bruto = unicodedata.normalize('NFKD', bruto)
    bruto = ''.join(c for c in bruto if not unicodedata.combining(c))
    limpio = ''.join(c for c in bruto if c.isascii() and (c.isalnum() or c == '_'))
    return limpio[:512]


def variables_en(texto: str) -> list[int]:
    return [int(n) for n in _VAR_RE.findall(texto or '')]


def validar_variables_secuenciales(texto: str, etiqueta: str) -> None:
    nums = variables_en(texto)
    if not nums:
        return
    esperadas = list(range(1, max(nums) + 1))
    if sorted(set(nums)) != esperadas:
        raise ValidationError({
            etiqueta: 'Las variables deben ser {{1}}, {{2}}… en orden, sin saltos.',
        })
    cuerpo = (texto or '').strip()
    if cuerpo.startswith('{{') or cuerpo.endswith('}}'):
        raise ValidationError({
            etiqueta: 'El texto no puede empezar ni terminar con una variable.',
        })
    if '}}{{' in cuerpo.replace(' ', ''):
        raise ValidationError({
            etiqueta: 'Dos variables no pueden ir pegadas.',
        })


def ejemplos_lista(texto: str) -> list[str]:
    return [p.strip() for p in (texto or '').split('|') if p.strip()]


class PlantillaMeta(models.Model):
    """Plantilla HSM creada con POST /{waba}/message_templates."""

    nombre_interno = models.CharField(max_length=120, verbose_name='Nombre interno')
    meta_name = models.CharField(
        max_length=512,
        blank=True,
        verbose_name='Nombre en Meta',
        help_text='Minúsculas y guion bajo. Si se deja vacío, se arma desde el nombre interno.',
    )
    idioma = models.CharField(max_length=10, default='es', verbose_name='Idioma')
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIAS_META,
        default='UTILITY',
        verbose_name='Categoría Meta',
    )
    header_texto = models.CharField(
        max_length=60,
        blank=True,
        verbose_name='Header',
        help_text='Opcional. Texto, puede incluir {{1}}.',
    )
    header_ejemplo = models.CharField(
        max_length=60,
        blank=True,
        verbose_name='Ejemplo del header',
        help_text='Obligatorio si el header tiene {{1}}.',
    )
    cuerpo = models.TextField(
        verbose_name='Cuerpo',
        help_text='Texto que ve la persona. Variables {{1}}, {{2}}…',
    )
    ejemplos_cuerpo = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Ejemplos del cuerpo',
        help_text='Un valor por variable, separados por |. Ej: Ana|Café',
    )
    footer = models.CharField(max_length=60, blank=True, verbose_name='Footer')
    tipo = models.CharField(
        max_length=16,
        choices=[('TEXTO', 'Texto'), ('CARRUSEL', 'Carrusel')],
        default='TEXTO',
        verbose_name='Tipo',
        help_text='El carrusel se crea en Meta con la acción «Enviar plantilla a Meta para aprobación».',
    )
    boton_1_tipo = models.CharField(
        max_length=20,
        blank=True,
        choices=[('', 'Sin botón'), ('QUICK_REPLY', 'Respuesta rápida'), ('URL', 'Enlace')],
        default='',
        verbose_name='Botón 1',
    )
    boton_1_texto = models.CharField(max_length=25, blank=True, verbose_name='Texto botón 1')
    boton_1_url = models.CharField(
        max_length=2000,
        blank=True,
        verbose_name='URL botón 1',
        help_text='Si lleva variable, termina en {{1}}. Ej: https://app.eki.technology/c/{{1}}',
    )
    boton_1_ejemplo = models.CharField(max_length=200, blank=True, verbose_name='Ejemplo URL botón 1')
    boton_2_tipo = models.CharField(
        max_length=20,
        blank=True,
        choices=[('', 'Sin botón'), ('QUICK_REPLY', 'Respuesta rápida'), ('URL', 'Enlace')],
        default='',
        verbose_name='Botón 2',
    )
    boton_2_texto = models.CharField(max_length=25, blank=True, verbose_name='Texto botón 2')
    boton_2_url = models.CharField(max_length=2000, blank=True, verbose_name='URL botón 2')
    boton_2_ejemplo = models.CharField(max_length=200, blank=True, verbose_name='Ejemplo URL botón 2')

    meta_template_id = models.CharField(max_length=64, blank=True, default='', verbose_name='ID en Meta')
    waba_id = models.CharField(max_length=64, blank=True, default='', verbose_name='WABA')
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_PLANTILLA,
        default='BORRADOR',
        db_index=True,
        verbose_name='Estado',
    )
    rejected_reason = models.CharField(max_length=500, blank=True, default='', verbose_name='Motivo')
    ultimo_error_code = models.CharField(max_length=32, blank=True, default='', verbose_name='Código error')
    ultimo_error_mensaje = models.TextField(blank=True, default='', verbose_name='Error Meta')
    activa = models.BooleanField(default=True, verbose_name='Activa')
    enviada_en = models.DateTimeField(null=True, blank=True, verbose_name='Enviada a Meta')
    sincronizada_en = models.DateTimeField(null=True, blank=True, verbose_name='Última sync')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plantilla Meta'
        verbose_name_plural = 'Plantillas Meta'
        ordering = ['-fecha_creacion']
        constraints = [
            models.UniqueConstraint(fields=['meta_name', 'idioma'], name='uniq_plantilla_meta_nombre_idioma'),
        ]

    def __str__(self):
        return f'{self.nombre_interno} ({self.estado})'

    def save(self, *args, **kwargs):
        if not (self.meta_name or '').strip():
            self.meta_name = sanitizar_nombre_meta(self.nombre_interno)
        else:
            self.meta_name = sanitizar_nombre_meta(self.meta_name)
        super().save(*args, **kwargs)

    def clean(self):
        if self.categoria == 'AUTHENTICATION':
            raise ValidationError({
                'categoria': 'Autenticación (OTP) no está en este corte. Use Utilidad o Marketing.',
            })
        if not _NOMBRE_META_RE.match(sanitizar_nombre_meta(self.meta_name or self.nombre_interno)):
            raise ValidationError({
                'meta_name': 'Solo minúsculas, números y guion bajo.',
            })
        validar_variables_secuenciales(self.cuerpo, 'cuerpo')
        validar_variables_secuenciales(self.header_texto, 'header_texto')
        n_body = len(set(variables_en(self.cuerpo)))
        ejemplos = ejemplos_lista(self.ejemplos_cuerpo)
        if n_body and len(ejemplos) < n_body:
            raise ValidationError({
                'ejemplos_cuerpo': f'Hacen falta ejemplos: {n_body} variable(s), separados por |.',
            })
        if variables_en(self.header_texto) and not (self.header_ejemplo or '').strip():
            raise ValidationError({'header_ejemplo': 'El header con variable necesita un ejemplo.'})
        self._validar_boton(1)
        self._validar_boton(2)
        if len(self.cuerpo or '') > 1024:
            raise ValidationError({'cuerpo': 'El cuerpo supera 1024 caracteres.'})

    def _validar_boton(self, n: int) -> None:
        tipo = getattr(self, f'boton_{n}_tipo') or ''
        texto = (getattr(self, f'boton_{n}_texto') or '').strip()
        url = (getattr(self, f'boton_{n}_url') or '').strip()
        ejemplo = (getattr(self, f'boton_{n}_ejemplo') or '').strip()
        if not tipo:
            return
        if not texto:
            raise ValidationError({f'boton_{n}_texto': 'El botón necesita texto (máx. 25).'})
        if tipo == 'URL':
            if not url:
                raise ValidationError({f'boton_{n}_url': 'El botón de enlace necesita URL.'})
            if variables_en(url) and not ejemplo:
                raise ValidationError({f'boton_{n}_ejemplo': 'La URL con {{1}} necesita ejemplo.'})


class TarjetaPlantillaMeta(models.Model):
    """Tarjeta de un carrusel guardado en el admin. Mismos dos botones en cada una."""

    plantilla = models.ForeignKey(
        PlantillaMeta,
        on_delete=models.CASCADE,
        related_name='tarjetas',
    )
    orden = models.PositiveIntegerField(default=0)
    titulo = models.CharField(max_length=200)
    cuerpo = models.CharField(max_length=160)
    imagen_url = models.URLField(max_length=1000)
    boton_ver_id = models.CharField(max_length=64)
    boton_ver_texto = models.CharField(max_length=20, default='Ver curso')
    boton_info_id = models.CharField(max_length=64)
    boton_info_texto = models.CharField(max_length=20, default='Más información')
    info_url = models.URLField(max_length=2000, blank=True, default='')

    class Meta:
        verbose_name = 'Tarjeta de carrusel'
        verbose_name_plural = 'Tarjetas de carrusel'
        ordering = ['plantilla', 'orden', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['plantilla', 'orden'],
                name='uniq_tarjeta_plantilla_orden',
            ),
        ]

    def __str__(self):
        return f'{self.orden}. {self.titulo}'


def guardar_borrador_carrusel(nombre: str, claves: list[str]) -> PlantillaMeta:
    """Guarda el carrusel del día. No llama a Meta."""
    from core.cursos_generales import item_catalogo, texto_tarjeta, url_imagen_catalogo

    nombre = (nombre or '').strip()
    if not nombre:
        raise ValidationError('Escriba el nombre de la campaña.')
    items = []
    for clave in claves:
        item = item_catalogo(clave)
        if item is not None:
            items.append(item)
    if len(items) < 2:
        raise ValidationError('Elija al menos dos cursos.')
    plantilla = PlantillaMeta.objects.create(
        nombre_interno=nombre[:120],
        categoria='MARKETING',
        idioma='es',
        tipo='CARRUSEL',
        cuerpo='Deslice los cursos de eki. Ver curso inscribe. Más información manda la ficha.',
        estado='BORRADOR',
    )
    for orden, item in enumerate(items):
        TarjetaPlantillaMeta.objects.create(
            plantilla=plantilla,
            orden=orden,
            titulo=(item['nombre'] or '')[:200],
            cuerpo=texto_tarjeta(item)[:160],
            imagen_url=url_imagen_catalogo(item['imagen'])[:1000],
            boton_ver_id=f"ver_{item['clave']}"[:64],
            boton_ver_texto='Ver curso',
            boton_info_id=f"info_{item['clave']}"[:64],
            boton_info_texto='Más información',
            info_url=(item.get('url') or '')[:2000],
        )
    return plantilla


class CampanaMeta(models.Model):
    """Lanzamiento que envía una PlantillaMeta por Cloud API (no por Twilio)."""

    nombre = models.CharField(max_length=120)
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campanas_meta',
        verbose_name='Cliente',
    )
    plantilla = models.ForeignKey(
        PlantillaMeta,
        on_delete=models.PROTECT,
        related_name='campanas',
        verbose_name='Plantilla Meta',
        help_text='Tiene que estar Aprobada para poder enviarla.',
    )
    mapeo_header = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Variables del header',
        help_text='Si el header tiene {{1}}: nombre, telefono, o un texto fijo. Varias, separadas por |.',
    )
    mapeo_body = models.CharField(
        max_length=300,
        blank=True,
        default='nombre',
        verbose_name='Variables del cuerpo',
        help_text='Una por cada {{n}}, separadas por |. nombre y telefono salen del estudiante; el resto es texto fijo.',
    )
    mapeo_boton = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Variable del botón URL',
        help_text='Si algún botón URL lleva {{1}}. Misma regla: nombre, telefono o texto fijo.',
    )
    phone_number_id = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Phone number ID',
        help_text='Vacío usa WHATSAPP_PHONE_ID (línea Cloud API). No es el número de Twilio.',
    )
    grupo = models.ForeignKey(
        'GrupoEstudiantes',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campanas_meta',
        verbose_name='Grupo',
    )
    destinatarios = models.ManyToManyField(
        'Estudiante',
        blank=True,
        related_name='campanas_meta',
        verbose_name='Destinatarios',
    )
    ejecutada = models.BooleanField(default=False, verbose_name='Ejecutada')
    total_enviados = models.IntegerField(default=0, verbose_name='Enviados')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Campaña Meta'
        verbose_name_plural = 'Campañas Meta'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.nombre


class EnvioCampanaMeta(models.Model):
    ESTADO = [
        ('ENVIADO', 'Enviado'),
        ('FALLIDO', 'Fallido'),
    ]

    campana = models.ForeignKey(CampanaMeta, on_delete=models.CASCADE, related_name='envios')
    estudiante = models.ForeignKey('Estudiante', on_delete=models.CASCADE, related_name='envios_campana_meta')
    estado = models.CharField(max_length=20, choices=ESTADO, default='FALLIDO')
    wamid = models.CharField(max_length=200, blank=True, default='')
    respuesta = models.TextField(blank=True, default='')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Envío campaña Meta'
        verbose_name_plural = 'Envíos campaña Meta'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.campana_id} {self.estudiante_id} {self.estado}'
