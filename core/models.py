from django.db import models
from django.db.models import Q
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import re
import openpyxl # <--- Nueva librería
import os
from django.db import IntegrityError

# 0. TEMA DE CAMPAÑA (para organizar plantillas y campañas)
class TemaCampana(models.Model):
    """Temas/etiquetas para organizar plantillas y campañas (ej: café, aguacate, maíz)"""
    nombre = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Nombre del tema",
        help_text="Ej: Café, Aguacate, Maíz, Motivación General"
    )
    emoji = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Emoji",
        help_text="Copia y pega uno: ☕ 🥑 🌽 🍌 🍊 🍇 🥔 🥕 🧅 🌶️ 🫘 🥬 🍅 🥒 🥦 🐄 🐔 🐷 🐑 🌱 🌾 🌳 🚜 💧 🌤️"
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción",
        help_text="Descripción opcional del tema"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está desactivado, no aparecerá en las opciones"
    )
    
    class Meta:
        verbose_name = 'Tema de Campaña'
        verbose_name_plural = 'Temas de Campaña'
        ordering = ['nombre']
    
    def __str__(self):
        if self.emoji:
            return f"{self.emoji} {self.nombre}"
        return self.nombre


# 0b. CLIENTE (Organización/Empresa que usa la plataforma)
class Cliente(models.Model):
    """Cliente/Organización que usa la plataforma (cooperativa, empresa, ONG)"""
    TIPO_PROYECTO_CHOICES = [
        ('cursos', 'Cursos eki'),
        ('gei', 'Inventario GEI'),
        ('nat', 'Agente Nat'),
    ]

    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del Cliente",
        help_text="Ej: Cooperativa Cafetera del Valle, Fundación Agrícola"
    )
    nit = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="NIT/RUT",
        help_text="Número de identificación tributaria"
    )
    contacto_principal = models.CharField(
        max_length=100,
        verbose_name="Contacto Principal",
        help_text="Nombre de la persona de contacto"
    )
    email = models.EmailField(
        verbose_name="Email",
        help_text="Email de contacto del cliente"
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono"
    )
    numero_whatsapp_autorizado = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Número WhatsApp Autorizado en Meta",
        help_text="Número autorizado en Meta Business para envío masivo (ej: 573001234567)"
    )
    enviar_certificados_email = models.BooleanField(
        default=True,
        verbose_name="Enviar Certificados por Email",
        help_text="Si está activado, se enviarán los certificados de sus estudiantes al email del cliente"
    )
    enlace_grupo_whatsapp = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Enlace de Grupo de WhatsApp",
        help_text="Enlace de invitación al grupo de WhatsApp del cliente (ej: https://chat.whatsapp.com/xxxxx)"
    )
    enlace_habeas_data = models.URLField(
        max_length=700,
        blank=True,
        verbose_name="Enlace Habeas Data (override)",
        help_text="Opcional: URL de política de datos propia del cliente. Si se deja vacío, se usa la URL general de eki."
    )
    content_sid_habeas_data_twilio = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Habeas Data Template (Twilio Content SID por cliente)',
        help_text=(
            'Opcional: Content SID (HX...) del template de Habeas Data para ESTE cliente. '
            'Si se deja vacío, el sistema usa el template global de eki configurado en '
            '"Configuración Global".'
        ),
    )
    usar_gamificacion = models.BooleanField(
        default=True,
        verbose_name="Usar Gamificación",
        help_text="Sincronizado automáticamente desde «Modo de gamificación». Legacy para compatibilidad."
    )
    modo_gamificacion = models.CharField(
        max_length=20,
        choices=[
            ('desactivado', 'Desactivada'),
            ('puntos', 'Puntos (ranking y recompensas)'),
            ('calificacion', 'Calificación 1–5 (ranking por promedio)'),
        ],
        default='puntos',
        verbose_name='Modo de gamificación',
        help_text=(
            'Puntos: ranking por puntos acumulados (actual). '
            'Calificación 1–5: gamificación por notas (promedio ponderado para ranking; ej. 3,5). '
            'Desactivada: sin gamificación visible.'
        ),
    )
    modo_avance_modulo = models.CharField(
        max_length=20,
        choices=[
            ('texto', 'Solo escribir listo / continuar'),
            ('boton', 'Solo botón WhatsApp (plantilla)'),
            ('ambos', 'Texto y botón'),
        ],
        default='texto',
        verbose_name='Avance entre módulos',
        help_text=(
            'Texto = escribir listo (default). Botón = plantilla Twilio al cerrar entrega del módulo. '
            'No aplica en onboarding, PQRS ni conversación con agentes IA.'
        ),
    )
    content_sid_boton_listo = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Plantilla botón Listo (Twilio)',
        help_text='Content SID (HX…) con quick reply «Listo». Vacío = plantilla global continuar_modulo.',
    )
    peso_gamificacion_reto = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1,
        verbose_name='Peso de notas — reto',
        help_text='Peso en el promedio ponderado del ranking (modo calificación).',
    )
    peso_gamificacion_abierta = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1,
        verbose_name='Peso de notas — pregunta abierta',
        help_text='Peso en el promedio ponderado del ranking (modo calificación).',
    )
    exigir_nota_minima_certificado = models.BooleanField(
        default=False,
        verbose_name='Exigir nota mínima para certificado',
        help_text=(
            'Opcional. Solo aplica en modo «Calificación 1–5». Si el promedio ponderado '
            'es menor a la nota mínima, no se emite certificado.'
        ),
    )
    nota_minima_certificado = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=3,
        verbose_name='Nota mínima certificado (1–5)',
        help_text='Umbral de aprobación (ej. 3 o 3.5). Por debajo: curso completado sin certificado.',
    )
    drip_modulos_solo_estudiantes_listados = models.BooleanField(
        default=False,
        verbose_name='Módulos solo por lista de estudiantes',
        help_text=(
            'Si está activo, cada módulo solo es accesible para estudiantes con '
            '«Habilitación de módulo (estudiante)» en el admin. El drip general del cliente sigue '
            'aplicando fechas; la lista define quién puede entrar.'
        ),
    )
    habilitar_pregunta_abierta_final = models.BooleanField(
        default=False,
        verbose_name='Habilitar Pregunta Abierta Final',
        help_text='Activa la pregunta abierta final para este cliente según la ventana de fechas.'
    )
    fecha_inicio_pregunta_abierta_final = models.DateField(
        null=True,
        blank=True,
        verbose_name='Inicio Pregunta Abierta Final',
        help_text='Fecha desde la cual se activa la pregunta abierta final para este cliente.'
    )
    fecha_fin_pregunta_abierta_final = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fin Pregunta Abierta Final',
        help_text='Fecha límite de activación de la pregunta abierta final para este cliente.'
    )
    habilitar_gamificacion_proximidad = models.BooleanField(
        default=False,
        verbose_name='Habilitar Gamificación por Proximidad',
        help_text='Activa radar de empleabilidad por proximidad para este cliente según la ventana de fechas.'
    )
    fecha_inicio_gamificacion_proximidad = models.DateField(
        null=True,
        blank=True,
        verbose_name='Inicio Gamificación Proximidad',
        help_text='Fecha desde la cual se activa el radar de proximidad para este cliente.'
    )
    fecha_fin_gamificacion_proximidad = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fin Gamificación Proximidad',
        help_text='Fecha límite de activación del radar de proximidad para este cliente.'
    )
    empleabilidad_exploracion_activa = models.BooleanField(
        default=False,
        verbose_name='Empleabilidad Exploración Activa',
        help_text='Activa la experiencia tipo exploración para oportunidades cercanas (por cliente).'
    )
    empleabilidad_radio_metros = models.PositiveIntegerField(
        default=800,
        verbose_name='Radio de búsqueda (metros)',
        help_text='Distancia máxima para detectar oportunidades cercanas.'
    )
    empleabilidad_cooldown_horas = models.PositiveIntegerField(
        default=24,
        verbose_name='Cooldown entre validaciones (horas)',
        help_text='Horas mínimas entre validaciones exitosas de empleabilidad por estudiante.'
    )
    empleabilidad_max_misiones_dia = models.PositiveIntegerField(
        default=3,
        verbose_name='Máximo misiones por día',
        help_text='Límite diario de misiones de exploración por estudiante.'
    )
    empleabilidad_puntos_validacion = models.PositiveIntegerField(
        default=30,
        verbose_name='Puntos por validación',
        help_text='Puntos de gamificación otorgados al validar un código de oportunidad.'
    )
    # NOMBRES PERSONALIZADOS DE AGENTES IA (por Cliente)
    nombre_agente_tutor = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Nombre del Profesor (Tutor IA)',
        help_text='Nombre personalizado para el agente tutor/profesor (por defecto: Gerónimo). Ej: Carlos, Sofía'
    )
    nombre_agente_asistente = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Nombre de la Asistente (IA)',
        help_text='Nombre personalizado para la agente asistente (por defecto: María). Ej: Laura, Andrea'
    )
    # BOT COMERCIAL (Nat) — identidad y prompt extra editable desde admin
    nombre_bot = models.CharField(
        max_length=40,
        blank=True,
        default='Nati',
        verbose_name='Nombre del Bot Comercial',
        help_text='Nombre con el que se presenta el bot comercial al productor (default en código: Nat). Ej: Nat, Aliada, Sofi.'
    )
    system_prompt_extra = models.TextField(
        blank=True,
        default='',
        verbose_name='Instrucciones extra para el Bot Comercial',
        help_text='Instrucciones específicas de este cliente que se concatenan al system prompt de Nat. Útil para tono, productos prioritarios o restricciones por marca.'
    )
    numero_whatsapp_nat = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name='Número WhatsApp Nat (línea comercial)',
        help_text=(
            'Número Twilio al que escribe el productor para hablar con Nat (solo dígitos, ej: 573001234567). '
            'Cada organización puede tener su propia línea; el webhook identifica el cliente por este número (campo To). '
            'Distinto del número de campañas educativas y del BOT_COMERCIAL_CLIENTE_ID global.'
        ),
    )
    tipo_proyecto = models.CharField(
        max_length=20,
        choices=TIPO_PROYECTO_CHOICES,
        default='cursos',
        verbose_name='Tipo de producto principal',
        help_text='Producto principal del contrato. Para combinar varios módulos en el portal, use «Módulos del portal».',
    )
    portal_productos = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Módulos del portal',
        help_text=(
            'Opcional. Lista separada por coma: cursos, gei, nat, empleabilidad. '
            'Ej: cursos,empleabilidad o cursos,gei,nat. Vacío = solo el tipo principal.'
        ),
    )
    fecha_inicio_suscripcion = models.DateField(
        null=True,
        blank=True,
        verbose_name='Inicio de suscripción',
    )
    fecha_fin_suscripcion = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fin de suscripción',
    )
    logo_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Logo (portal)',
        help_text='URL pública del logo de la organización. Visible en el portal B2B.',
    )
    portal_subtitulo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Subtítulo en portal',
        help_text='Texto corto bajo el nombre en el portal (ej: Cooperativa del Valle — 2026).',
    )
    cupos_portal = models.PositiveIntegerField(
        default=5,
        verbose_name='Cupos de usuarios portal',
        help_text=(
            'Máximo de usuarios del portal B2B para esta organización. '
            'Solo eki (Django admin) puede crearlos; el cliente no invita usuarios.'
        ),
    )
    gei_factores_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Factores GEI personalizados',
        help_text='Overrides de factores de emisión (portal). Claves válidas = FACTORES en formulario.calculadora.',
    )
    whatsapp_numero = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='WhatsApp propio del cliente',
        help_text='Número WhatsApp del cliente para multi-tenant futuro.',
    )
    twilio_account_sid = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='Twilio Account SID propio',
    )
    twilio_auth_token = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name='Twilio Auth Token propio',
    )
    twilio_whatsapp_from = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='Twilio WhatsApp From propio',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está inactivo, sus estudiantes no recibirán mensajes"
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name="Notas Internas",
        help_text="Notas para uso interno de eki (no visibles para el cliente)"
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro"
    )
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes (Organizaciones)'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        from core.gamificacion_modo import sincronizar_usar_gamificacion

        sincronizar_usar_gamificacion(self)
        super().save(*args, **kwargs)

    @property
    def suscripcion_activa(self):
        from datetime import date

        if not self.fecha_fin_suscripcion:
            return self.activo
        return self.activo and date.today() <= self.fecha_fin_suscripcion
    
    def total_estudiantes(self):
        """Retorna total de estudiantes activos del cliente"""
        return self.estudiantes.filter(activo=True).count()
    
    def total_cursos(self):
        """Retorna total de cursos asignados al cliente"""
        return self.cursos.count()


