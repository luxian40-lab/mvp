"""Modelos de modulos (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from core.models.estudiantes import Estudiante
from core.models.cursos import Curso


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
                'Texto legacy del módulo completo. Opcional si usa Clase, '
                'Estructura/Materiales o microcontenidos.'
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

    # Course Engine — override opcional (hereda del curso si vacio)
    course_engine_tier = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=[
            ('', '— Heredar del curso —'),
            ('economico', 'Economico (~20-30 s, sin Runway)'),
            ('estandar', 'Estandar (~25-35 s, 1 clip Runway)'),
            ('premium', 'Premium (~35-50 s, hasta 3 clips Runway)'),
        ],
        verbose_name='Tier video IA (modulo)',
        help_text='Vacío = usa tier del curso. Use estandar/premium solo en modulos hero.',
    )
    course_engine_voice_id = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='ElevenLabs Voice ID (modulo)',
        help_text='Override del curso. Util para voz clonada del cliente en un modulo concreto.',
    )
    course_engine_voice_label = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Nombre visible de la voz (modulo)',
    )

    def get_course_engine_tier(self) -> str:
        from core.course_engine.voice_config import resolver_tier_modulo
        return resolver_tier_modulo(self)

    def get_course_engine_voice_id(self) -> str | None:
        from core.course_engine.voice_config import resolver_voice_id_modulo
        return resolver_voice_id_modulo(self)

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

    TIPO_RETO_HEREDAR = ''
    TIPO_RETO_SITUACION = 'situacion_decision'
    TIPO_RETO_DIAGNOSTICO = 'diagnostico'
    TIPO_RETO_PLAN = 'plan_accion'
    TIPO_RETO_APLICACION = 'aplicacion_practica'
    TIPO_RETO_REFLEXION = 'reflexion'
    TIPO_RETO_IA_CHOICES = [
        (TIPO_RETO_HEREDAR, 'Heredar / sin plantilla (solo guía de texto)'),
        (TIPO_RETO_SITUACION, 'Situación + decisión práctica'),
        (TIPO_RETO_DIAGNOSTICO, 'Diagnóstico (qué ve / qué verificaría)'),
        (TIPO_RETO_PLAN, 'Plan de acción (qué haría esta semana)'),
        (TIPO_RETO_APLICACION, 'Aplicación a su finca/trabajo'),
        (TIPO_RETO_REFLEXION, 'Reflexión breve (qué aprendió y cómo lo usa)'),
    ]
    tipo_reto_ia = models.CharField(
        max_length=32,
        choices=TIPO_RETO_IA_CHOICES,
        blank=True,
        default=TIPO_RETO_HEREDAR,
        verbose_name='Tipo de reto Claudia (este módulo)',
        help_text=(
            'Solo importa si este módulo dispara checkpoint (facilitadora). '
            'Plantilla del formato de la pregunta. Vacío = sin plantilla fija.'
        ),
    )
    reto_guia_ia = models.TextField(
        blank=True,
        default='',
        verbose_name='Guía del reto (este módulo)',
        help_text=(
            'Instrucciones y/o ejemplos para Claudia al cerrar ESTE módulo. '
            'Prioridad sobre la guía del curso. Ej: «Situación de caja semanal; '
            'una sola pregunta; que diga qué gasto cortaría primero».'
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

    publicado_wa = models.BooleanField(
        default=True,
        verbose_name='Activo en WhatsApp',
        help_text=(
            'Activo = el bot puede enviar este módulo al avanzar. '
            'Pausado (desmarcado) = no se envía por WA; el estudiante se detiene en el último '
            'módulo activo anterior (no se borra el módulo). '
            'Los módulos nuevos en admin suelen empezar pausados hasta publicar.'
        ),
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        from core.curso.reglas_modulo import validar_contenido_modulo

        super().clean()
        # Admin ModuloAdminForm ya validó con Clase/Estructura/POST; evitar doble fail.
        if getattr(self, '_eki_skip_contenido_model_clean', False):
            return
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
    VIDEO_WHATSAPP = 'whatsapp'
    VIDEO_ENLACE = 'enlace'
    video_entrega = models.CharField(
        max_length=16,
        choices=[
            (VIDEO_WHATSAPP, 'WhatsApp directo'),
            (VIDEO_ENLACE, 'videos.eki.technology'),
        ],
        default=VIDEO_WHATSAPP,
        verbose_name='Entrega del video',
        help_text='Solo aplica si el archivo es video. WhatsApp directo lo adjunta. El enlace abre el reproductor de eki y cuenta la apertura.',
    )
    media_wa_apto = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name='Apto WhatsApp',
        help_text=(
            'True si el último upload de video pasó compresión/gate WA (~16MB, H.264). '
            'Vacío = legado / desconocido. No reprocesa videos antiguos solos.'
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

    @property
    def media_es_video(self) -> bool:
        from core.curso.reglas_modulo import es_video_rastreable

        return es_video_rastreable(self.media_url or '')

    def __str__(self):
        return f'{self.modulo_id} · {self.orden} · {self.titulo}'

    @property
    def es_evaluacion(self):
        if self.tipo in (self.TIPO_EVAL_OPC, self.TIPO_EVAL_ABIERTA):
            return True
        if self.tipo == self.TIPO_CONTENIDO:
            from core.curso.reglas_modulo import paso_contenido_con_mc_como_eval

            return paso_contenido_con_mc_como_eval(self)
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


class ModuloPublicacionEvent(models.Model):
    """Historial de publicación / QA de módulo WA (diff resumido)."""

    ACCION_PUBLICAR = 'publicar'
    ACCION_QA = 'qa_validar'
    ACCION_CHOICES = (
        (ACCION_PUBLICAR, 'Publicar'),
        (ACCION_QA, 'QA pre-publicar'),
    )

    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.CASCADE,
        related_name='eventos_publicacion',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES, default=ACCION_PUBLICAR)
    snapshot_antes = models.JSONField(default=dict, blank=True)
    snapshot_despues = models.JSONField(default=dict, blank=True)
    diff_resumen = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Evento publicación módulo'
        verbose_name_plural = 'Eventos publicación módulo'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.get_accion_display()} · M{self.modulo_id} · {self.created_at:%Y-%m-%d %H:%M}'


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
        """Calcula el porcentaje de avance en el curso (denominador = módulos publicados WA)."""
        total_modulos = modulos_publicados_wa_qs(self.curso).count()
        if total_modulos == 0:
            return 0
        pub_ids = set(modulos_publicados_wa_qs(self.curso).values_list('id', flat=True))
        modulos_completados = self.modulos_completados.filter(modulo_id__in=pub_ids).count()
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


def curso_usa_gate_publicacion_wa(curso: Curso | None) -> bool:
    if curso is None:
        return False
    return not curso.es_modo_clases()


def modulos_publicados_wa_qs(curso: Curso | None):
    if curso is None:
        return Modulo.objects.none()
    if not curso_usa_gate_publicacion_wa(curso):
        return curso.modulos.all()
    return curso.modulos.filter(publicado_wa=True)
