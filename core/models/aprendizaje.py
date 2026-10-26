"""Modelos de aprendizaje (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
from core.models.estudiantes import Estudiante
from core.models.cursos import Curso
from core.models.modulos import Modulo


class EstudianteEventoAprendizaje(models.Model):
    """
    Telemetría de aprendizaje (Centro de Éxito).
    Independiente de EventoIA (trazas técnicas de agentes).
    """

    TIPO_CONTENIDO_ENVIADO = 'contenido_enviado'
    TIPO_LISTO_RECIBIDO = 'listo_recibido'
    TIPO_EVALUACION_RESPONDIDA = 'evaluacion_respondida'
    TIPO_RECORDATORIO_ENVIADO = 'recordatorio_enviado'
    TIPO_RECORDATORIO_RESPONDIDO = 'recordatorio_respondido'
    TIPO_MEDIA_ENTREGADA = 'media_entregada'
    TIPO_MEDIA_FALLIDA = 'media_fallida'
    TIPO_MODULO_INICIADO = 'modulo_iniciado'
    TIPO_MODULO_COMPLETADO = 'modulo_completado'
    TIPO_RETO_PLANTEADO = 'reto_planteado'
    TIPO_RETO_RESPONDIDO = 'reto_respondido'

    TIPO_CHOICES = [
        (TIPO_CONTENIDO_ENVIADO, 'Contenido enviado'),
        (TIPO_LISTO_RECIBIDO, 'Listo recibido'),
        (TIPO_EVALUACION_RESPONDIDA, 'Evaluación respondida'),
        (TIPO_RECORDATORIO_ENVIADO, 'Recordatorio enviado'),
        (TIPO_RECORDATORIO_RESPONDIDO, 'Recordatorio respondido'),
        (TIPO_MEDIA_ENTREGADA, 'Media entregada'),
        (TIPO_MEDIA_FALLIDA, 'Media fallida'),
        (TIPO_MODULO_INICIADO, 'Módulo iniciado'),
        (TIPO_MODULO_COMPLETADO, 'Módulo completado'),
        (TIPO_RETO_PLANTEADO, 'Reto planteado'),
        (TIPO_RETO_RESPONDIDO, 'Reto respondido'),
    ]

    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.CASCADE,
        related_name='eventos_aprendizaje',
    )
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.CASCADE,
        related_name='eventos_aprendizaje',
        null=True,
        blank=True,
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_aprendizaje',
    )
    modulo = models.ForeignKey(
        'Modulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_aprendizaje',
    )
    paso = models.ForeignKey(
        'PasoModulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_aprendizaje',
    )
    seccion = models.ForeignKey(
        'SeccionModulo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_aprendizaje',
    )
    tipo = models.CharField(max_length=40, choices=TIPO_CHOICES, db_index=True)
    canal = models.CharField(max_length=30, default='whatsapp', db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Evento de aprendizaje'
        verbose_name_plural = 'Eventos de aprendizaje'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['estudiante', 'created_at']),
            models.Index(fields=['curso', 'tipo', 'created_at']),
            models.Index(fields=['modulo', 'tipo']),
            models.Index(fields=['cliente', 'tipo', 'created_at']),
        ]

    def __str__(self):
        return f'{self.tipo} · est={self.estudiante_id} · {self.created_at:%Y-%m-%d %H:%M}'


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