class MetaMetricaEmpresa(models.Model):
    """Metas configurables por organización (educación B2B)."""

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="metas_metricas",
        verbose_name="Organización",
    )
    curso = models.ForeignKey(
        "Curso",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="metas_metricas",
        verbose_name="Curso",
        help_text="Vacío = meta general del cliente para todos los cursos.",
    )
    meta_finalizacion_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=70
    )
    meta_inicio_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=80
    )
    meta_max_no_iniciados_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=20
    )
    meta_min_lectura_mensajes_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=60
    )
    verde_desde = models.DecimalField(max_digits=5, decimal_places=2, default=80)
    amarillo_desde = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meta métrica empresa"
        verbose_name_plural = "Metas métricas por empresa"
        constraints = [
            models.UniqueConstraint(
                fields=["cliente", "curso"],
                name="uniq_meta_metrica_cliente_curso",
                condition=Q(curso__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["cliente"],
                name="uniq_meta_metrica_cliente_general",
                condition=Q(curso__isnull=True),
            ),
        ]

    def __str__(self):
        curso = self.curso.nombre if self.curso_id else "General"
        return f"{self.cliente.nombre} — {curso}"


class MetaMetricaNati(models.Model):
    """Metas del bot comercial Nat por organización."""

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="metas_nati",
        verbose_name="Organización",
    )
    meta_lectura_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=60,
        verbose_name="Meta lectura WhatsApp (%)",
    )
    meta_respuesta_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=70,
        verbose_name="Meta respuesta a consultas (%)",
    )
    verde_desde = models.DecimalField(max_digits=5, decimal_places=2, default=80)
    amarillo_desde = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meta métrica Nat"
        verbose_name_plural = "Metas métricas Nat"

    def __str__(self):
        return f"Nat — {self.cliente.nombre}"


# 1. ESTUDIANTE
class Estudiante(models.Model):
    TIPO_DOCUMENTO_CHOICES = [
        ('CC', 'Cédula de Ciudadanía'),
        ('TI', 'Tarjeta de Identidad'),
        ('CE', 'Cédula de Extranjería'),
        ('PP', 'Pasaporte'),
    ]
    
    RANGO_EDAD_CHOICES = [
        ('18-30', '18 a 30 años'),
        ('31-50', '31 a 50 años'),
        ('50+', 'Mayor de 50 años'),
    ]
    
    # === ESTADOS DEL CHAT (Máquina de Estados B2B) ===
    ESTADO_CHAT_CHOICES = [
        ('ESPERANDO_HABEAS_DATA', 'Esperando Habeas Data'),
        ('ESPERANDO_CEDULA', 'Esperando Cédula (2FA)'),
        ('CONFIRMANDO_DATOS', 'Confirmando Datos'),
        ('ESPERANDO_AYUDA_MODIFICAR', 'Esperando Ayuda Modificar Datos'),
        ('ESPERANDO_CORRECCION_DATOS', 'Esperando Corrección Datos'),
        ('ACTIVO', 'Activo'),
        # Estados legacy del onboarding anterior
        ('nuevo', 'Nuevo (legacy)'),
        ('esperando_tipo_doc', 'Esperando tipo doc (legacy)'),
        ('esperando_cedula_legacy', 'Esperando cédula (legacy)'),
        ('esperando_nombre', 'Esperando nombre (legacy)'),
        ('esperando_respuesta_modulo', 'Esperando respuesta módulo'),
        ('esperando_respuesta_tutor_ia', 'Esperando respuesta tutor IA'),
        ('esperando_respuesta_progreso', 'Esperando respuesta progreso'),
        ('esperando_seleccion_curso', 'Esperando selección curso'),
        ('esperando_respuesta_asistente', 'Esperando respuesta asistente Darío'),
        ('esperando_respuesta_reto', 'Esperando respuesta reto facilitador'),
        ('esperando_codigo_empleabilidad', 'Esperando código de empleabilidad'),
        ('esperando_respuesta_pregunta_abierta_final', 'Esperando respuesta pregunta abierta final'),
        ('curso_finalizado', 'Curso finalizado (sin interacción)'),
        ('completado', 'Completado (legacy)'),
    ]
    
    tipo_documento = models.CharField(
        max_length=2,
        choices=TIPO_DOCUMENTO_CHOICES,
        default='CC',
        verbose_name='Tipo de Documento',
        help_text='Tipo de documento de identificación'
    )
    cedula = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número de Documento',
        help_text='Número de identificación único (limpio, sin puntos ni espacios)'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre Completo')
    telefono = models.CharField(max_length=20, unique=True, verbose_name='Teléfono WhatsApp')
    
    # UBICACIÓN GEOGRÁFICA
    municipio = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Municipio',
        help_text='Municipio donde reside el estudiante'
    )
    departamento = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Departamento',
        help_text='Departamento de Colombia (Ej: Antioquia, Cundinamarca)'
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Región',
        help_text='Región geográfica (Ej: Zona Norte, Magdalena Medio)'
    )
    ubicacion_detalle = models.TextField(
        blank=True,
        verbose_name='Ubicación Detalle',
        help_text='Vereda, barrio o información adicional de ubicación'
    )
    
    # DATOS DEMOGRÁFICOS
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
        ('NR', 'No Reporta'),
    ]
    genero = models.CharField(
        max_length=2,
        choices=GENERO_CHOICES,
        blank=True,
        default='',
        verbose_name='Género',
        help_text='Género del estudiante'
    )
    edad = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Edad',
        help_text='Edad del estudiante en años'
    )
    rango_edad = models.CharField(
        max_length=10,
        choices=RANGO_EDAD_CHOICES,
        blank=True,
        verbose_name='Rango de Edad',
        help_text='Rango de edad del estudiante (se calcula automáticamente si se proporciona edad)'
    )
    
    # ORGANIZACIÓN (Multi-tenant B2B)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='estudiantes',
        verbose_name='Organización',
        help_text='Organización/Empresa B2B a la que pertenece este estudiante'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    foto_perfil = models.ImageField(
        upload_to='estudiantes/avatars/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Foto de perfil',
        help_text='Avatar del estudiante (aula web y reportes).',
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    
    # HABEAS DATA - Proteccion de datos personales (Ley 1581 de 2012 - Colombia)
    acepto_terminos = models.BooleanField(
        default=False,
        verbose_name='Aceptó Términos y Condiciones',
        help_text='Indica si el estudiante aceptó la política de tratamiento de datos'
    )
    fecha_aceptacion_terminos = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Aceptación',
        help_text='Fecha y hora en que aceptó los términos'
    )
    
    # MÁQUINA DE ESTADOS B2B (estado_chat reemplaza estado_onboarding)
    estado_chat = models.CharField(
        max_length=50,
        choices=ESTADO_CHAT_CHOICES,
        default='ESPERANDO_HABEAS_DATA',
        verbose_name='Estado del Chat',
        help_text='Estado actual en la máquina de estados B2B del onboarding'
    )
    
    # ONBOARDING LEGACY - mantener para retrocompatibilidad
    estado_onboarding = models.CharField(
        max_length=50,
        default='nuevo',
        verbose_name='Estado Onboarding (Legacy)',
        help_text='nuevo, esperando_tipo_doc, esperando_cedula, esperando_nombre, esperando_respuesta_modulo, completado'
    )
    
    # ANTI-ABUSO IA
    preguntas_ia_restantes = models.IntegerField(
        default=3,
        verbose_name='Preguntas IA Restantes',
        help_text='Máximo de preguntas libres a la IA por módulo (se resetea al completar módulo)'
    )
    
    # CONTEXTO TEMPORAL - Para preguntas de modulo
    contexto_temporal = models.JSONField(
        null=True,
        blank=True,
        help_text='Guarda el módulo_id y pregunta_id actual cuando está respondiendo mini examen'
    )

    @property
    def organizacion(self):
        """Alias para acceder al cliente como 'organizacion' (B2B)"""
        return self.cliente
    
    @organizacion.setter
    def organizacion(self, value):
        self.cliente = value

    def clean(self):
        # Limpieza de teléfono
        numero = re.sub(r'\D', '', str(self.telefono))
        if len(numero) == 10: numero = f"57{numero}"
        
        # Validación
        if not (10 <= len(numero) <= 15):
            pass 
        self.telefono = numero
        
        # Limpieza de cédula (sanitización B2B)
        if self.cedula and not self.cedula.startswith('TEMP_'):
            self.cedula = re.sub(r'[\s\.\-]', '', str(self.cedula))
        
        # Capitalizar nombre
        if self.nombre and self.nombre != 'Usuario':
            self.nombre = self.nombre.strip().title()
        
        # Auto-calcular rango_edad si se proporciona edad
        if self.edad:
            if self.edad < 18:
                self.rango_edad = '18-30'  # Menores se agrupan en el primer rango
            elif 18 <= self.edad <= 30:
                self.rango_edad = '18-30'
            elif 31 <= self.edad <= 50:
                self.rango_edad = '31-50'
            else:
                self.rango_edad = '50+'

    def save(self, *args, **kwargs):
        self.clean() # Forzamos limpieza antes de guardar
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['cedula']),
            models.Index(fields=['telefono']),
        ]

    def __str__(self): 
        return f"{self.nombre} (CC: {self.cedula})"

# 2. PLANTILLA
class Plantilla(models.Model):
    """Plantillas de mensajes personalizables para campañas"""

    CATEGORIA_CHOICES = [
        ('cultivos', 'Cultivos'),
        ('ganaderia', 'Ganadería'),
        ('general_agricola', 'General Agrícola'),
        ('educacion', 'Educación'),
        ('gestion', 'Gestión'),
        ('otro', 'Otro'),
    ]

    nombre_interno = models.CharField(
        max_length=100,
        verbose_name="Nombre de la plantilla",
        help_text="Nombre interno para identificar la plantilla (ej: 'Recordatorio Riego Café')"
    )

    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='cultivos',
        verbose_name="Categoría",
        help_text="Categoría principal de la plantilla"
    )

    emoji = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Emoji",
        help_text="Emoji que representa esta plantilla (se autocompletará según la categoría)"
    )

    cuerpo_mensaje = models.TextField(
        verbose_name="Mensaje",
        help_text="Contenido del mensaje. Usa {nombre} para personalizar con el nombre del estudiante."
    )

    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si está desactivada, no aparecerá en las opciones de campaña"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_modificacion = models.DateTimeField(auto_now=True, null=True, blank=True)

    veces_usada = models.IntegerField(
        default=0,
        verbose_name="Veces usada",
        help_text="Contador automático de veces que se ha usado"
    )
    
    # ==========================================
    # 🔵 TWILIO CONTENT TEMPLATES
    # ==========================================
    twilio_template_sid = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Twilio Content SID",
        help_text="Content SID de Twilio (ej: HX1234...). Obtén esto desde Twilio Console después de crear tu plantilla aprobada."
    )
    twilio_template_nombre = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nombre en Twilio",
        help_text="Nombre de la plantilla en Twilio Console (para referencia)"
    )
    aprobada_twilio = models.BooleanField(
        default=False,
        verbose_name="Aprobada en Twilio",
        help_text="Marca esto cuando tu plantilla esté aprobada en Twilio Console"
    )
    
    # ==========================================
    # Meta WhatsApp (Deprecated - Usando solo Twilio)
    # ==========================================
    meta_template_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="[Deprecated] ID de Plantilla en Meta",
        help_text="No usar - Solo Twilio"
    )
    meta_template_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ('PENDING', 'Pendiente de Revisión'),
            ('APPROVED', 'Aprobada'),
            ('REJECTED', 'Rechazada'),
            ('DISABLED', 'Deshabilitada'),
        ],
        verbose_name="[Deprecated] Estado en Meta",
        help_text="No usar - Solo Twilio"
    )
    meta_template_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="[Deprecated] Nombre en Meta",
        help_text="No usar - Solo Twilio"
    )
    enviada_a_meta = models.BooleanField(
        default=False,
        verbose_name="[Deprecated] Enviada a Meta",
        help_text="No usar - Solo Twilio"
    )
    
    class Meta:
        verbose_name = 'Plantilla de Mensaje'
        verbose_name_plural = 'Plantillas de Mensaje'
        ordering = ['-fecha_modificacion']
    
    def __str__(self):
        emoji = self.emoji or self.get_default_emoji()
        return f"{emoji} {self.nombre_interno}"

    def get_default_emoji(self):
        """Retorna emoji por defecto según la categoría"""
        defaults = {
            'cultivos': '',
            'ganaderia': '',
            'general_agricola': '',
            'educacion': '',
            'gestion': '',
            'otro': ''
        }
        return defaults.get(self.categoria, '')

    def save(self, *args, **kwargs):
        """Autocompletar emoji si está vacío"""
        if not self.emoji:
            self.emoji = self.get_default_emoji()
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        import re
        
        # Validar longitud máxima de WhatsApp (1600 caracteres)
        if len(self.cuerpo_mensaje) > 1600:
            raise ValidationError({
                'cuerpo_mensaje': f'El mensaje es demasiado largo ({len(self.cuerpo_mensaje)} caracteres). WhatsApp tiene un límite de 1600 caracteres.'
            })
        
        # Advertir si usa variables que no existen
        variables_validas = ['{nombre}', '{telefono}', '{curso}']
        variables_encontradas = re.findall(r'\{(\w+)\}', self.cuerpo_mensaje)
        
        for var in variables_encontradas:
            if f'{{{var}}}' not in variables_validas:
                raise ValidationError({
                    'cuerpo_mensaje': f'Variable desconocida: {{{var}}}. Variables válidas: {", ".join(variables_validas)}'
                })
    
    def vista_previa(self):
        """Retorna una vista previa del mensaje"""
        return self.cuerpo_mensaje[:100] + '...' if len(self.cuerpo_mensaje) > 100 else self.cuerpo_mensaje
    
    def incrementar_uso(self):
        """Incrementa el contador de uso"""
        self.veces_usada += 1
        self.save(update_fields=['veces_usada'])

