"""Modelos de canal (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.models.opciones import PLAN_CHOICES as PLAN_LINEA_CHOICES


class SandboxCanalSesion(models.Model):
    """Modo sticky del menú sandbox (Nat|agentes|cursos) — solo número Twilio sandbox."""

    MODO_MENU = 'menu'
    MODO_AGENTES = 'agentes'
    MODO_NAT = 'nat'
    MODO_COACH = 'coach'
    MODO_IA_CAMPO = 'ia_campo'
    MODO_VENTAS = 'ventas'
    MODO_CURSOS = 'cursos'
    MODO_CHOICES = [
        (MODO_MENU, 'Menú'),
        (MODO_AGENTES, 'Submenú agentes'),
        (MODO_NAT, 'Agrónomo (Nat)'),
        (MODO_COACH, 'Coach'),
        (MODO_IA_CAMPO, 'IA para el campo'),
        (MODO_VENTAS, 'Ventas y comercialización'),
        ('finanzas', 'Experto en finanzas'),
        ('cafe', 'Experto en café'),
        (MODO_CURSOS, 'Cursos'),
        ('formacion', 'Formación'),
        ('asesoria', 'Asesoría'),
    ]

    telefono = models.CharField(max_length=30, db_index=True)
    phone_id = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Línea Meta',
        help_text='Phone number id de la línea. Vacío = sesión anterior a las dos líneas.',
    )
    modo = models.CharField(max_length=16, choices=MODO_CHOICES, default=MODO_MENU)
    # Historial Nat/BOT_COMERCIAL solo cuenta mensajes posteriores a este corte.
    memoria_corte_en = models.DateTimeField(null=True, blank=True)
    habeas_aceptado = models.BooleanField(
        default=False,
        help_text='Aceptó tratamiento de datos en la línea Meta antes del menú.',
    )
    plan = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=PLAN_LINEA_CHOICES,
        verbose_name='Plan (solo esta persona)',
        help_text='Vacío = usa el plan de su grupo y, si el grupo no tiene, el de su organización.',
    )
    preguntas_mes = models.PositiveIntegerField(default=0, verbose_name='Preguntas al asesor (mes)')
    preguntas_mes_desde = models.DateField(
        null=True,
        blank=True,
        help_text='Primer día del mes al que corresponde el contador de preguntas.',
    )
    racha_actual = models.PositiveIntegerField(default=0, verbose_name='Racha (días seguidos)')
    racha_maxima = models.PositiveIntegerField(default=0, verbose_name='Récord de racha')
    racha_ultimo_dia = models.DateField(null=True, blank=True, verbose_name='Último día activo')
    aviso_pendiente = models.CharField(
        max_length=300,
        blank=True,
        default='',
        help_text='Línea de racha/insignia que va al inicio del próximo mensaje del día.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sesión menú sandbox'
        verbose_name_plural = 'Sesiones menú sandbox'
        constraints = [
            models.UniqueConstraint(
                fields=('telefono', 'phone_id'),
                name='uniq_sandbox_sesion_tel_linea',
            ),
        ]

    def __str__(self):
        return f'{self.telefono} → {self.modo}'


class EventOutbox(models.Model):
    """Outbox transaccional hacia Data Lake raw (Event Engine v0)."""

    event_id = models.UUIDField(unique=True, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    schema_version = models.PositiveSmallIntegerField(default=1)
    occurred_at = models.DateTimeField(db_index=True)
    ingested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    org_id = models.IntegerField(null=True, blank=True, db_index=True)
    territory_id = models.CharField(max_length=32, blank=True, default='', db_index=True)
    actor_pseudo = models.CharField(max_length=64, blank=True, default='')
    session_or_trace_id = models.CharField(max_length=64, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    correlation_ids = models.JSONField(default=list, blank=True)
    pii_class = models.CharField(max_length=32, default='internal')
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    lake_uri = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        verbose_name = 'Evento outbox'
        verbose_name_plural = 'Eventos outbox'
        ordering = ['-ingested_at']
        indexes = [
            models.Index(fields=['published_at', 'id']),
            models.Index(fields=['event_type', '-occurred_at']),
        ]

    def __str__(self):
        return f'{self.event_type} ({self.event_id})'
