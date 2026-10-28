"""Ficha del negocio: lo que la persona cuenta de sí, por teléfono.

Va por teléfono y no por estudiante ni por sesión: mucha gente de la línea
principal no tiene `Estudiante`, y la sesión es por teléfono y línea.
"""
from django.db import models


class FichaNegocio(models.Model):
    ETAPA_EMPEZANDO = 'empezando'
    ETAPA_VENDE = 'vende'
    ETAPA_CRECER = 'crecer'
    ETAPA_CHOICES = [
        (ETAPA_EMPEZANDO, 'Apenas empezando'),
        (ETAPA_VENDE, 'Ya vende'),
        (ETAPA_CRECER, 'Quiere crecer'),
    ]
    EQUIPO_SOLO = 'solo'
    EQUIPO_FAMILIA = 'familia'
    EQUIPO_TRABAJADORES = 'trabajadores'
    EQUIPO_CHOICES = [
        (EQUIPO_SOLO, 'Solo'),
        (EQUIPO_FAMILIA, 'Con su familia'),
        (EQUIPO_TRABAJADORES, 'Con trabajadores'),
    ]

    telefono = models.CharField(max_length=30, unique=True)
    dedica = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='A qué se dedica',
        help_text='Con sus palabras, sin correos ni números de teléfono.',
    )
    etapa = models.CharField(
        max_length=20, blank=True, default='', choices=ETAPA_CHOICES, verbose_name='Cómo va su negocio',
    )
    equipo = models.CharField(
        max_length=20, blank=True, default='', choices=EQUIPO_CHOICES, verbose_name='Con quién trabaja',
    )
    preguntadas = models.CharField(
        max_length=60,
        blank=True,
        default='',
        help_text='Preguntas ya hechas, separadas por coma. Ninguna se repite.',
    )
    pendiente = models.CharField(
        max_length=20, blank=True, default='', help_text='Pregunta que espera respuesta.',
    )
    pendiente_desde = models.DateTimeField(null=True, blank=True)
    saltadas = models.PositiveSmallIntegerField(default=0)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ficha del negocio'
        verbose_name_plural = 'Fichas del negocio'

    def __str__(self):
        return f'{self.telefono} · {self.dedica[:40] or "sin datos"}'


class DerivacionAsesoria(models.Model):
    """Cada vez que la pregunta libre se lleva a un asesor. Para revisar si se acierta.

    Corregida: justo después la persona cambió de asesor o volvió al menú.
    """
    telefono_hash = models.CharField(max_length=16, help_text='HMAC del teléfono; no es reversible.')
    frase = models.CharField(max_length=300, help_text='Lo que escribió, sin correos ni números.')
    agente = models.CharField(max_length=20)
    agente_secundario = models.CharField(max_length=20, blank=True, default='')
    fuente = models.CharField(max_length=10, help_text='llm o sin_llm (palabras clave).')
    con_contexto = models.BooleanField(default=False, help_text='Se usó lo que ya se sabía de la persona.')
    corregida = models.BooleanField(default=False)
    corregida_a = models.CharField(max_length=20, blank=True, default='', help_text='A dónde se fue.')
    creada_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Derivación de asesoría'
        verbose_name_plural = 'Derivaciones de asesoría'
        ordering = ('-creada_en',)
        indexes = [models.Index(fields=['telefono_hash', '-creada_en'], name='deriv_tel_fecha_idx')]

    def __str__(self):
        return f'{self.agente} · {self.frase[:40]}'