# 3. CAMPAÑA
class Campana(models.Model):
    nombre = models.CharField(max_length=100)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='campanas',
        verbose_name='Cliente',
        help_text='Cliente para el que es esta campaña'
    )
    
    # NUEVO CAMPO: Subir Excel
    archivo_excel = models.FileField(
        upload_to='excels/', 
        blank=True, null=True,
        help_text="Sube un archivo .xlsx con columnas: 'Nombre' y 'Telefono'. Se agregarán automáticamente."
    )
    
    # NUEVO: Categoría de la campaña (para filtrar plantillas)
    CATEGORIA_CHOICES = [
        ('cultivos', 'Cultivos'),
        ('ganaderia', 'Ganadería'),
        ('general_agricola', 'General Agrícola'),
        ('educacion', 'Educación'),
        ('gestion', 'Gestión'),
        ('todas', 'Todas las categorías'),
    ]
    
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='todas',
        verbose_name="Categoría",
        help_text="Filtrar plantillas por categoría. 'Todas' mostrará plantillas de cualquier categoría.",
    )
    
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT, null=True, blank=True)
    
    # Envío directo con Content Template de Twilio (sin Django Plantilla)
    template_twilio_id = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name="Content SID de Twilio",
        help_text="SID del template aprobado en Twilio (ej: HX123abc...). Si se llena, se usa en vez de la plantilla Django."
    )
    
    # CAMPAÑA DE CURSO: Al ejecutar, pone estudiantes en flujo habeas data → curso
    es_campana_curso = models.BooleanField(
        default=False,
        verbose_name="¿Es campaña de inicio de curso?",
        help_text="Si está activado, al enviar la campaña los estudiantes entrarán al flujo de habeas data → verificación → curso."
    )
    curso_destino = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campanas_curso',
        verbose_name='Curso destino',
        help_text='Curso al que se inscribirán los estudiantes al completar el onboarding de esta campaña.'
    )
    
    # NUEVO: Tipo de audiencia (individual o grupo)
    TIPO_AUDIENCIA_CHOICES = [
        ('individual', 'Estudiantes individuales'),
        ('grupo', 'Grupo de estudiantes'),
    ]
    tipo_audiencia = models.CharField(
        max_length=20,
        choices=TIPO_AUDIENCIA_CHOICES,
        default='individual',
        verbose_name='Tipo de audiencia',
        help_text='Selecciona si quieres enviar a estudiantes individuales o a un grupo'
    )
    
    # NUEVO: Grupo de destinatarios (opcional, solo si tipo_audiencia='grupo')
    grupo = models.ForeignKey(
        'GrupoEstudiantes',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Grupo',
        help_text='Selecciona el grupo al que se enviará la campaña',
        related_name='campanas'
    )
    
    destinatarios = models.ManyToManyField(Estudiante, blank=True) # blank=True para permitir guardar sin seleccionar manual

    # Canal de envío (solo WhatsApp)
    CANAL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
    ]
    canal_envio = models.CharField(
        max_length=20, 
        choices=CANAL_CHOICES, 
        default='whatsapp',
        verbose_name='Canal de Envío',
        help_text='Actualmente solo se soporta WhatsApp'
    )

    # Línea de origen (opcional)
    linea_origen = models.ForeignKey('Linea', null=True, blank=True, on_delete=models.SET_NULL)

    # Envío programado
    fecha_programada = models.DateTimeField(blank=True, null=True)

    ejecutada = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    # Estadísticas de envío
    total_enviados = models.IntegerField(default=0, verbose_name="Total enviados")
    respuestas_si = models.IntegerField(default=0, verbose_name="Respuestas SÍ")
    respuestas_no = models.IntegerField(default=0, verbose_name="Respuestas NO")
    
    def get_plantillas_disponibles(self):
        """Retorna plantillas filtradas por el tema de la campaña"""
        if self.tema:
            return Plantilla.objects.filter(temas=self.tema, activa=True)
        return Plantilla.objects.filter(activa=True)

    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Campaña'
        verbose_name_plural = 'Campañas'


# 3b. LINEAS (líneas de envío, e.g., cuentas de WhatsApp)
class Linea(models.Model):
    nombre = models.CharField(max_length=100, help_text='Etiqueta de la línea, p.ej. FKWhatsapp')
    numero = models.CharField(max_length=30, help_text='Número de la línea, p.ej. +573208198063')

    def __str__(self):
        return f"{self.nombre} ({self.numero})"

# 4. LOGS
class EnvioLog(models.Model):
    campana = models.ForeignKey(Campana, on_delete=models.CASCADE)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, default='PENDIENTE')
    
    # 👇 ESTA ES LA LÍNEA QUE FALTABA, AGRÉGALA:
    respuesta_api = models.TextField(blank=True, null=True, help_text="Respuesta del servidor")
    
    fecha_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.estado}"


# Registro de mensajes enviados/recibidos por WhatsApp
class WhatsappLog(models.Model):
    TIPO_CHOICES = [
        ('INCOMING', 'Mensaje Recibido'),
        ('SENT', 'Mensaje Enviado'),
    ]
    
    telefono = models.CharField(max_length=30)
    mensaje = models.TextField(blank=True, null=True)
    mensaje_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    estado = models.CharField(max_length=50, default='PENDING')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='INCOMING')
    fecha = models.DateTimeField(auto_now_add=True)
    estudiante = models.ForeignKey(
        Estudiante, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='mensajes_whatsapp',
        help_text='Estudiante asociado a esta conversación'
    )
    
    # Soporte para mensajes de audio
    es_audio = models.BooleanField(
        default=False,
        help_text='Indica si el mensaje es un audio'
    )
    audio_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='URL del archivo de audio'
    )
    audio_transcripcion = models.TextField(
        blank=True,
        null=True,
        help_text='Transcripción del audio (generada por Whisper)'
    )
    audio_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Ruta local del archivo de audio descargado'
    )
    agente_usado = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Nombre del agente IA que generó la respuesta'
    )
    tema_detectado = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Tema detectado en la conversación (café, aguacate, etc.)'
    )

    # Nuevo: campo para guardar detalles de error Twilio
    error_detalle = models.TextField(
        blank=True,
        null=True,
        help_text='Detalle de error Twilio o del envío (código, mensaje, etc.)'
    )

    def __str__(self):
        return f"{self.telefono} - {self.tipo} - {self.estado} ({self.mensaje_id})"
    
    class Meta:
        verbose_name = 'Registro de WhatsApp'
        verbose_name_plural = 'Historial WhatsApp'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['telefono', '-fecha']),
        ]


class SesionComercial(models.Model):
    """Memoria de conversación del bot comercial por cliente + teléfono."""

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sesiones_comerciales',
        verbose_name='Cliente',
    )
    telefono = models.CharField(max_length=30, db_index=True)
    historial_mensajes = models.JSONField(
        default=list,
        blank=True,
        help_text='Lista de mensajes [{"role": "...", "content": "..."}]. Máximo 10 turnos (20 mensajes).',
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_mensaje = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = 'Sesión comercial'
        verbose_name_plural = 'Sesiones comerciales'
        ordering = ['-fecha_ultimo_mensaje']
        indexes = [
            models.Index(fields=['telefono', '-fecha_ultimo_mensaje']),
            models.Index(fields=['cliente', '-fecha_ultimo_mensaje']),
        ]

    def __str__(self):
        cliente_txt = self.cliente.nombre if self.cliente_id else 'General'
        return f"{self.telefono} ({cliente_txt})"


# Procesar Excel subido: crear Estudiantes y agregarlos a la campaña
@receiver(post_save, sender=Campana)
def procesar_excel_campana(sender, instance, created, **kwargs):
    # Si hay un archivo y no hay destinatarios, intentamos cargarlo
    if instance.archivo_excel and instance.destinatarios.count() == 0:
        try:
            file_path = instance.archivo_excel.path
            if os.path.exists(file_path):
                wb = openpyxl.load_workbook(file_path)
                sheet = wb.active
                # Esperamos: columna A = Nombre, columna B = Telefono
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if not row: 
                        continue
                    nombre = str(row[0]).strip() if row[0] is not None else ''
                    telefono = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
                    if not telefono:
                        continue
                    # Normalizamos y creamos/obtenemos estudiante
                    try:
                        estudiante, created_est = Estudiante.objects.get_or_create(telefono=telefono, defaults={'nombre': nombre})
                    except IntegrityError:
                        # Si falla por formato, intentamos limpiar y reintentar
                        telefono_clean = re.sub(r'\D', '', telefono)
                        if len(telefono_clean) == 10:
                            telefono_clean = f"57{telefono_clean}"
                        estudiante, created_est = Estudiante.objects.get_or_create(telefono=telefono_clean, defaults={'nombre': nombre})
                    # Añadimos a destinatarios
                    instance.destinatarios.add(estudiante)
                # Guardar para asegurar M2M
                instance.save()
        except Exception:
            # Si falla la lectura del excel no queremos romper el flujo de guardado
            pass


# ==========================================
# SISTEMA EDUCATIVO DE CURSOS
# ==========================================

class Curso(models.Model):
    """Curso completo (ej: Café, Aguacate, Ganadería)"""
    nombre = models.CharField(max_length=200, help_text="Ej: Café Arábigo")
    descripcion = models.TextField(help_text="Descripción completa del curso")
    emoji = models.CharField(max_length=10, default="", blank=True, help_text="Emoji representativo (opcional)")
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cursos',
        verbose_name='Cliente Específico',
        help_text='Si es para un cliente específico. Dejar vacío = curso general de eki disponible para todos'
    )
    duracion_semanas = models.IntegerField(default=5, help_text="Duración estimada en semanas")
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(default=0, help_text="Orden de visualización")
    
    # GAMIFICACION OPCIONAL
    usar_gamificacion = models.BooleanField(
        default=True,
        verbose_name='Usar Gamificación',
        help_text='Si está activado, se otorgan puntos y badges en este curso'
    )
    habilitar_pregunta_abierta_final = models.BooleanField(
        default=False,
        verbose_name='Habilitar Pregunta Abierta Final',
        help_text='Si está activado, este curso puede mostrar preguntas abiertas finales (hasta 3).'
    )
    
    # GRUPO DE WHATSAPP
    enlace_grupo_whatsapp = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Enlace de Grupo de WhatsApp',
        help_text='Enlace de invitación al grupo de WhatsApp del curso (ej: https://chat.whatsapp.com/xxxxx)'
    )
    
    # NOMBRES PERSONALIZADOS DE AGENTES IA
    nombre_agente_tutor = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Nombre del Profesor (Tutor IA)',
        help_text='Nombre personalizado para el agente tutor/profesor (por defecto: Gerónimo). Ej: Carlos, Sofía'
    )
    nombre_agente_asistente = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Nombre de la Asistente (IA)',
        help_text='Nombre personalizado para la agente asistente (por defecto: María). Ej: Laura, Andrea'
    )
    
    # PREGUNTAS EJEMPLO PARA IA — alimentadas por admin
    preguntas_ejemplo_ia = models.TextField(
        blank=True,
        default='',
        verbose_name='Preguntas ejemplo para IA',
        help_text='Preguntas ejemplo que la IA usará como referencia para generar la pregunta final de recuperación. Una pregunta por línea.'
    )
    dias_espera_entre_modulos = models.IntegerField(
        default=0,
        verbose_name='Días de espera entre módulos',
        help_text='0 = flujo libre. >0 bloquea avance hasta cumplir días entre módulos. Para el mismo curso en varias empresas con ritmos distintos, usar Configuración drip en el admin del Cliente.'
    )

    # Activador del formulario GEI sin tocar TipoFormulario.
    tiene_formulario_gei = models.BooleanField(
        default=False,
        verbose_name='¿Activa formulario GEI al completar el último módulo?',
        help_text=(
            'Si está activo, al completar el módulo disparador configurado en '
            'Formulario → Tipos de formulario se inicia la recolección de datos '
            'GEI por WhatsApp. Si está inactivo, ningún flujo se dispara aunque '
            'exista el TipoFormulario.'
        ),
    )

    # Toggle de retos IA (Darío + Claudia) al terminar módulo 3 y módulo final.
    usar_agentes_ia = models.BooleanField(
        default=True,
        verbose_name='¿Usar retos con agentes IA (Darío + Claudia)?',
        help_text=(
            'Si está activo, al completar el módulo 3 y el último módulo del curso se '
            'dispara una pausa con el asistente Darío (resuelve dudas) y luego un reto '
            'evaluado por la facilitadora Claudia (otorga puntos). '
            'Si está inactivo, el curso es lineal: examen → siguiente módulo, sin retos. '
            'Útil para cursos cortos, formularios o pilotos donde no se quiere la capa de IA.'
        ),
    )

    visible_en_aula = models.BooleanField(
        default=False,
        verbose_name='Visible en aula (catálogo interno)',
        help_text=(
            'Reservado para listados internos. El catálogo público de inscripción '
            'vive en eki Studio (visible_en_studio).'
        ),
    )

    visible_en_studio = models.BooleanField(
        default=False,
        verbose_name='Publicado en eki Studio',
        help_text=(
            'Si está activo, el curso aparece en studio.eki.technology para que '
            'estudiantes elegibles se inscriban. El estudio se hace en el aula virtual.'
        ),
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self):
        return f"{self.emoji} {self.nombre}"

    def total_modulos(self):
        return self.modulos.count()

    def copiar_a_analytics_pruebas(self, reset: bool = False):
        """Copia este curso al cliente Analytics (Pruebas). Ver ``core.copiar_cursos``."""
        from core.copiar_cursos import copiar_cursos_a_pruebas

        return copiar_cursos_a_pruebas(solo_curso_id=self.pk, reset=reset)


