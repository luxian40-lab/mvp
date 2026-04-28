from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# Siete campos clave de la ficha (para cálculo de emisiones / seguimiento).
# Deben alinearse con el flujo de 7 pasos (FlujoPregunta.campo_destino apunta a estos nombres).
CAMPOS_GEI_7 = (
    "nombre_finca",
    "area_ha",
    "num_plantas",
    "fertilizante_kg",
    "concentracion_n_pct",
    "produccion_kg",
    "energia_kwh",
)


class TipoFormulario(models.Model):
    """
    Definición de un formulario secuencial asociado a un curso y a un módulo disparador
    (por ejemplo, al completar el módulo 4, antes del módulo 5).
    """

    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, default="", verbose_name="Descripción")
    curso = models.ForeignKey(
        "core.Curso",
        on_delete=models.CASCADE,
        related_name="tipos_formulario",
        verbose_name="Curso",
    )
    modulo = models.ForeignKey(
        "core.Modulo",
        on_delete=models.CASCADE,
        related_name="tipos_formulario",
        help_text="Módulo que al completar dispara el formulario (p. ej. módulo 4).",
        verbose_name="Módulo disparador",
    )
    cliente = models.ForeignKey(
        "core.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tipos_formulario",
        verbose_name="Cliente",
        help_text="Vacío = aplica a todos los clientes. Específico = solo para ese cliente (tiene prioridad sobre el global).",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    notas = models.TextField(blank=True, default="", verbose_name="Notas internas")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("curso", "nombre")
        verbose_name = "Tipo de formulario"
        verbose_name_plural = "Tipos de formulario"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.curso})"


class FlujoPregunta(models.Model):
    TIPO_DATO = [
        ("float", "Número decimal"),
        ("bool", "Sí o no"),
        ("choice", "Lista de opciones"),
        ("text", "Texto breve"),
    ]

    formulario = models.ForeignKey(
        TipoFormulario, on_delete=models.CASCADE, related_name="flujo_pasos", verbose_name="Formulario"
    )
    orden = models.PositiveSmallIntegerField(verbose_name="Orden")
    campo_destino = models.CharField(
        max_length=80,
        verbose_name="Campo destino en FichaGEI",
        help_text="Nombre del atributo, por ejemplo: fertilizante_kg",
    )
    pregunta_texto = models.TextField(verbose_name="Texto de la pregunta (usted, sin tecnicismos)")
    tipo_dato = models.CharField(max_length=20, choices=TIPO_DATO, default="float", verbose_name="Tipo de dato")
    rango_min = models.FloatField(null=True, blank=True, verbose_name="Mínimo (si aplica)")
    rango_max = models.FloatField(null=True, blank=True, verbose_name="Máximo (si aplica)")
    # Para parseo con modelo de lenguaje: unidad lógica (kg, kWh, ha, etc.)
    unidad_parseo = models.CharField(
        max_length=40,
        blank=True,
        default="",
        verbose_name="Unidad esperada (parseo con IA)",
    )
    opciones_choice = models.TextField(
        blank=True,
        default="",
        help_text="Para tipo «Lista de opciones»: valores separados por | (ej. diésel|gasolina|GLP).",
        verbose_name="Opciones (choice)",
    )
    usar_llm_parseo = models.BooleanField(
        default=False,
        verbose_name="Usar IA para leer el número o cantidad en lenguaje natural",
    )
    es_opcional = models.BooleanField(default=False, verbose_name="Puede omitirse (OMITIR)")
    texto_reintento = models.TextField(
        blank=True,
        default="",
        verbose_name="Mensaje si la respuesta no es válida",
    )

    class Meta:
        ordering = ("formulario", "orden")
        verbose_name = "Paso del flujo"
        verbose_name_plural = "Pasos del flujo"
        unique_together = [("formulario", "orden")]

    def __str__(self) -> str:
        return f"{self.formulario_id} — {self.orden} ({self.campo_destino})"

    def clean(self):
        if self.tipo_dato == "choice" and not (self.opciones_choice or "").strip():
            raise ValidationError(
                {
                    "opciones_choice": "Debe indicar al menos una opción separada por |.",
                }
            )


class FichaGEI(models.Model):
    TIPO_COMBUSTIBLE = [
        ("", "—"),
        ("diesel", "Diésel"),
        ("gasolina", "Gasolina"),
        ("glp", "GLP"),
        ("otro", "Otro / no aplica"),
    ]
    MANEJO_RESIDUOS = [
        ("", "—"),
        ("compost", "Compost o enterrado en finca"),
        ("externo", "Entrega a tercero / recolección"),
        ("quemado", "Quema en campo (no recomendado)"),
        ("otro", "Otra forma / no aplica"),
    ]

    estudiante = models.ForeignKey("core.Estudiante", on_delete=models.CASCADE, related_name="fichas_gei")
    cliente = models.ForeignKey(
        "core.Cliente", on_delete=models.SET_NULL, null=True, blank=True, related_name="fichas_gei"
    )
    curso = models.ForeignKey(
        "core.Curso", on_delete=models.SET_NULL, null=True, blank=True, related_name="fichas_gei"
    )

    nombre_finca = models.CharField(max_length=200, blank=True, default="")
    area_ha = models.FloatField(null=True, blank=True, verbose_name="Área (ha)")
    num_plantas = models.PositiveIntegerField(null=True, blank=True, verbose_name="Número de plantas")
    fertilizante_kg = models.FloatField(null=True, blank=True, verbose_name="Fertilizante (kg)")
    concentracion_n_pct = models.FloatField(
        null=True, blank=True, verbose_name="Concentración de N (%)"
    )
    tipo_combustible = models.CharField(
        max_length=20, choices=TIPO_COMBUSTIBLE, blank=True, default=""
    )
    combustible_gal = models.FloatField(null=True, blank=True, verbose_name="Combustible (gal)")
    energia_kwh = models.FloatField(null=True, blank=True, verbose_name="Energía (kWh)")
    residuos_ton = models.FloatField(null=True, blank=True, verbose_name="Residuos (t)")
    manejo_residuos = models.CharField(
        max_length=30, choices=MANEJO_RESIDUOS, blank=True, default=""
    )
    produccion_kg = models.FloatField(null=True, blank=True, verbose_name="Producción (kg)")
    tiene_bosque = models.BooleanField(null=True, blank=True, verbose_name="¿Tiene bosque o setos?")
    area_bosque_ha = models.FloatField(
        null=True, blank=True, verbose_name="Área de bosque o cobertura (ha)"
    )

    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_update = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ficha GEI"
        verbose_name_plural = "Fichas GEI"
        ordering = ("-fecha_update",)

    @property
    def completitud_pct(self) -> int:
        llenos = 0
        for campo in CAMPOS_GEI_7:
            v = getattr(self, campo, None)
            if v is not None and v != "":
                llenos += 1
        return (100 * llenos) // len(CAMPOS_GEI_7)

    def __str__(self) -> str:
        return f"Ficha GEI {self.estudiante_id} — {self.nombre_finca or 'sin finca'}"


