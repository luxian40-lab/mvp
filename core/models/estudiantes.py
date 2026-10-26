"""Modelos de estudiantes (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.documento_identidad import TIPO_DOCUMENTO_CHOICES
from core.models.clientes import Cliente


# 1. ESTUDIANTE
class Estudiante(models.Model):
    TIPO_DOCUMENTO_CHOICES = TIPO_DOCUMENTO_CHOICES

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
        max_length=8,
        choices=TIPO_DOCUMENTO_CHOICES,
        default='CC',
        verbose_name='Tipo de Documento',
        help_text='Tipo de documento (CC Colombia, DUI El Salvador, CURP/INE México, DNI, RUT, etc.)'
    )
    cedula = models.CharField(
        max_length=32,
        unique=True,
        verbose_name='Número de Documento',
        help_text='Número/ID único (cédula, DUI, CURP, DNI…). Sin puntos ni espacios; puede incluir letras.'
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
    territory_id = models.CharField(
        max_length=10,
        blank=True,
        default='',
        db_index=True,
        verbose_name='Territory ID (DIVIPOLA)',
        help_text='Código DIVIPOLA de 5 dígitos del municipio canónico. Vacío si no resuelto.',
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
    rural_disperso = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Rural disperso',
        help_text='Corte de impacto. Vacío = desconocido. No cambia el chat.',
    )
    pdet = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Municipio PDET',
        help_text='Corte de impacto. Vacío = desconocido. No cambia el chat.',
    )
    consentimiento_impacto = models.BooleanField(
        default=False,
        verbose_name='Consentimiento para reportes de impacto',
        help_text='Distinto del habeas operativo. Hace falta para incluir a esta persona en Impacto.',
    )
    consentimiento_impacto_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha del consentimiento de impacto',
    )
    consentimiento_impacto_acudiente = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Acudiente (menores)',
    )
    area_unidad_ha = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Área de la unidad (ha)',
        help_text='Para A2 cuando exista práctica adoptada. No se publica como causa.',
    )
    impacto_respuestas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Respuestas de impacto (agentes)',
        help_text='Captura B por código (E1, E2, A1, A3). No se inventa el dato.',
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
    wa_optin_fecha = models.DateTimeField(null=True, blank=True)
    wa_optin_version = models.CharField(max_length=32, blank=True, default='')
    wa_optin_origen = models.CharField(max_length=32, blank=True, default='')
    wa_optout_fecha = models.DateTimeField(null=True, blank=True)
    
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
        from core.documento_identidad import (
            normalizar_numero_documento,
            normalizar_tipo_documento,
        )
        from core.utils_telefono import normalizar_telefono

        # Teléfono: solo dígitos; 57 automático solo si parece móvil CO (10 dígitos que empiezan en 3).
        self.telefono = normalizar_telefono(self.telefono)

        self.tipo_documento = normalizar_tipo_documento(self.tipo_documento)
        if self.cedula and not str(self.cedula).startswith('TEMP_'):
            self.cedula = normalizar_numero_documento(self.cedula)

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
        return f"{self.nombre} ({self.tipo_documento}: {self.cedula})"