class ConfiguracionDripCliente(models.Model):
    """
    Override del ritmo drip (días entre módulos) por cliente y curso.
    Permite que un curso global tenga 7 días de espera para la cooperativa A
    y flujo libre para la empresa B, sin duplicar el curso.
    """
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='configuraciones_drip_curso',
        verbose_name='Cliente',
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='configuraciones_drip_cliente',
        verbose_name='Curso',
    )
    dias_espera_entre_modulos = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Días de espera (override)',
        help_text='Vacío = usar el valor configurado en el curso. 0 = sin espera para este cliente. N = N días entre módulos.',
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Si está desactivado, se ignora esta fila y se usa solo el curso.',
    )

    class Meta:
        verbose_name = 'Configuración drip (cliente × curso)'
        verbose_name_plural = 'Configuraciones drip (cliente × curso)'
        constraints = [
            models.UniqueConstraint(fields=['cliente', 'curso'], name='uniq_drip_cliente_curso'),
        ]

    def __str__(self):
        return f'{self.cliente} → {self.curso}'


class HabilitacionModuloDripCliente(models.Model):
    """
    Fecha/hora en que un módulo concreto se habilita para los estudiantes de un cliente.
    Sustituye el campo «Disponible desde» del módulo cuando existe fila activa para ese cliente × curso × módulo.
    """

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='habilitaciones_modulo_drip',
        verbose_name='Cliente',
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='habilitaciones_modulo_por_cliente',
        verbose_name='Curso',
    )
    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.CASCADE,
        related_name='habilitaciones_por_cliente',
        verbose_name='Módulo',
    )
    habilitado_desde = models.DateTimeField(
        verbose_name='Disponible desde',
        help_text='Hora local del servidor según TIME_ZONE; el estudiante no recibe este módulo antes de este instante.',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Habilitación de módulo (cliente × curso × módulo)'
        verbose_name_plural = 'Habilitaciones de módulos por cliente'
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'curso', 'modulo'],
                name='uniq_habilitacion_drip_cliente_curso_modulo',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.modulo_id and self.curso_id and self.modulo.curso_id != self.curso_id:
            raise ValidationError('El módulo debe pertenecer al curso seleccionado.')

    def __str__(self):
        return f'{self.cliente} · M{self.modulo.numero} · desde {self.habilitado_desde}'


class HabilitacionModuloEstudiante(models.Model):
    """
    Override de drip/calendario por estudiante (además del drip del cliente).
    Con «Módulos solo por lista» en el cliente, solo estos estudiantes acceden al módulo.
    """

    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.CASCADE,
        related_name='habilitaciones_modulo_individual',
        verbose_name='Estudiante',
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='habilitaciones_modulo_estudiante',
        verbose_name='Curso',
    )
    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.CASCADE,
        related_name='habilitaciones_estudiante',
        verbose_name='Módulo',
    )
    habilitado_desde = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Disponible desde (este estudiante)',
        help_text=(
            'Opcional. Si se define, sustituye la fecha del cliente para este estudiante. '
            'Vacío = sin fecha extra (solo inclusión en la lista).'
        ),
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    notas = models.CharField(max_length=200, blank=True, default='', verbose_name='Notas internas')

    class Meta:
        verbose_name = 'Habilitación de módulo (estudiante)'
        verbose_name_plural = 'Habilitaciones de módulos por estudiante'
        constraints = [
            models.UniqueConstraint(
                fields=['estudiante', 'curso', 'modulo'],
                name='uniq_habilitacion_modulo_estudiante',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.modulo_id and self.curso_id and self.modulo.curso_id != self.curso_id:
            raise ValidationError('El módulo debe pertenecer al curso seleccionado.')
        if self.estudiante_id and self.curso_id and self.estudiante.cliente_id:
            curso = self.curso
            if curso.cliente_id and curso.cliente_id != self.estudiante.cliente_id:
                raise ValidationError('El curso debe ser del mismo cliente que el estudiante.')

    def __str__(self):
        desde = self.habilitado_desde.strftime('%d/%m/%Y %H:%M') if self.habilitado_desde else 'sin fecha'
        return f'{self.estudiante.nombre} · M{self.modulo.numero} · {desde}'


class DocumentoRAG(models.Model):
    """
    Documento subido para el sistema RAG Multi-Tenant.
    Cada documento se asocia a un Curso (y por extensión a su Cliente).
    Los agentes IA usan estos documentos para responder preguntas.
    
    Aislamiento: Solo el curso al que pertenece puede acceder a este documento.
    """
    TIPO_CHOICES = [
        ('contenido', 'Contenido del Curso'),
        ('manual', 'Manual / Documentación'),
        ('faq', 'Preguntas Frecuentes'),
        ('guia', 'Guía Práctica'),
        ('normativa', 'Normativa / Regulación'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de indexar'),
        ('indexado', 'Indexado en RAG'),
        ('error', 'Error al indexar'),
    ]

    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='documentos_rag',
        verbose_name='Curso',
        help_text='Curso al que pertenece este documento. Los agentes IA SOLO verán documentos de su curso.'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del documento',
        help_text='Identificador único (ej: Manual_Tomates_v1, FAQ_Café)'
    )
    archivo = models.FileField(
        upload_to='documentos_rag/%Y/%m/',
        verbose_name='Archivo (PDF, DOCX, TXT, XLSX)',
        help_text='Formatos soportados: .pdf, .docx, .txt, .xlsx, .xlsm (Excel; listas de precios)',
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='contenido',
        verbose_name='Tipo de documento'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado RAG'
    )
    chunks_indexados = models.IntegerField(
        default=0,
        verbose_name='Chunks indexados',
        help_text='Cantidad de fragmentos indexados en la BD vectorial'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción opcional del contenido del documento'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_indexado = models.DateTimeField(null=True, blank=True)
    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Subido por'
    )

    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Documento RAG'
        verbose_name_plural = 'Documentos RAG (Base de Conocimiento IA)'
        unique_together = ['curso', 'nombre']
        indexes = [
            models.Index(fields=['curso', 'estado']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.curso.nombre})"

    @property
    def cliente_id(self):
        return self.curso.cliente_id if self.curso.cliente_id else 0

    def indexar(self):
        """Indexa este documento en ChromaDB para el cliente+curso."""
        from core.rag_manager import rag_manager
        from django.utils import timezone
        import os

        if not self.archivo:
            self.estado = 'error'
            self.save(update_fields=['estado'])
            return 0

        try:
            ruta = self.archivo.path
            if not os.path.exists(ruta):
                # Intentar descargar desde S3 a temp
                ruta = self._descargar_temp()
                if not ruta:
                    self.estado = 'error'
                    self.save(update_fields=['estado'])
                    return 0

            n_chunks = rag_manager.procesar_documento(
                cliente_id=self.cliente_id,
                curso_id=self.curso_id,
                ruta_archivo=ruta,
                nombre_documento=self.nombre,
                tipo=self.tipo
            )
            self.chunks_indexados = n_chunks
            self.estado = 'indexado' if n_chunks > 0 else 'error'
            self.fecha_indexado = timezone.now()
            self.save(update_fields=['chunks_indexados', 'estado', 'fecha_indexado'])
            return n_chunks
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAG] Error indexando {self.nombre}: {e}")
            self.estado = 'error'
            self.save(update_fields=['estado'])
            return 0

    def _descargar_temp(self):
        """Descarga archivo desde storage (S3) a /tmp para procesamiento."""
        import tempfile
        try:
            ext = os.path.splitext(self.archivo.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in self.archivo.chunks():
                    tmp.write(chunk)
                return tmp.name
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAG] Error descargando {self.nombre}: {e}")
            return None


class DocumentoRAGComercial(models.Model):
    """
    Documento para el RAG comercial.
    Aislado del RAG de cursos para evitar mezclar conocimiento educativo y comercial.
    """
    CANAL_CHOICES = [
        ('bot_comercial', 'Bot Comercial WhatsApp'),
    ]
    TIPO_CHOICES = [
        ('producto', 'Producto / Catálogo'),
        ('precio', 'Precio / Lista comercial'),
        ('informe_tecnico', 'Informe técnico (ICA / ensayos)'),
        ('faq', 'Preguntas frecuentes comerciales'),
        ('politica', 'Políticas comerciales'),
        ('promo', 'Promociones'),
        ('general', 'Información general comercial'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de indexar'),
        ('indexado', 'Indexado en RAG comercial'),
        ('error', 'Error al indexar'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_rag_comercial',
        verbose_name='Cliente',
        help_text='Cliente comercial del documento. Vacío = comercial general.'
    )
    canal = models.CharField(
        max_length=40,
        choices=CANAL_CHOICES,
        default='bot_comercial',
        verbose_name='Canal comercial'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del documento',
        help_text='Identificador único por cliente/canal (ej: catalogo_abril_2026).'
    )
    archivo = models.FileField(
        upload_to='documentos_rag_comercial/%Y/%m/',
        verbose_name='Archivo (PDF, DOCX, TXT, XLSX)',
        help_text='Formatos soportados: .pdf, .docx, .txt, .xlsx, .xlsm (Excel; listas de precios)',
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='producto',
        verbose_name='Tipo de documento'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado RAG'
    )
    chunks_indexados = models.IntegerField(
        default=0,
        verbose_name='Chunks indexados',
        help_text='Cantidad de fragmentos indexados en la BD vectorial comercial.'
    )
    error_indexacion = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Motivo del último fallo de indexación RAG.',
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción opcional del contenido comercial.'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_indexado = models.DateTimeField(null=True, blank=True)
    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Subido por'
    )

    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Documento RAG Comercial'
        verbose_name_plural = 'Documentos RAG Comercial'
        unique_together = ['cliente', 'canal', 'nombre']
        indexes = [
            models.Index(fields=['cliente', 'canal', 'estado']),
        ]

    def __str__(self):
        cliente_txt = self.cliente.nombre if self.cliente else 'General'
        return f"{self.nombre} ({cliente_txt} - {self.canal})"

    @property
    def cliente_scope_id(self):
        return self.cliente_id if self.cliente_id else 0

    def indexar(self):
        """Indexa este documento en el RAG comercial (aislado de cursos)."""
        from core.rag_comercial_manager import rag_comercial_manager
        from django.utils import timezone

        if not self.archivo:
            self.estado = 'error'
            self.error_indexacion = 'Sin archivo adjunto.'
            self.save(update_fields=['estado', 'error_indexacion'])
            return 0

        if not rag_comercial_manager.disponible:
            self.estado = 'error'
            self.error_indexacion = 'ChromaDB no disponible en el servidor.'
            self.save(update_fields=['estado', 'error_indexacion'])
            return 0

        ruta_temp = None
        try:
            ruta = None
            try:
                if hasattr(self.archivo, 'path') and os.path.exists(self.archivo.path):
                    ruta = self.archivo.path
            except Exception:
                pass
            if not ruta:
                ruta_temp = self._descargar_temp()
                ruta = ruta_temp
            if not ruta:
                self.estado = 'error'
                self.error_indexacion = 'No se pudo descargar el archivo desde almacenamiento (S3).'
                self.save(update_fields=['estado', 'error_indexacion'])
                return 0

            n_chunks = rag_comercial_manager.procesar_documento(
                cliente_id=self.cliente_scope_id,
                canal=self.canal,
                ruta_archivo=ruta,
                nombre_documento=self.nombre,
                tipo=self.tipo,
            )

            if n_chunks == 0:
                from core.extractores_documento import extraer_texto_archivo

                texto_arch, metodo = extraer_texto_archivo(ruta)
                fallback = f"# {self.nombre}\n\n{(self.descripcion or '').strip()}"
                if len(fallback.strip()) < 15:
                    fallback = f"# {self.nombre}\nDocumento comercial indexado desde biblioteca RAG."
                if len(texto_arch.strip()) >= 5:
                    fallback = f"{fallback}\n\nExtracto parcial ({metodo}):\n{texto_arch[:8000]}"
                n_chunks = rag_comercial_manager.procesar_texto(
                    cliente_id=self.cliente_scope_id,
                    canal=self.canal,
                    texto=fallback,
                    nombre_documento=self.nombre,
                    tipo=self.tipo,
                )

            self.chunks_indexados = n_chunks
            if n_chunks > 0:
                self.estado = 'indexado'
                self.error_indexacion = ''
            else:
                self.estado = 'error'
                from core.extractores_documento import diagnostico_pdf
                ext = os.path.splitext(ruta)[1].lower()
                if ext == '.pdf':
                    diag = diagnostico_pdf(ruta)
                    self.error_indexacion = (
                        f'PDF sin texto indexable ({diag.get("paginas", "?")} págs, '
                        f'método={diag.get("metodo")}). '
                        'Si es escaneado, active OCR o agregue descripción al documento.'
                    )[:500]
                else:
                    self.error_indexacion = 'No se extrajo texto del archivo. Revise formato o agregue descripción.'
            self.fecha_indexado = timezone.now()
            self.save(update_fields=['chunks_indexados', 'estado', 'error_indexacion', 'fecha_indexado'])
            return n_chunks
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAGComercial] Error indexando {self.nombre}: {e}")
            self.estado = 'error'
            self.error_indexacion = str(e)[:500]
            self.save(update_fields=['estado', 'error_indexacion'])
            return 0
        finally:
            if ruta_temp and os.path.exists(ruta_temp):
                try:
                    os.unlink(ruta_temp)
                except Exception:
                    pass

    def _descargar_temp(self):
        """Descarga archivo desde storage a un temporal local para indexación."""
        import tempfile

        try:
            ext = os.path.splitext(self.archivo.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in self.archivo.chunks():
                    tmp.write(chunk)
                return tmp.name
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAGComercial] Error descargando {self.nombre}: {e}")
            return None


class BibliotecaConocimiento(models.Model):
    """
    Knowledge Hub Nat — biblioteca de conocimiento agrícola por organización.
    Alimenta el RAG comercial (Chroma) además de DocumentoRAGComercial legacy.
    """

    CATEGORIA_CHOICES = [
        ('manuales', 'Manuales'),
        ('investigaciones', 'Investigaciones'),
        ('protocolos', 'Protocolos'),
        ('cartillas', 'Cartillas'),
        ('videos', 'Videos'),
        ('podcasts', 'Podcasts'),
        ('faq', 'Preguntas frecuentes'),
        ('casos', 'Casos reales'),
        ('productos', 'Productos'),
        ('normatividad', 'Normatividad'),
        ('noticias', 'Noticias'),
        ('experiencias', 'Experiencias'),
        ('general', 'General'),
    ]
    FORMATO_CHOICES = [
        ('archivo', 'Archivo (PDF, Word, Excel…)'),
        ('texto', 'Artículo / texto'),
        ('faq', 'Pregunta y respuesta'),
        ('enlace', 'Enlace web'),
        ('imagen', 'Imagen'),
        ('audio', 'Audio / podcast'),
        ('video', 'Video'),
    ]
    NIVEL_CHOICES = [
        ('basico', 'Básico'),
        ('intermedio', 'Intermedio'),
        ('avanzado', 'Avanzado'),
    ]
    FUENTE_CHOICES = [
        ('cliente', 'Organización'),
        ('agrosavia', 'AGROSAVIA'),
        ('ica', 'ICA'),
        ('fedepanela', 'Fedepanela'),
        ('cenipalma', 'Cenipalma'),
        ('ciat', 'CIAT'),
        ('fao', 'FAO'),
        ('eki', 'eki'),
        ('otro', 'Otra fuente'),
    ]
    ESTADO_PUBLICACION_CHOICES = [
        ('borrador', 'Borrador'),
        ('publicado', 'Publicado'),
        ('archivado', 'Archivado'),
    ]
    ESTADO_RAG_CHOICES = [
        ('pendiente', 'Pendiente de indexar'),
        ('indexado', 'Indexado en RAG'),
        ('error', 'Error al indexar'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='biblioteca_conocimiento',
    )
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, help_text='Identificador único para indexación RAG')
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES, default='general')
    formato = models.CharField(max_length=20, choices=FORMATO_CHOICES, default='archivo')
    pregunta = models.CharField(max_length=500, blank=True, default='', help_text='Solo FAQ')
    texto_contenido = models.TextField(blank=True, default='', help_text='Artículo, respuesta FAQ o transcripción')
    archivo = models.FileField(
        upload_to='biblioteca_nat/%Y/%m/',
        blank=True,
        null=True,
        help_text='PDF, DOCX, TXT, XLSX, imagen, audio o video',
    )
    enlace_url = models.URLField(max_length=500, blank=True, default='')
    cultivo = models.CharField(max_length=80, blank=True, default='')
    problema = models.CharField(max_length=120, blank=True, default='')
    region = models.CharField(max_length=120, blank=True, default='')
    idioma = models.CharField(max_length=20, default='es', verbose_name='Idioma')
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='basico')
    fuente = models.CharField(max_length=30, choices=FUENTE_CHOICES, default='cliente')
    autor = models.CharField(max_length=120, blank=True, default='')
    fecha_contenido = models.DateField(null=True, blank=True)
    estado_publicacion = models.CharField(
        max_length=20,
        choices=ESTADO_PUBLICACION_CHOICES,
        default='publicado',
    )
    estado_rag = models.CharField(max_length=20, choices=ESTADO_RAG_CHOICES, default='pendiente')
    rag_error_detalle = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Motivo del último fallo de indexación (si aplica).',
    )
    chunks_indexados = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_indexado = models.DateTimeField(null=True, blank=True)
    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biblioteca_subidos',
    )

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Conocimiento (biblioteca Nat)'
        verbose_name_plural = 'Biblioteca de conocimiento Nat'
        unique_together = [('cliente', 'slug')]
        indexes = [
            models.Index(fields=['cliente', 'estado_publicacion', 'categoria']),
        ]

    def __str__(self):
        return f'{self.titulo} ({self.cliente.nombre})'

    @property
    def cliente_scope_id(self):
        return self.cliente_id


