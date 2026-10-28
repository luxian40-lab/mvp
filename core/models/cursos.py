"""Modelos de cursos (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.models.clientes import Cliente


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
    
    PERFIL_FACILITADOR_HEREDAR = ''
    PERFIL_FACILITADOR_CLAUDIA = 'claudia'
    PERFIL_FACILITADOR_TECNICOAGRO = 'tecnicoagro'
    PERFIL_FACILITADOR_CHOICES = [
        (PERFIL_FACILITADOR_HEREDAR, 'Heredar del cliente'),
        (PERFIL_FACILITADOR_CLAUDIA, 'Claudia (facilitadora ABR eki)'),
        (PERFIL_FACILITADOR_TECNICOAGRO, 'tecnicoagro (copiloto extensión AGROSAVIA)'),
    ]
    perfil_facilitador = models.CharField(
        max_length=20,
        choices=PERFIL_FACILITADOR_CHOICES,
        blank=True,
        default=PERFIL_FACILITADOR_HEREDAR,
        verbose_name='Facilitador de retos (este curso)',
        help_text=(
            'Vacío = usa el facilitador del Cliente. '
            'Elija tecnicoagro solo en programas AGROSAVIA/agro; el resto suele quedar en Claudia.'
        ),
    )

    CONTEXTO_HEREDAR = ''
    CONTEXTO_RURAL = 'rural'
    CONTEXTO_URBANO = 'urbano'
    CONTEXTO_MIXTO = 'mixto'
    CONTEXTO_PARTICIPANTES_CHOICES = [
        (CONTEXTO_HEREDAR, 'Heredar del cliente'),
        (CONTEXTO_RURAL, 'Rural (finca, vereda, cosecha)'),
        (CONTEXTO_URBANO, 'Urbano (negocio, tienda, redes)'),
        (CONTEXTO_MIXTO, 'Mixto (sin asumir campo ni ciudad)'),
    ]
    contexto_participantes = models.CharField(
        max_length=10,
        choices=CONTEXTO_PARTICIPANTES_CHOICES,
        blank=True,
        default=CONTEXTO_HEREDAR,
        db_default=CONTEXTO_HEREDAR,
        verbose_name='A quién va dirigido',
        help_text=(
            'Vacío = usa el del Cliente. Define los ejemplos que usan el Formador y el Compañero: '
            'rural habla de finca y cosecha; urbano, de negocio y redes; mixto no asume ninguno.'
        ),
    )

    # PREGUNTAS EJEMPLO PARA IA — alimentadas por admin (reto facilitador + recuperación)
    preguntas_ejemplo_ia = models.TextField(
        blank=True,
        default='',
        verbose_name='Guía de retos / preguntas para IA (curso)',
        help_text=(
            'Guía al facilitador (Claudia o tecnicoagro) y a la pregunta de recuperación: tono, tipo de '
            'situación y 1–3 ejemplos. Una idea por línea. '
            'Si un módulo checkpoint tiene su propia guía/tipo de reto, esa manda y esta '
            'queda como complemento del curso.'
        ),
    )
    dias_espera_entre_modulos = models.IntegerField(
        default=0,
        verbose_name='Días de espera entre módulos',
        help_text='0 = flujo libre. >0 bloquea avance hasta cumplir días entre módulos. Para el mismo curso en varias empresas con ritmos distintos, usar Configuración drip en el admin del Cliente.'
    )

    # Course Engine — defaults del curso (modulo puede override)
    course_engine_tier = models.CharField(
        max_length=20,
        choices=[
            ('economico', 'Economico (~20-30 s, sin Runway)'),
            ('estandar', 'Estandar (~25-35 s, 1 clip Runway)'),
            ('premium', 'Premium (~35-50 s, hasta 3 clips Runway)'),
        ],
        default='economico',
        verbose_name='Tier video IA (default curso)',
        help_text='Tier por defecto al generar micro-videos de modulos. Cada modulo puede override.',
    )
    course_engine_voice_id = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='ElevenLabs Voice ID',
        help_text=(
            'ID de voz ElevenLabs (biblioteca o voz clonada del cliente). '
            'Ej. Wb1wmVQjMx9g2QSIOTPI. Si vacio, usa ELEVENLABS_VOICE_ID del entorno.'
        ),
    )
    course_engine_voice_label = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Nombre visible de la voz',
        help_text='Etiqueta ops: «Voz Maria», «Agronomo cliente Cenipalma», etc.',
    )
    course_engine_format = models.CharField(
        max_length=24,
        choices=[
            ('solo_video', 'Solo video MP4 (1 paso WA)'),
            ('video_infografia', 'Video + infografía PNG (2 pasos)'),
            ('mixto_completo', 'Mixto completo: video + infografía + podcast (3 pasos)'),
            ('mixto_ligero', 'Ligero: video económico sin podcast ni PNG suelta'),
        ],
        default='video_infografia',
        verbose_name='Formato Course Engine (segmentación)',
        help_text='Cómo se segmenta cada módulo al generar contenido IA (pasos WhatsApp).',
    )
    course_engine_podcast_minutos = models.PositiveSmallIntegerField(
        choices=[(2, '2 min'), (3, '3 min'), (4, '4 min')],
        default=2,
        verbose_name='Podcast (minutos)',
        help_text='Duración objetivo del podcast en formato mixto_completo.',
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

    catalogo_menu = models.BooleanField(
        default=False,
        verbose_name='Catálogo general del menú',
        help_text=(
            'Sin cliente y marcado: sale en Formación. Al crear un curso general '
            'queda marcado. WhatsApp muestra hasta 10 por carrusel; si hay más, '
            'manda otro a continuación. Desmárquelo para ocultarlo.'
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

    MODO_AULA_MODULOS = 'modulos'
    MODO_AULA_CLASES = 'clases'
    MODO_AULA_CHOICES = [
        (MODO_AULA_MODULOS, 'Módulos (WhatsApp + avance)'),
        (MODO_AULA_CLASES, 'Clases / biblioteca (sin avance WA)'),
    ]
    modo_aula = models.CharField(
        max_length=20,
        choices=MODO_AULA_CHOICES,
        default=MODO_AULA_MODULOS,
        verbose_name='Experiencia en aula',
        help_text=(
            'Clases: en Aprende se habla de «Clases», Biblioteca es el hub '
            '(«mis clases guardadas») y no se menciona avance ni *listo*. '
            'Ideal para curso C / 10x informativo.'
        ),
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"

    def __str__(self):
        return f"{self.emoji} {self.nombre}"

    def es_modo_clases(self) -> bool:
        return (self.modo_aula or self.MODO_AULA_MODULOS) == self.MODO_AULA_CLASES

    def save(self, *args, **kwargs):
        # Un curso general nuevo entra solo al carrusel de Formación.
        if self._state.adding and self.cliente_id is None:
            self.catalogo_menu = True
            uf = kwargs.get('update_fields')
            if uf is not None:
                kwargs['update_fields'] = list(set(uf) | {'catalogo_menu'})
        # Curso C / informativo: sin puntos, ranking ni retos IA.
        if self.es_modo_clases():
            self.usar_gamificacion = False
            self.usar_agentes_ia = False
            uf = kwargs.get('update_fields')
            if uf is not None:
                kwargs['update_fields'] = list(
                    set(uf) | {'usar_gamificacion', 'usar_agentes_ia'}
                )
        super().save(*args, **kwargs)

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