class ResultadoGEI(models.Model):
    """Resultado persistido del balance GEI calculado a partir de una FichaGEI."""

    ficha = models.OneToOneField(
        FichaGEI,
        on_delete=models.CASCADE,
        related_name="resultado",
        verbose_name="Ficha GEI",
    )
    em_fertilizante_kg = models.FloatField(null=True, blank=True, verbose_name="Em. fertilizante (kg CO₂e)")
    em_combustible_kg = models.FloatField(null=True, blank=True, verbose_name="Em. combustible (kg CO₂e)")
    em_energia_kg = models.FloatField(null=True, blank=True, verbose_name="Em. energía (kg CO₂e)")
    em_residuos_kg = models.FloatField(null=True, blank=True, verbose_name="Em. residuos (kg CO₂e)")
    em_total_kg = models.FloatField(null=True, blank=True, verbose_name="Emisiones totales (kg CO₂e)")
    rem_bosque_kg = models.FloatField(null=True, blank=True, verbose_name="Remoción bosque (kg CO₂e)")
    balance_neto_tco2e = models.FloatField(null=True, blank=True, verbose_name="Balance neto (t CO₂e/año)")

    intensidad_kg_co2e_por_kg = models.FloatField(
        null=True, blank=True, verbose_name="Intensidad (kg CO₂e / kg producto)"
    )
    evaluacion = models.CharField(
        max_length=20,
        choices=[
            ("excelente", "Excelente"),
            ("bueno", "Bueno"),
            ("mejorable", "Mejorable"),
        ],
        null=True,
        blank=True,
        verbose_name="Evaluación (benchmark café)",
    )

    completitud_calculo_pct = models.IntegerField(default=0, verbose_name="Completitud del cálculo (%)")
    campos_faltantes = models.JSONField(default=list, blank=True, verbose_name="Campos faltantes")
    fecha_calculo = models.DateTimeField(auto_now=True, verbose_name="Último cálculo")

    class Meta:
        verbose_name = "Resultado GEI"
        verbose_name_plural = "Resultados GEI"

    def __str__(self) -> str:
        return f"Resultado GEI ficha={self.ficha_id}"


class SesionFormulario(models.Model):
    """
    Sesión con estado. `ficha_destino_id` referencia al PK de FichaGEI; se mantiene el nombre
    pedido en la spec y además se guarda FK `ficha` para comodidad en el ORM.
    """

    estudiante = models.ForeignKey("core.Estudiante", on_delete=models.CASCADE, related_name="sesiones_formulario")
    formulario = models.ForeignKey(
        TipoFormulario, on_delete=models.CASCADE, related_name="sesiones", verbose_name="Formulario"
    )
    paso_actual = models.PositiveIntegerField(default=0, verbose_name="Paso (índice 0 = primera pregunta)")
    ficha = models.ForeignKey(
        FichaGEI, on_delete=models.CASCADE, related_name="sesiones", verbose_name="Ficha destino"
    )
    ficha_destino_id = models.PositiveIntegerField(
        editable=False, default=0, help_text="Coincide con ficha_id (compatibilidad)."
    )
    completado = models.BooleanField(default=False)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_update = models.DateTimeField(auto_now=True)
    reintentos_paso = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Reintentos en el paso actual",
    )
    progreso = models.ForeignKey(
        "core.ProgresoEstudiante",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sesiones_formulario_gei",
    )
    modulo_siguiente = models.ForeignKey(
        "core.Modulo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Tras finalizar el formulario, se avanza el curso a este módulo.",
        related_name="sesiones_formulario_que",
    )

    class Meta:
        ordering = ("-fecha_update",)
        verbose_name = "Sesión de formulario"
        verbose_name_plural = "Sesiones de formulario"
        indexes = [
            models.Index(fields=["estudiante", "completado", "fecha_update"]),
        ]

    def save(self, *args, **kwargs):
        if self.ficha_id and self.ficha_destino_id != self.ficha_id:
            self.ficha_destino_id = self.ficha_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Sesión {self.formulario} — {self.estudiante} — paso {self.paso_actual}"

    @property
    def max_reintentos(self) -> int:
        return int(getattr(settings, "FORMULARIO_GEI_MAX_REINTENTOS_PASO", 2) or 2)