class ProductoComercial(models.Model):
    """
    Catálogo de precios estructurado para Nat (WhatsApp comercial).
    Fuente de verdad en Postgres; el RAG comercial queda para documentos técnicos.
    """

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='productos_comerciales',
        verbose_name='Cliente',
        help_text='Vacío = catálogo general visible para todos los clientes.',
    )
    sku = models.CharField(
        max_length=80,
        verbose_name='SKU / código',
        help_text='Identificador único por cliente (ej: UREA-46-50KG).',
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del producto')
    presentacion = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Presentación',
        help_text='Ej: bulto 50 kg, garrafa 1 L.',
    )
    unidad = models.CharField(
        max_length=40,
        blank=True,
        default='',
        verbose_name='Unidad de venta',
        help_text='Ej: bulto, kg, litro.',
    )
    precio = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Precio',
    )
    moneda = models.CharField(max_length=8, default='COP', verbose_name='Moneda')
    categoria = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='Categoría',
        help_text='Ej: fertilizante, herbicida, fungicida.',
    )
    notas = models.TextField(blank=True, default='', verbose_name='Notas comerciales')
    vigencia_desde = models.DateField(null=True, blank=True, verbose_name='Vigente desde')
    vigencia_hasta = models.DateField(null=True, blank=True, verbose_name='Vigente hasta')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto comercial (precio)'
        verbose_name_plural = 'Productos comerciales (precios)'
        ordering = ['nombre', 'sku']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'sku'],
                name='uniq_producto_comercial_cliente_sku',
            ),
        ]
        indexes = [
            models.Index(fields=['cliente', 'activo', '-fecha_actualizacion']),
            models.Index(fields=['nombre']),
            models.Index(fields=['categoria']),
        ]

    def __str__(self):
        cliente_txt = self.cliente.nombre if self.cliente_id else 'General'
        return f"{self.sku} — {self.nombre} ({cliente_txt})"


class ProductoCatalogo(models.Model):
    """
    Catálogo comercial por organización (Cliente) para recomendaciones Nat.
    Separado de ProductoComercial (lista de precios SKU) y de DocumentoRAGComercial.
    """

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='catalogo_productos',
        verbose_name='Cliente',
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del producto')
    descripcion = models.TextField(
        verbose_name='Descripción',
        help_text='Para qué sirve el producto',
    )
    problema_que_resuelve = models.TextField(
        verbose_name='Problemas que resuelve',
        help_text=(
            'Síntomas o problemas del cultivo que este producto atiende. '
            'Ej: roya, manchas amarillas, deficiencia de nitrógeno, plagas de suelo. '
            'Mientras más descriptivo, mejor el match con la pregunta del agricultor.'
        ),
    )
    ingrediente_activo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Ingrediente activo',
    )
    categoria = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Categoría',
        help_text='Ej: fungicida, fertilizante foliar, bioestimulante, herbicida',
    )
    cultivos_objetivo = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Cultivos objetivo',
        help_text='Ej: café, caña panelera, aguacate, maíz',
    )
    dosis = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Dosis recomendada',
        help_text='Ej: 300-500g por 200L de agua',
    )
    precio_cop = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name='Precio (COP)',
    )
    unidad = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Unidad de venta',
        help_text='Ej: 500g, 1L, bolsa x 25kg',
    )
    url_producto = models.URLField(
        blank=True,
        verbose_name='Link del producto',
        help_text='URL directa a la página de compra del producto',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto del catálogo'
        verbose_name_plural = 'Catálogo de productos'
        ordering = ['cliente', 'categoria', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'nombre'],
                name='uniq_producto_catalogo_cliente_nombre',
            ),
        ]

    def __str__(self):
        precio_str = f' — ${self.precio_cop:,.0f}' if self.precio_cop else ''
        return f'{self.nombre} ({self.cliente.nombre}){precio_str}'


class Modulo(models.Model):
    """Módulo dentro de un curso (ej: Módulo 1: Siembra)"""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='modulos')
    numero = models.PositiveIntegerField(
        help_text='Número de orden del módulo en el curso (enteros ≥ 0: 0 = intro/bienvenida, luego 1, 2, 3…)'
    )
    titulo = models.CharField(max_length=200, help_text="Ej: Siembra y Establecimiento")
    descripcion = models.TextField(help_text="Breve descripción del módulo")
    contenido = models.TextField(
        blank=True,
        default='',
        help_text=(
            'Contenido del módulo completo (Legacy). Obligatorio solo sin microcontenidos; '
            'con pasos en Microcontenidos puede quedar vacío.'
        ),
    )

    # 🎥 SOPORTE DE VIDEOS Y MULTIMEDIA
    video_url = models.URLField(
        max_length=500, 
        blank=True, 
        null=True,
        help_text="URL del video (YouTube, Vimeo, archivo directo)"
    )
    video_archivo = models.FileField(
        upload_to='videos/lecciones/%Y/%m/',
        blank=True,
        null=True,
        help_text="Archivo de video (MP4, baja resolución recomendada para el campo)"
    )
    video_resolucion = models.CharField(
        max_length=20,
        choices=[
            ('360p', '360p - Baja (recomendado campo)'),
            ('480p', '480p - Media'),
            ('720p', '720p - Alta'),
        ],
        default='360p',
        help_text="Resolución del video (baja = menos datos)"
    )
    imagen_portada_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL de la imagen de portada del módulo"
    )

    def get_video_url_publica(self):
        """
        Genera presigned URL de S3 para el video (bucket privado).
        Usa la misma lógica que obtener_video_url() de response_templates.
        """
        if self.video_url and self.video_url.startswith('http'):
            # Si es S3, convertir a presigned
            if 'eki-produccion.s3' in self.video_url:
                try:
                    import boto3
                    from botocore.config import Config
                    key = self.video_url.split('.amazonaws.com/')[-1].split('?')[0]
                    s3_client = boto3.client('s3', config=Config(signature_version='s3v4', region_name='us-east-2'))
                    return s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': 'eki-produccion', 'Key': key},
                        ExpiresIn=3600
                    )
                except Exception:
                    pass
            return self.video_url
        if self.video_archivo:
            try:
                import boto3
                from botocore.config import Config
                key = self.video_archivo.name.lstrip('/')
                s3_client = boto3.client('s3', config=Config(signature_version='s3v4', region_name='us-east-2'))
                return s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': 'eki-produccion', 'Key': key},
                    ExpiresIn=3600
                )
            except Exception:
                pass
        return None

    archivo_pdf_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Material PDF descargable"
    )
    
    # EXAMEN OBLIGATORIO
    examen_obligatorio = models.BooleanField(
        default=False,
        verbose_name='Examen Obligatorio',
        help_text='El estudiante DEBE aprobar el examen para avanzar al siguiente módulo'
    )
    puntaje_minimo_aprobacion = models.IntegerField(
        default=70,
        verbose_name='Puntaje Mínimo (%)',
        help_text='Porcentaje mínimo para aprobar (0-100)'
    )

    MODO_ENTREGA_AUTO = 'auto'
    MODO_ENTREGA_LEGACY = 'legacy'
    MODO_ENTREGA_PASOS = 'pasos'
    MODOS_ENTREGA = [
        (MODO_ENTREGA_AUTO, 'Automático (hereda: pasos si existen, legacy si no)'),
        (MODO_ENTREGA_LEGACY, 'Todo de una vez (contenido + multimedia completo)'),
        (MODO_ENTREGA_PASOS, 'Por pasos con "listo" (requiere pasos configurados)'),
    ]
    modo_entrega = models.CharField(
        max_length=10,
        choices=MODOS_ENTREGA,
        default=MODO_ENTREGA_AUTO,
        verbose_name='Modo de entrega',
        help_text=(
            'Automático: usa pasos si existen, legacy si no. '
            'Legacy: envía todo el módulo de una vez aunque haya pasos internos cargados. '
            'Pasos: un paso por *listo*; sin pasos activos el admin muestra aviso y el estudiante recibe un mensaje seguro.'
        ),
    )

    FACILITADOR_CP_AUTO = 'auto'
    FACILITADOR_CP_SI = 'si'
    FACILITADOR_CP_NO = 'no'
    facilitador_checkpoint = models.CharField(
        max_length=10,
        choices=[
            (FACILITADOR_CP_AUTO, 'Heredar regla del curso (mód. 3, penúltimos, etc.)'),
            (FACILITADOR_CP_SI, 'Sí: al cerrar este módulo, compañero + facilitadora'),
            (FACILITADOR_CP_NO, 'No: nunca checkpoint IA al cerrar este módulo'),
        ],
        default=FACILITADOR_CP_AUTO,
        verbose_name='Checkpoint facilitadora',
        help_text=(
            'Solo aplica si el curso tiene agentes IA activos. Define si al terminar este módulo '
            'entra el flujo Darío/facilitadora o se salta, independiente del número de módulo.'
        ),
    )

    secciones_por_listo = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Secciones por *listo*',
        help_text=(
            'Reservado: históricamente permitía agrupar varias secciones en un solo *listo*. '
            'Ahora siempre se pide *listo* entre secciones (un bloque a la vez) para asegurar que el '
            'estudiante sigue el material. Dentro de una misma sección pueden enviarse varios pasos seguidos.'
        ),
    )
    
    habilitado_desde = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Disponible desde (calendario global)',
        help_text=(
            'Opcional. Antes de esta fecha y hora ningún estudiante puede recibir este módulo al avanzar desde el anterior. '
            'Para una empresa concreta, creá una fila en el cliente: «Habilitación de módulos por cliente» (sustituye esto).'
        ),
    )

    duracion_dias = models.IntegerField(default=7, help_text="Días estimados para completar")

    def clean(self):
        from django.core.exceptions import ValidationError

        from .module_steps import validar_contenido_modulo

        super().clean()
        try:
            validar_contenido_modulo(self.contenido or '', self)
        except ValidationError as exc:
            raise ValidationError({'contenido': exc.messages}) from exc

    class Meta:
        ordering = ['curso', 'numero']
        verbose_name = "Módulo"
        verbose_name_plural = "Módulos"
        unique_together = ['curso', 'numero']

    def __str__(self):
        return f"{self.curso.nombre} - Módulo {self.numero}: {self.titulo}"


