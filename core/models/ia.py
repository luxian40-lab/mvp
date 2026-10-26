"""Modelos de ia (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.models.clientes import Cliente
from core.models.mensajeria import SesionComercial
from core.models.conocimiento import DocumentoRAGComercial


class EventoIA(models.Model):
    """Trazabilidad persistente de decisiones IA, checkpoints y RAG (Parte 2A)."""

    TIPO_MODULO_COMPLETADO = 'modulo_completado'
    TIPO_CHECKPOINT_EVALUADO = 'checkpoint_evaluado'
    TIPO_IA_AGENT_TRIGGERED = 'ia_agent_triggered'
    TIPO_RAG_QUERY_EXECUTED = 'rag_query_executed'
    TIPO_WEBHOOK_RECIBIDO = 'webhook_recibido'
    TIPO_INTENT_DETECTADO = 'intent_detectado'
    TIPO_MENSAJE_ENVIADO = 'mensaje_enviado'

    TIPO_CHOICES = [
        (TIPO_MODULO_COMPLETADO, 'Módulo completado'),
        (TIPO_CHECKPOINT_EVALUADO, 'Checkpoint evaluado'),
        (TIPO_IA_AGENT_TRIGGERED, 'Agente IA activado'),
        (TIPO_RAG_QUERY_EXECUTED, 'Consulta RAG'),
        (TIPO_WEBHOOK_RECIBIDO, 'Webhook recibido'),
        (TIPO_INTENT_DETECTADO, 'Intent detectado'),
        (TIPO_MENSAJE_ENVIADO, 'Mensaje enviado'),
    ]

    CANAL_WHATSAPP_EDU = 'whatsapp_edu'
    CANAL_WHATSAPP_COMERCIAL = 'whatsapp_comercial'
    CANAL_ADMIN = 'admin'

    trace_id = models.UUIDField(db_index=True, verbose_name='Trace ID')
    tipo = models.CharField(max_length=40, choices=TIPO_CHOICES, db_index=True)

    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )
    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_ia',
    )

    agente = models.CharField(max_length=60, blank=True, default='')
    canal = models.CharField(max_length=30, default=CANAL_WHATSAPP_EDU, db_index=True)

    facilitador_checkpoint = models.CharField(max_length=10, blank=True, default='')
    regla_aplicada = models.CharField(max_length=60, blank=True, default='', db_index=True)
    es_reto = models.BooleanField(null=True, blank=True)

    modelo = models.CharField(max_length=60, blank=True, default='')
    latencia_ms = models.PositiveIntegerField(null=True, blank=True)
    tokens_in = models.PositiveIntegerField(null=True, blank=True)
    tokens_out = models.PositiveIntegerField(null=True, blank=True)

    input_preview = models.TextField(blank=True, default='')
    output_preview = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Evento IA'
        verbose_name_plural = 'Eventos IA'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'tipo']),
            models.Index(fields=['trace_id', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} · {self.trace_id} · {self.created_at:%Y-%m-%d %H:%M}'


class ContextoAgroSession(models.Model):
    """Contexto agronómico estructurado por sesión Nat (Parte 3)."""

    sesion = models.OneToOneField(
        SesionComercial,
        on_delete=models.CASCADE,
        related_name='contexto_agro',
        verbose_name='Sesión comercial',
    )
    cultivo = models.CharField(max_length=80, blank=True, default='')
    etapa = models.CharField(max_length=80, blank=True, default='', help_text='Ej: floración, desarrollo')
    region = models.CharField(max_length=120, blank=True, default='', help_text='Departamento o zona')
    municipio = models.CharField(max_length=80, blank=True, default='')
    vereda = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Vereda, localidad o zona más exacta dentro del municipio',
    )
    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Latitud geocodificada (Open-Meteo u otra fuente)',
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Longitud geocodificada (Open-Meteo u otra fuente)',
    )
    clima = models.CharField(max_length=80, blank=True, default='', help_text='Ej: alta humedad, sequía')
    problema = models.CharField(max_length=200, blank=True, default='', help_text='Plaga, enfermedad, nutrición')
    notas = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contexto agronómico (Nat)'
        verbose_name_plural = 'Contextos agronómicos (Nat)'

    def campos_llenos(self) -> list[str]:
        out = []
        for k in ('cultivo', 'etapa', 'region', 'municipio', 'clima', 'problema'):
            if (getattr(self, k, '') or '').strip():
                out.append(k)
        return out

    def completitud_pct(self) -> int:
        total = 6
        return int(len(self.campos_llenos()) * 100 / total) if total else 0

    def to_dict(self) -> dict:
        return {
            'cultivo': self.cultivo,
            'etapa': self.etapa,
            'region': self.region,
            'municipio': self.municipio,
            'vereda': self.vereda,
            'latitud': float(self.latitud) if self.latitud is not None else None,
            'longitud': float(self.longitud) if self.longitud is not None else None,
            'clima': self.clima,
            'problema': self.problema,
            'completitud_pct': self.completitud_pct(),
        }

    def __str__(self):
        parts = [p for p in (self.cultivo, self.problema, self.region) if p]
        return ' · '.join(parts) if parts else f'Contexto sesión {self.sesion_id}'


class ConversacionRAGCandidata(models.Model):
    """Cola HITL: conversación Nat candidata a publicarse como conocimiento validado (Parte 4)."""

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_APROBADA = 'aprobada'
    ESTADO_RECHAZADA = 'rechazada'
    ESTADO_PUBLICADA = 'publicada'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente revisión'),
        (ESTADO_APROBADA, 'Aprobada (sin publicar)'),
        (ESTADO_RECHAZADA, 'Rechazada'),
        (ESTADO_PUBLICADA, 'Publicada en RAG'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_rag',
    )
    sesion = models.ForeignKey(
        SesionComercial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_rag',
    )
    telefono = models.CharField(max_length=30, db_index=True)
    trace_id = models.UUIDField(null=True, blank=True, db_index=True)
    pregunta = models.TextField()
    respuesta_nati = models.TextField()
    respuesta_revisada = models.TextField(blank=True, default='')
    contexto_agro = models.JSONField(default=dict, blank=True)
    chunks_rag = models.JSONField(default=list, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE, db_index=True)
    revisado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_rag_revisadas',
    )
    notas_revisor = models.TextField(blank=True, default='')
    agentes = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Aplica a',
        help_text='Agentes que pueden usar esta respuesta.',
    )
    alcance = models.CharField(
        max_length=16,
        choices=[('todos', 'Todos'), ('cliente', 'Un cliente')],
        default='todos',
        verbose_name='Alcance',
    )
    documento_rag = models.ForeignKey(
        DocumentoRAGComercial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatas_origen',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Candidata RAG (HITL)'
        verbose_name_plural = 'Candidatas RAG (HITL)'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.get_estado_display()} · {self.pregunta[:60]}'
