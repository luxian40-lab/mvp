"""Modelos de clientes (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from django.db.models import Q
from core.models.opciones import PLAN_CHOICES as PLAN_LINEA_CHOICES


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
        default='Formador',
        verbose_name='Nombre del formador',
        help_text='En todos los cursos se llama Formador.'
    )
    nombre_agente_asistente = models.CharField(
        max_length=100,
        blank=True,
        default='Compañero',
        verbose_name='Nombre del compañero',
        help_text='En todos los cursos se llama Compañero.'
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
    desactivar_llm_comercial = models.BooleanField(
        default=False,
        verbose_name='Kill switch LLM (eki.ia)',
        help_text=(
            'Si está marcado, eki.ia/Nat no llama al modelo de lenguaje: responde con '
            'catálogo, biblioteca/RAG y mensajes fijos (Plan B). Útil en incidente o costo. '
            'También existe el interruptor global EKI_IA_LLM_DISABLED en el servidor.'
        ),
    )
    PERFIL_FACILITADOR_CLAUDIA = 'claudia'
    PERFIL_FACILITADOR_TECNICOAGRO = 'tecnicoagro'
    PERFIL_FACILITADOR_CHOICES = [
        (PERFIL_FACILITADOR_CLAUDIA, 'Claudia (facilitadora ABR eki)'),
        (PERFIL_FACILITADOR_TECNICOAGRO, 'tecnicoagro (copiloto extensión AGROSAVIA)'),
    ]
    perfil_facilitador = models.CharField(
        max_length=20,
        choices=PERFIL_FACILITADOR_CHOICES,
        default=PERFIL_FACILITADOR_CLAUDIA,
        verbose_name='Facilitador de retos (WhatsApp)',
        help_text=(
            'Quién plantea y evalúa los retos tras checkpoints. '
            'Claudia = default eki. tecnicoagro = copiloto técnico AGROSAVIA (mismo flujo, otro prompt). '
            'Los cursos pueden sobreescribir este valor.'
        ),
    )
    numero_whatsapp_nat = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name='Número WhatsApp Nat (línea comercial)',
        help_text=(
            'Número Twilio al que escribe el productor para hablar con Nat (solo dígitos, ej: 573001234567). '
            'Debe coincidir exactamente con el campo To del webhook; si no, el mensaje irá al bot educativo. '
            'Cada organización puede tener su propia línea. '
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
    phone_id_meta = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Phone number id de su línea',
        help_text=(
            'Id del número en Meta (WhatsApp Manager → Phone numbers). '
            'Solo indica que ese número es de esta empresa. '
            'Los cursos y los agentes se eligen aparte. Vacío = no tiene línea propia.'
        ),
    )
    agentes_linea = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='Agentes en esta línea',
        help_text='Lo escriben las casillas del formulario. Vacío = los cinco agentes.',
    )
    cursos_whatsapp = models.ManyToManyField(
        'Curso',
        blank=True,
        related_name='clientes_en_linea',
        verbose_name='Cursos en WhatsApp',
        help_text=(
            'Cursos generales de eki y los de esta empresa. '
            'Vacío = en su línea propia salen los cursos de la empresa; '
            'en la línea principal sigue el catálogo general. '
            'De 2 a 10 salen en carrusel. Más de 10, en lista.'
        ),
    )
    plan_linea_meta = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=PLAN_LINEA_CHOICES,
        verbose_name='Plan línea Meta',
        help_text=(
            'Plan de quienes no estén en un grupo con plan propio. Vacío = sin plan '
            '(no abren cursos nuevos ni usan el asesor). Un grupo puede llevar OP1 '
            'y otro OP2. Una persona se cambia en «Sesiones menú sandbox».'
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
    wallpaper_aula_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='URL del wallpaper (Aprende)',
        help_text=(
            'Se completa sola al subir el archivo en admin. '
            'JPG/WebP ≤ 2 MB, ancho ≥ 1600px. Vacío = fondo eki por defecto.'
        ),
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
    es_demo = models.BooleanField(
        default=False,
        verbose_name='Es demo o prueba',
        help_text='Marca organizaciones de prueba. No cambia envíos ni permisos.',
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

    @property
    def contacto_soporte_texto(self) -> str:
        """Líneas de contacto para derivar consultas de la organización (PQRS)."""
        partes = []
        nombre = (self.contacto_principal or '').strip()
        if nombre:
            partes.append(f'Contacto: {nombre}')
        email = (self.email or '').strip()
        if email:
            partes.append(f'Correo: {email}')
        wa = (self.whatsapp_numero or '').strip()
        if wa:
            partes.append(f'WhatsApp: {wa}')
        tel = (self.telefono or '').strip()
        if tel and tel != wa:
            partes.append(f'Teléfono: {tel}')
        return '\n'.join(partes) if partes else ''

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


class FaqOrganizacion(models.Model):
    """FAQ institucional del cliente para PQRS (no es contenido del curso ni Nat)."""

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='faqs_organizacion',
        verbose_name='Organización',
    )
    pregunta = models.CharField(
        max_length=300,
        verbose_name='Pregunta',
        help_text='Cómo la haría el estudiante (ej. ¿Cuándo pagan el bono?).',
    )
    respuesta = models.TextField(
        verbose_name='Respuesta',
        help_text='Texto que el agente envía por WhatsApp si hay coincidencia.',
    )
    palabras_clave = models.CharField(
        max_length=400,
        blank=True,
        default='',
        verbose_name='Palabras clave',
        help_text='Opcional, separadas por coma (bono, pago, nómina). Mejoran el match.',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'FAQ de organización'
        verbose_name_plural = 'FAQ de organización (PQRS)'
        ordering = ['orden', 'pregunta']

    def __str__(self):
        return f'{self.cliente_id}: {self.pregunta[:60]}'


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