class SeccionModulo(models.Model):
    """Bloque dentro de un módulo: agrupa varios PasoModulo (organización en admin)."""

    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='secciones')
    orden = models.PositiveIntegerField(
        help_text='Orden de la sección dentro del módulo (1, 2, 3…).',
    )
    titulo = models.CharField(
        max_length=200,
        blank=True,
        help_text='Nombre interno para el equipo; no se envía por WhatsApp.',
    )
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['modulo', 'orden', 'id']
        verbose_name = 'Sección'
        verbose_name_plural = 'Secciones'
        constraints = [
            models.UniqueConstraint(
                fields=['modulo', 'orden'],
                name='uniq_seccionmodulo_modulo_orden',
            ),
        ]

    def __str__(self):
        t = (self.titulo or '').strip() or '(sin título)'
        return f'{self.modulo_id} · Sec.{self.orden} · {t}'


class PasoModulo(models.Model):
    """Paso interno de entrega progresiva (drip dentro del módulo por WhatsApp)."""
    TIPO_CONTENIDO = 'contenido'
    TIPO_EVAL_OPC = 'evaluacion_opciones'
    TIPO_EVAL_ABIERTA = 'evaluacion_abierta'
    TIPO_RETO = 'reto'
    TIPO_ENTREGA = 'entrega'
    TIPOS = [
        (TIPO_CONTENIDO, 'Contenido'),
        (TIPO_EVAL_OPC, 'Evaluación (opciones)'),
        (TIPO_EVAL_ABIERTA, 'Evaluación (abierta)'),
        (TIPO_RETO, 'Reto'),
        (TIPO_ENTREGA, 'Entrega'),
    ]

    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='pasos')
    seccion = models.ForeignKey(
        SeccionModulo,
        on_delete=models.CASCADE,
        related_name='pasos',
        help_text='Sección (bloque) a la que pertenece este paso.',
    )
    orden = models.PositiveIntegerField()
    titulo = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Referencia interna (admin). No se envía por WhatsApp; el texto al estudiante va en «Contenido».',
    )
    tipo = models.CharField(max_length=32, choices=TIPOS, default=TIPO_CONTENIDO)
    contenido = models.TextField(
        blank=True,
        help_text='Texto que ve el estudiante (enunciado, instrucciones). En evaluación opciones = la pregunta.',
    )
    media_url = models.URLField(
        max_length=1000,
        blank=True,
        help_text=(
            'URL pública del archivo (S3). Si usa «Subir archivo desde PC», se completa al Guardar. '
            'Debe verse un enlace https://… aquí; si queda vacío, el video no se enviará por WhatsApp.'
        ),
    )
    eval_opcion_a = models.TextField(blank=True, default='', verbose_name='Opción A')
    eval_opcion_b = models.TextField(blank=True, default='', verbose_name='Opción B')
    eval_opcion_c = models.TextField(blank=True, default='', verbose_name='Opción C')
    eval_opcion_d = models.TextField(blank=True, default='', verbose_name='Opción D')
    opciones_json = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            'Opcional / legado. Si completás A–D y «Letra correcta» arriba, se genera solo. '
            'Solo tocá este JSON si importás datos a mano.'
        ),
    )
    respuesta_correcta = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Letra correcta (A–D)',
        help_text='Para evaluación con opciones: A, B, C o D.',
    )
    feedback_correcto = models.TextField(blank=True)
    feedback_incorrecto = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    requiere_listo_para_avanzar = models.BooleanField(default=True)

    class Meta:
        ordering = ['modulo', 'orden', 'id']
        verbose_name = 'Paso'
        verbose_name_plural = 'Pasos'
        constraints = [
            models.UniqueConstraint(
                fields=['modulo', 'orden'],
                name='uniq_pasomodulo_modulo_orden',
            ),
        ]

    def __str__(self):
        return f'{self.modulo_id} · {self.orden} · {self.titulo}'

    @property
    def es_evaluacion(self):
        if self.tipo in (self.TIPO_EVAL_OPC, self.TIPO_EVAL_ABIERTA):
            return True
        if self.tipo == self.TIPO_CONTENIDO:
            from . import module_steps as _ms

            return _ms.paso_contenido_con_mc_como_eval(self)
        return False

    def save(self, *args, **kwargs):
        parts = {
            'A': (self.eval_opcion_a or '').strip(),
            'B': (self.eval_opcion_b or '').strip(),
            'C': (self.eval_opcion_c or '').strip(),
            'D': (self.eval_opcion_d or '').strip(),
        }
        rc = (self.respuesta_correcta or '').strip().upper()[:1]
        if any(parts.values()) or rc in ('A', 'B', 'C', 'D'):
            d = {k: v for k, v in parts.items() if v}
            if rc in ('A', 'B', 'C', 'D'):
                d['correcta'] = rc
            if d:
                self.opciones_json = d
        super().save(*args, **kwargs)


class ProgresoEstudiante(models.Model):
    """Progreso del estudiante en los cursos"""
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='progresos')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    modulo_actual = models.ForeignKey(Modulo, on_delete=models.SET_NULL, null=True, blank=True)
    completado = models.BooleanField(default=False)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)
    fecha_ultimo_avance = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha último avance',
        help_text='Se actualiza cuando el estudiante completa/avanza de módulo.'
    )
    paso_actual_modulo = models.PositiveIntegerField(
        default=1,
        help_text='Índice 1-based del siguiente paso a entregar con *listo* (solo si el módulo tiene pasos activos).',
    )
    esperando_respuesta_evaluacion_paso = models.BooleanField(default=False)
    paso_evaluacion_paso = models.ForeignKey(
        PasoModulo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        verbose_name = "Progreso de Estudiante"
        verbose_name_plural = "Progreso de Estudiantes"
        unique_together = ['estudiante', 'curso']

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.curso.nombre}"

    def porcentaje_avance(self):
        """Calcula el porcentaje de avance en el curso"""
        total_modulos = self.curso.modulos.count()
        if total_modulos == 0:
            return 0
        modulos_completados = self.modulos_completados.count()
        return int((modulos_completados / total_modulos) * 100)


class PreguntaModulo(models.Model):
    """Pregunta de validación al final de cada módulo (mini examen)"""
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='preguntas')
    pregunta = models.TextField(help_text="Pregunta de validación del aprendizaje")
    
    # Opciones de respuesta (opción múltiple)
    opcion_a = models.CharField(max_length=500)
    opcion_b = models.CharField(max_length=500)
    opcion_c = models.CharField(max_length=500, blank=True, null=True)
    opcion_d = models.CharField(max_length=500, blank=True, null=True)
    
    respuesta_correcta = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
        help_text="Letra de la respuesta correcta"
    )
    
    explicacion = models.TextField(
        blank=True,
        help_text="Explicación de la respuesta correcta (opcional)"
    )
    
    activa = models.BooleanField(
        default=True,
        help_text="Si está desactivada, no se mostrará"
    )

    class Meta:
        verbose_name = "Pregunta de Módulo"
        verbose_name_plural = "Preguntas de Módulos"
        ordering = ['modulo', 'id']

    def __str__(self):
        return f"{self.modulo.titulo} - {self.pregunta[:50]}..."


class ModuloCompletado(models.Model):
    """Registro de módulos completados por el estudiante"""
    progreso = models.ForeignKey(ProgresoEstudiante, on_delete=models.CASCADE, related_name='modulos_completados')
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    fecha_completado = models.DateTimeField(auto_now_add=True)
    
    # Respuesta al mini examen
    pregunta_respondida = models.ForeignKey(
        PreguntaModulo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Pregunta que se le hizo al completar"
    )
    respuesta_dada = models.CharField(
        max_length=1, 
        blank=True,
        help_text="A, B, C o D"
    )
    respuesta_correcta = models.BooleanField(
        default=False,
        help_text="Si respondió correctamente"
    )

    class Meta:
        verbose_name = "Módulo Completado"
        verbose_name_plural = "Módulos Completados"
        unique_together = ['progreso', 'modulo']

    def __str__(self):
        return f"{self.progreso.estudiante.nombre} completó {self.modulo.titulo}"


class Examen(models.Model):
    """Examen final del curso"""
    curso = models.OneToOneField(Curso, on_delete=models.CASCADE, related_name='examen')
    instrucciones = models.TextField(default="Responde las siguientes preguntas sobre el curso:")
    puntaje_minimo = models.IntegerField(default=70, help_text="Puntaje mínimo para aprobar (0-100)")

    class Meta:
        verbose_name = "Examen"
        verbose_name_plural = "Exámenes"

    def __str__(self):
        return f"Examen de {self.curso.nombre}"

    def total_preguntas(self):
        return self.preguntas.count()


class PreguntaExamen(models.Model):
    """Pregunta del examen"""
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE, related_name='preguntas')
    numero = models.IntegerField(help_text="Número de la pregunta")
    pregunta = models.TextField(help_text="Texto de la pregunta")
    respuesta_correcta = models.TextField(
        help_text="Palabras clave o conceptos esperados en la respuesta (separados por comas)"
    )
    puntos = models.IntegerField(default=20, help_text="Puntos que vale esta pregunta")

    class Meta:
        ordering = ['examen', 'numero']
        verbose_name = "Pregunta de Examen"
        verbose_name_plural = "Preguntas de Examen"
        unique_together = ['examen', 'numero']

    def __str__(self):
        return f"Pregunta {self.numero} - {self.examen.curso.nombre}"


class ResultadoExamen(models.Model):
    """Resultado del examen del estudiante"""
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='resultados_examenes')
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE)
    puntaje = models.IntegerField(default=0, help_text="Puntaje obtenido (0-100)")
    aprobado = models.BooleanField(default=False)
    respuestas = models.JSONField(default=dict, help_text="Diccionario con las respuestas del estudiante")
    feedback = models.TextField(blank=True, help_text="Retroalimentación generada por IA")
    fecha_realizado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Resultado de Examen"
        verbose_name_plural = "Resultados de Exámenes"
        unique_together = ['estudiante', 'examen']

    def __str__(self):
        estado = "Aprobado" if self.aprobado else "Reprobado"
        return f"{self.estudiante.nombre} - {self.examen.curso.nombre} - {self.puntaje}% {estado}"


# ========== SISTEMA DE EVALUACIÓN EDUCATIVA ==========

class ObjetivoCurso(models.Model):
    """Objetivos de aprendizaje del curso (general y específicos)"""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='objetivos')
    tipo = models.CharField(
        max_length=20,
        choices=[('general', 'General'), ('especifico', 'Específico')],
        default='especifico',
        verbose_name='Tipo de Objetivo'
    )
    orden = models.IntegerField(default=0, help_text='Orden del objetivo')
    descripcion = models.TextField(help_text='Descripción del objetivo de aprendizaje')
    peso_evaluacion = models.IntegerField(
        default=25,
        help_text='Peso porcentual de este objetivo en la evaluación (0-100)'
    )
    
    class Meta:
        verbose_name = 'Objetivo de Curso'
        verbose_name_plural = 'Objetivos de Cursos'
        ordering = ['curso', 'orden']
    
    def __str__(self):
        return f"{self.curso.nombre} - {self.get_tipo_display()}: {self.descripcion[:50]}"


class RubricaEvaluacion(models.Model):
    """Rúbrica para evaluar ejercicios y respuestas abiertas"""
    objetivo = models.ForeignKey(
        ObjetivoCurso,
        on_delete=models.CASCADE,
        related_name='rubricas',
        null=True,
        blank=True,
        help_text='Objetivo al que pertenece esta rúbrica'
    )
    nombre = models.CharField(max_length=200, help_text='Nombre de la rúbrica')
    descripcion = models.TextField(help_text='Descripción de qué evalúa')
    criterios = models.JSONField(
        default=dict,
        help_text='Criterios de evaluación en formato JSON: {"criterio1": {"excelente": 100, "bueno": 75, "regular": 50, "insuficiente": 25}}'
    )
    palabras_clave = models.TextField(
        blank=True,
        help_text='Palabras clave esperadas en respuestas correctas (separadas por comas)'
    )
    activa = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Rúbrica de Evaluación'
        verbose_name_plural = 'Rúbricas de Evaluación'
    
    def __str__(self):
        return self.nombre


class EjercicioPractico(models.Model):
    """Ejercicios prácticos y situaciones hipotéticas para evaluación"""
    TIPO_CHOICES = [
        ('numerico', 'Numérico (cálculos)'),
        ('abierto', 'Respuesta Abierta'),
        ('hipotetico', 'Situación Hipotética'),
        ('comprension', '¿Entendiste? (comprensión)'),
    ]
    
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.CASCADE,
        related_name='ejercicios',
        null=True,
        blank=True
    )
    objetivo = models.ForeignKey(
        ObjetivoCurso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ejercicios'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='comprension')
    enunciado = models.TextField(help_text='Texto del ejercicio o situación hipotética')
    contexto_previo = models.TextField(
        blank=True,
        help_text='Contexto o información necesaria para resolver el ejercicio'
    )
    
    # Para ejercicios numéricos
    respuesta_numerica_esperada = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Respuesta numérica correcta (ej: utilidad esperada)'
    )
    tolerancia_porcentual = models.IntegerField(
        default=5,
        help_text='Tolerancia de error aceptable en porcentaje (ej: 5 = ±5%)'
    )
    formula_evaluacion = models.TextField(
        blank=True,
        help_text='Fórmula o criterio para evaluar (ej: "ingresos - costos = utilidad")'
    )
    
    # Para ejercicios abiertos
    rubrica = models.ForeignKey(
        RubricaEvaluacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ejercicios'
    )
    
    puntaje_maximo = models.IntegerField(default=100, help_text='Puntaje máximo del ejercicio')
    tiempo_estimado_minutos = models.IntegerField(
        default=5,
        help_text='Tiempo estimado para completar (minutos)'
    )
    orden = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Ejercicio Práctico'
        verbose_name_plural = 'Ejercicios Prácticos'
        ordering = ['modulo', 'orden']
    
    def __str__(self):
        modulo_str = f"{self.modulo.titulo}" if self.modulo else "Sin módulo"
        return f"{modulo_str} - {self.get_tipo_display()}: {self.enunciado[:50]}"


class RespuestaEjercicio(models.Model):
    """Respuestas de estudiantes a ejercicios prácticos"""
    ejercicio = models.ForeignKey(
        EjercicioPractico,
        on_delete=models.CASCADE,
        related_name='respuestas'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='respuestas_ejercicios'
    )
    intento = models.IntegerField(default=1, help_text='Número de intento')
    
    # Respuesta del estudiante
    respuesta_texto = models.TextField(blank=True, help_text='Respuesta en texto')
    respuesta_numerica = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Respuesta numérica si aplica'
    )
    respuesta_audio_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='URL del audio de respuesta (si respondió por audio)'
    )
    
    # Evaluación
    puntaje_obtenido = models.IntegerField(default=0, help_text='Puntaje obtenido (0-100)')
    es_correcto = models.BooleanField(default=False)
    feedback_ia = models.TextField(
        blank=True,
        help_text='Retroalimentación generada por la IA'
    )
    evaluado_por_ia = models.BooleanField(default=False)
    evaluado_por_docente = models.BooleanField(default=False)
    
    # Metadata
    tiempo_respuesta_segundos = models.IntegerField(
        null=True,
        blank=True,
        help_text='Tiempo que tardó en responder'
    )
    modalidad = models.CharField(
        max_length=10,
        choices=[('texto', 'Texto'), ('audio', 'Audio'), ('mixto', 'Mixto')],
        default='texto'
    )
    fecha_respuesta = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Respuesta a Ejercicio'
        verbose_name_plural = 'Respuestas a Ejercicios'
        ordering = ['-fecha_respuesta']
        unique_together = ['ejercicio', 'estudiante', 'intento']
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.ejercicio.enunciado[:30]} (Intento {self.intento})"


class InteraccionLog(models.Model):
    """Log completo de interacciones para análisis de métricas"""
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='interacciones'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interacciones'
    )
    modulo = models.ForeignKey(
        Modulo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interacciones'
    )
    
    # Tipo de interacción
    tipo = models.CharField(
        max_length=30,
        choices=[
            ('pregunta', 'Pregunta'),
            ('reto', 'Reto'),
            ('ejercicio', 'Ejercicio'),
            ('examen', 'Examen'),
            ('consulta', 'Consulta General'),
            ('comprension', 'Pregunta de Comprensión'),
        ],
        default='consulta'
    )
    
    # Modalidad y duración
    modalidad = models.CharField(
        max_length=10,
        choices=[('texto', 'Texto'), ('audio', 'Audio'), ('mixto', 'Mixto')],
        default='texto'
    )
    duracion_segundos = models.IntegerField(
        null=True,
        blank=True,
        help_text='Duración de la interacción en segundos'
    )
    
    # Evaluación (si aplica)
    puntaje = models.IntegerField(
        null=True,
        blank=True,
        help_text='Puntaje obtenido (0-100)'
    )
    es_correcto = models.BooleanField(
        null=True,
        blank=True,
        help_text='Si la respuesta fue correcta'
    )
    
    # Contenido
    respuesta_raw = models.TextField(
        blank=True,
        help_text='Respuesta original del estudiante'
    )
    feedback_generado = models.TextField(
        blank=True,
        help_text='Retroalimentación generada'
    )
    intent = models.CharField(
        max_length=50,
        blank=True,
        help_text='Intención detectada (si aplica NLU)'
    )
    
    # Ubicación (para análisis geográfico)
    municipio = models.CharField(
        max_length=100,
        blank=True,
        help_text='Municipio del estudiante'
    )
    
    # Metadata adicional
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Metadata adicional en formato JSON'
    )
    
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Interacción Log'
        verbose_name_plural = 'Logs de Interacciones'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['estudiante', 'fecha']),
            models.Index(fields=['curso', 'fecha']),
            models.Index(fields=['municipio', 'fecha']),
            models.Index(fields=['modalidad', 'fecha']),
        ]
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.get_tipo_display()} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"


# ========== SOPORTE Y ATENCIÓN AL CLIENTE ==========

class SolicitudSoporte(models.Model):
    """Solicitudes de soporte/ayuda de estudiantes y PQRS unificado"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_atencion', 'En Atención'),
        ('resuelta', 'Resuelta'),
        ('cerrada', 'Cerrada'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('baja', '🟢 Baja'),
        ('media', '🟡 Media'),
        ('alta', '🔴 Alta'),
        ('critica', '🚨 Crítica'),
    ]
    
    TIPO_SOLICITUD_CHOICES = [
        ('soporte', '🆘 Soporte (Botón de Pánico)'),
        ('peticion', '📋 Petición'),
        ('queja', '😤 Queja'),
        ('reclamo', '📢 Reclamo'),
        ('sugerencia', '💡 Sugerencia'),
        ('felicitacion', '🌟 Felicitación'),
    ]

    CATEGORIA_PQRS_CHOICES = [
        ('', '— Sin clasificar'),
        ('acceso', '🔑 Acceso (login, cédula, número)'),
        ('contenido', '📚 Contenido (módulo, video, examen)'),
        ('tecnico', '🛠️ Técnico (errores del sistema)'),
        ('duda_modulo', 'Duda de módulo'),
        ('problema_acceso', 'Problema de acceso'),
        ('solicitud_certificado', 'Solicitud de certificado'),
        ('consulta_calculo', 'Consulta de cálculo'),
        ('correccion_datos', 'Corrección de datos'),
        ('problema_tecnico', 'Problema técnico'),
        ('conversacion_escalada', 'Conversación escalada'),
        ('pregunta_sin_respuesta', 'Pregunta sin respuesta'),
        ('queja', 'Queja'),
        ('otro', '❓ Otro'),
    ]

    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_PQRS_CHOICES,
        blank=True,
        default='',
        verbose_name='Categoría PQRS',
        help_text='Clasificación automática del agente PQRS (acceso, contenido, técnico, otro).',
    )
    resuelto_por_agente = models.BooleanField(
        default=False,
        verbose_name='Resuelto por agente IA',
        help_text='True si el agente PQRS resolvió en primer nivel; False si quedó escalado.',
    )
    preguntas_realizadas = models.IntegerField(
        default=0,
        verbose_name='Preguntas de clarificación',
        help_text='Preguntas de clarificación del agente PQRS (máximo 2 por ticket).',
    )

    tipo_solicitud = models.CharField(
        max_length=20,
        choices=TIPO_SOLICITUD_CHOICES,
        default='soporte',
        verbose_name='Tipo de Solicitud',
        help_text='Tipo: soporte técnico o PQRS'
    )
    asunto = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Asunto',
        help_text='Asunto de la solicitud (opcional para soporte, recomendado para PQRS)'
    )
    curso_relacionado = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Curso Relacionado',
        help_text='Curso relacionado con la solicitud (opcional)'
    )
    calificacion = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Calificación',
        help_text='Del 1 al 5, otorgada por el estudiante'
    )
    comentario_calificacion = models.TextField(
        blank=True,
        verbose_name='Comentario de Calificación'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='solicitudes_soporte',
        verbose_name='Estudiante'
    )
    mensaje_original = models.TextField(
        verbose_name='Mensaje del Estudiante',
        help_text='El mensaje que envió el estudiante pidiendo ayuda'
    )
    keyword_usada = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Palabra Clave',
        help_text='Keyword que activó el soporte (AYUDA, SOPORTE, HUMANO, etc.)'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado'
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default='media',
        verbose_name='Prioridad'
    )
    respuesta = models.TextField(
        blank=True,
        verbose_name='Respuesta del Equipo',
        help_text='Respuesta que se le dio al estudiante'
    )
    respuesta_portal = models.TextField(
        null=True,
        blank=True,
        verbose_name='Respuesta desde portal',
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de respuesta desde portal',
    )
    respondido_por = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='pqrs_respondidas',
        verbose_name='Respondido por',
    )
    atendido_por = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Atendido Por',
        help_text='Nombre del miembro del equipo que atendió'
    )
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Solicitud'
    )
    fecha_atencion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Atención'
    )
    fecha_resolucion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Resolución'
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name='Notas Internas',
        help_text='Notas privadas del equipo (no visible para el estudiante)'
    )
    
    class Meta:
        verbose_name = 'Solicitud de Soporte y PQRS'
        verbose_name_plural = 'Soporte y PQRS'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado', 'prioridad']),
            models.Index(fields=['estudiante', 'fecha_solicitud']),
            models.Index(fields=['tipo_solicitud', 'estado']),
        ]
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.get_estado_display()} - {self.fecha_solicitud.strftime('%d/%m/%Y')}"


# ========== GAMIFICACIÓN ==========
# Importar modelos de gamificación desde archivo separado
from .gamificacion import (
    PerfilGamificacion,
    Badge,
    BadgeEstudiante,
    TransaccionPuntos,
    EvaluacionNotaGamificacion,
)

# ========== CERTIFICADOS ==========
# Importar modelos de certificados desde archivo separado
from .models_certificados import Certificado, PlantillaCertificado

# ========== AUDITORÍA ==========
# Importar modelos de auditoría desde archivo separado
from .models_audit import AuditLog

# ========== NUEVAS FUNCIONALIDADES ==========
# Importar modelos adicionales
from .models_extras import (
    GrupoEstudiantes, EnvioProgramado, PQRS, 
    ArchivoModulo, GrupoWhatsApp, InvitacionGrupo,
    MensajePush, EnvioMensajePush,
)

# ========== CAMPAÑAS ÚNICAS (SÍ/NO) ==========
class CampanaUnica(models.Model):
    """Campañas de una sola vez con botones (sí/no)"""
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
        ('completada', 'Completada'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la campaña")
    contenido = models.TextField(verbose_name="Contenido del mensaje", help_text="Texto que acompaña los botones SÍ/NO")
    template_twilio_id = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name="Content SID de Twilio",
        help_text="El SID del template aprobado en Twilio (ej: HX123abc...)"
    )
    
    # Selección de estudiantes (si vacío = todos los del cliente)
    estudiantes = models.ManyToManyField(
        'Estudiante', blank=True,
        verbose_name="Estudiantes destinatarios",
        help_text="Selecciona estudiantes específicos. Si dejas vacío, se enviará a TODOS los estudiantes activos del cliente."
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de envío")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador', verbose_name="Estado")
    
    # Estadísticas
    total_enviados = models.IntegerField(default=0, verbose_name="Total enviados")
    respuestas_si = models.IntegerField(default=0, verbose_name="Respuestas SÍ")
    respuestas_no = models.IntegerField(default=0, verbose_name="Respuestas NO")
    
    class Meta:
        verbose_name = "Campaña Única"
        verbose_name_plural = "Campañas Únicas"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.nombre} - {self.get_estado_display()}"


class RespuestaCampanaUnica(models.Model):
    """Guarda cada respuesta (sí/no) y el número del estudiante"""
    RESPUESTA_CHOICES = [
        ('si', 'Sí'),
        ('no', 'No'),
    ]
    
    campana = models.ForeignKey(CampanaUnica, on_delete=models.CASCADE, related_name='respuestas', verbose_name="Campaña")
    estudiante = models.ForeignKey(Estudiante, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Estudiante")
    
    numero_telefono = models.CharField(max_length=20, verbose_name="Número de teléfono")
    respuesta = models.CharField(max_length=5, choices=RESPUESTA_CHOICES, verbose_name="Respuesta")
    
    fecha_respuesta = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de respuesta")
    mensaje_sid = models.CharField(max_length=100, null=True, blank=True, verbose_name="Message SID de Twilio")
    
    class Meta:
        verbose_name = "Respuesta Campaña Única"
        verbose_name_plural = "Respuestas Campañas Únicas"
        ordering = ['-fecha_respuesta']
        unique_together = ['campana', 'numero_telefono']  # Un estudiante solo responde una vez
    
    def __str__(self):
        return f"{self.numero_telefono} - {self.get_respuesta_display()}"


# ========== PROSPECTOS B2B (Lead Generation) ==========
class ProspectoB2B(models.Model):
    """Prospectos B2B capturados por el bot cuando un número no registrado escribe."""
    ESTADO_CHOICES = [
        ('nuevo', 'Nuevo'),
        ('contactado', 'Contactado'),
        ('en_negociacion', 'En Negociación'),
        ('convertido', 'Convertido a Cliente'),
        ('descartado', 'Descartado'),
    ]
    
    ORIGEN_CHOICES = [
        ('whatsapp_bot', 'Bot WhatsApp'),
        ('web', 'Sitio Web'),
        ('referido', 'Referido'),
        ('otro', 'Otro'),
    ]
    
    telefono = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Teléfono WhatsApp',
        help_text='Número de teléfono del prospecto'
    )
    nombre_contacto = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre del Contacto'
    )
    email = models.EmailField(
        blank=True,
        verbose_name='Email',
        help_text='Correo electrónico del prospecto'
    )
    empresa = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Empresa',
        help_text='Nombre de la empresa del prospecto'
    )
    mensaje_original = models.TextField(
        blank=True,
        verbose_name='Mensaje Original',
        help_text='Primer mensaje que envió el prospecto'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='nuevo',
        verbose_name='Estado del Lead'
    )
    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_CHOICES,
        default='whatsapp_bot',
        verbose_name='Origen'
    )
    notas = models.TextField(
        blank=True,
        verbose_name='Notas de Seguimiento'
    )
    
    # Estado del chat con el prospecto
    esperando_email = models.BooleanField(
        default=False,
        verbose_name='Esperando Email',
        help_text='Si el bot está esperando que el prospecto envíe su email'
    )
    
    fecha_captura = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Captura'
    )
    fecha_ultimo_contacto = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último Contacto'
    )
    
    class Meta:
        verbose_name = 'Prospecto B2B'
        verbose_name_plural = 'Prospectos B2B (Leads)'
        ordering = ['-fecha_captura']
    
    def __str__(self):
        return f"{self.telefono} - {self.empresa or 'Sin empresa'} ({self.get_estado_display()})"


class CampanaB2B(models.Model):
    """Campañas de envío masivo para prospectos B2B — solo envío, sin registro."""
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
    ]
    
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre de la Campaña',
        help_text='Ej: Propuesta Café Huila 2026'
    )
    mensaje = models.TextField(
        verbose_name='Mensaje de texto',
        help_text='Texto del mensaje a enviar. Usa {nombre} para personalizar con el nombre del prospecto.',
        blank=True,
        default=''
    )
    twilio_template_sid = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Content SID de Twilio (opcional)',
        help_text='Si se especifica, se envía este template en lugar del mensaje de texto.'
    )
    url_media = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='URL del PDF/Media (opcional)',
        help_text='URL pública del PDF o archivo a adjuntar. Debe ser accesible públicamente.'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='borrador'
    )
    total_enviados = models.IntegerField(default=0)
    total_errores = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Campaña B2B'
        verbose_name_plural = 'Campañas B2B'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"


class AliadoEmpleabilidad(models.Model):
    """Empresas aliadas para gamificación geolocalizada de empleabilidad."""
    nombre_empresa = models.CharField(max_length=200, verbose_name='Nombre de la empresa')
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aliados_empleabilidad',
        verbose_name='Cliente asociado',
        help_text='Opcional. Si se define, solo aplica para estudiantes de ese cliente.'
    )
    latitud = models.FloatField(verbose_name='Latitud')
    longitud = models.FloatField(verbose_name='Longitud')
    cupos_disponibles = models.PositiveIntegerField(
        default=0,
        verbose_name='Cupos disponibles',
        help_text='Vacantes disponibles para priorización del radar de empleabilidad.'
    )
    prioridad = models.PositiveSmallIntegerField(
        default=3,
        verbose_name='Prioridad (1-5)',
        help_text='5 = máxima prioridad para aparecer en el radar de oportunidades.'
    )
    vigencia_desde = models.DateField(
        null=True,
        blank=True,
        verbose_name='Vigencia desde',
        help_text='Fecha de inicio de vigencia de la oportunidad.'
    )
    vigencia_hasta = models.DateField(
        null=True,
        blank=True,
        verbose_name='Vigencia hasta',
        help_text='Fecha de fin de vigencia de la oportunidad.'
    )
    vacantes_activas = models.BooleanField(default=True, verbose_name='Vacantes activas')
    codigo_secreto = models.CharField(max_length=120, verbose_name='Código secreto')
    indicacion_sector = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Indicación de sector',
        help_text='Ej: costado oriental del parque principal'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aliado de Empleabilidad'
        verbose_name_plural = 'Aliados de Empleabilidad'
        ordering = ['nombre_empresa']

    def __str__(self):
        return self.nombre_empresa


class MisionEmpleabilidad(models.Model):
    """Misiones de exploración/validación de oportunidades por proximidad."""

    ESTADO_CHOICES = [
        ('descubierta', 'Descubierta'),
        ('reclamada', 'Reclamada'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    FLUJO_CHOICES = [
        ('descubierto', 'Descubierto'),
        ('interesado', 'Interesado'),
        ('postulado', 'Postulado'),
        ('entrevista', 'Entrevista'),
        ('vinculado', 'Vinculado'),
        ('descartado', 'Descartado'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='misiones_empleabilidad',
        verbose_name='Cliente'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='misiones_empleabilidad',
        verbose_name='Estudiante'
    )
    aliado = models.ForeignKey(
        AliadoEmpleabilidad,
        on_delete=models.CASCADE,
        related_name='misiones_empleabilidad',
        verbose_name='Aliado'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='descubierta', verbose_name='Estado')
    latitud = models.FloatField(null=True, blank=True, verbose_name='Latitud referencia')
    longitud = models.FloatField(null=True, blank=True, verbose_name='Longitud referencia')
    distancia_metros = models.FloatField(null=True, blank=True, verbose_name='Distancia en metros')
    codigo_validado = models.BooleanField(default=False, verbose_name='Código validado')
    puntos_otorgados = models.IntegerField(default=0, verbose_name='Puntos otorgados')
    estado_flujo = models.CharField(
        max_length=20,
        choices=FLUJO_CHOICES,
        default='descubierto',
        verbose_name='Estado del embudo'
    )
    puntaje_prioridad = models.FloatField(
        default=0,
        verbose_name='Puntaje de priorización',
        help_text='Score calculado para priorizar oportunidades en el radar.'
    )
    canal_origen = models.CharField(
        max_length=40,
        default='whatsapp',
        verbose_name='Canal origen'
    )
    metadata = models.JSONField(null=True, blank=True, help_text='Datos adicionales de misión (debug/contexto).')

    fecha_descubierta = models.DateTimeField(auto_now_add=True)
    fecha_reclamada = models.DateTimeField(null=True, blank=True)
    fecha_completada = models.DateTimeField(null=True, blank=True)
    fecha_interes = models.DateTimeField(null=True, blank=True)
    fecha_postulacion = models.DateTimeField(null=True, blank=True)
    fecha_entrevista = models.DateTimeField(null=True, blank=True)
    fecha_vinculacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Misión de Empleabilidad'
        verbose_name_plural = 'Misiones de Empleabilidad'
        ordering = ['-fecha_descubierta']
        indexes = [
            models.Index(fields=['estudiante', 'estado', 'fecha_descubierta']),
            models.Index(fields=['cliente', 'estado', 'fecha_descubierta']),
            models.Index(fields=['aliado', 'estado']),
            models.Index(fields=['cliente', 'estado_flujo', 'fecha_descubierta']),
        ]

    def __str__(self):
        return f"{self.estudiante.nombre} -> {self.aliado.nombre_empresa} ({self.get_estado_display()})"


class PreguntaAbiertaFinalCurso(models.Model):
    """Pregunta abierta opcional al final del curso, evaluada por facilitadora."""
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='preguntas_abiertas_finales'
    )
    orden = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Orden',
        help_text='Orden de la pregunta en el cierre (1 a 3).'
    )
    pregunta = models.TextField(verbose_name='Pregunta abierta final')
    activa = models.BooleanField(default=True, verbose_name='Activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pregunta Abierta Final'
        verbose_name_plural = 'Preguntas Abiertas Finales'
        ordering = ['curso', 'orden', 'id']
        unique_together = ['curso', 'orden']

    def __str__(self):
        return f"Pregunta final #{self.orden} - {self.curso.nombre}"

    def clean(self):
        super().clean()
        if self.orden < 1 or self.orden > 3:
            raise ValidationError({'orden': 'El orden debe estar entre 1 y 3.'})

        existentes = PreguntaAbiertaFinalCurso.objects.filter(curso=self.curso)
        if self.pk:
            existentes = existentes.exclude(pk=self.pk)
        if existentes.count() >= 3:
            raise ValidationError('Cada curso permite máximo 3 preguntas abiertas finales.')


class RespuestaAbiertaFinal(models.Model):
    """Respuesta del estudiante a la pregunta abierta final (calificada por facilitadora)."""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de calificar'),
        ('calificada', 'Calificada'),
    ]

    pregunta = models.ForeignKey(
        PreguntaAbiertaFinalCurso,
        on_delete=models.CASCADE,
        related_name='respuestas'
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='respuestas_abiertas_finales'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='respuestas_abiertas_finales'
    )
    progreso = models.ForeignKey(
        ProgresoEstudiante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_abiertas_finales'
    )
    respuesta_texto = models.TextField(verbose_name='Respuesta del estudiante')
    fecha_respuesta = models.DateTimeField(default=timezone.now)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    calificacion = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Calificación (0-100)'
    )
    retroalimentacion = models.TextField(blank=True, default='', verbose_name='Retroalimentación facilitadora')
    calificada_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calificaciones_preguntas_abiertas'
    )
    fecha_calificacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Respuesta Abierta Final'
        verbose_name_plural = 'Respuestas Abiertas Finales'
        ordering = ['-fecha_respuesta']
        unique_together = ['pregunta', 'estudiante']

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.curso.nombre}"


class ConfiguracionGlobal(models.Model):
    """Singleton de configuración general de eki, editable desde el admin.

    Solo debe existir una fila (id=1). El método `get_solo()` la crea si falta.
    """
    content_sid_habeas_data_global = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Habeas Data — Plantilla Twilio general (Content SID)',
        help_text=(
            'Content SID (HX...) de la plantilla Twilio aprobada para el Habeas Data por defecto. '
            'Se usa cuando el cliente no tiene su propio Content SID configurado.'
        ),
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Configuración Global'
        verbose_name_plural = 'Configuración Global'

    def __str__(self):
        return 'Configuración Global eki'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


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


__all__ = [
    'TemaCampana', 'Cliente', 'Estudiante', 'Plantilla', 'Linea',
    'Campana', 'EnvioLog', 'WhatsappLog',
    'SesionComercial',
    'Curso', 'ConfiguracionDripCliente', 'HabilitacionModuloDripCliente',
    'HabilitacionModuloEstudiante', 'DocumentoRAG', 'DocumentoRAGComercial', 'Modulo',
    'ProgresoEstudiante', 'ModuloCompletado',
    'Examen', 'PreguntaExamen', 'ResultadoExamen',
    'ObjetivoCurso', 'RubricaEvaluacion', 'EjercicioPractico', 'RespuestaEjercicio',
    'InteraccionLog', 'SolicitudSoporte', 'PreguntaModulo',
    'PerfilGamificacion', 'Badge', 'BadgeEstudiante', 'TransaccionPuntos',
    'EvaluacionNotaGamificacion',
    'Certificado', 'PlantillaCertificado',
    'AuditLog',
    'GrupoEstudiantes', 'EnvioProgramado', 'PQRS',
    'ArchivoModulo', 'GrupoWhatsApp', 'InvitacionGrupo',
    'CampanaUnica', 'RespuestaCampanaUnica',
    'ProspectoB2B', 'CampanaB2B',
    'AliadoEmpleabilidad', 'MisionEmpleabilidad', 'PreguntaAbiertaFinalCurso', 'RespuestaAbiertaFinal',
    'ConfiguracionGlobal',
    'EventoIA',
    'ContextoAgroSession',
    'ConversacionRAGCandidata',
    'ProductoComercial',
    'ProductoCatalogo',
]
